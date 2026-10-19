"""
页面托管服务

维护「分类 → 页面」的路由事实源，把发布的页面目录落盘，并保证事实源与落盘一致。
页面目录可携带任意静态资源；共享资源集中存放，页面用绝对路径引用。

安全边界：所有资源请求解析出的真实路径必须落在各自允许的根内。
页面根（DATA_DIR/pages）与数据目录根在结构上分开——数据目录下的
元信息文件带着每个上传文件的访问凭据，页面路由不该有能力触达它。
"""

import html as html_module
import io
import json
import os
import re
import shutil
import zipfile
from datetime import date
from pathlib import Path, PurePosixPath
from typing import Optional

from ..config import settings
from ..pages_render import render_category_page, render_index_page

SLUG_RE = re.compile(r"^[a-z0-9]+(-[a-z0-9]+)*$")

REGISTRY_FILENAME = "registry.json"
PAGE_ENTRY = "index.html"
ASSETS_DIRNAME = "assets"


class PageError(Exception):
    """发布流程中的可预期错误（入参不合法、事实源与落盘不一致等）"""


class PagesService:
    """页面托管服务类"""

    def __init__(self):
        self.root = settings.data_dir / "pages"
        self.registry_path = self.root / REGISTRY_FILENAME
        self.assets_root = self.root / ASSETS_DIRNAME
        self.max_page_size = settings.max_file_size

    # ---------------------------------------------------------------- 事实源

    def load_registry(self) -> dict:
        """
        读取路由事实源

        Returns:
            事实源内容；尚未发布过任何页面时返回空结构

        Raises:
            PageError: 文件存在但无法解析
        """
        if not self.registry_path.is_file():
            return {"categories": []}

        try:
            with open(self.registry_path, "r", encoding="utf-8") as f:
                data = json.load(f)
        except (OSError, json.JSONDecodeError) as e:
            raise PageError(f"路由事实源读取失败：{e}")

        if not isinstance(data.get("categories"), list):
            raise PageError("路由事实源缺少 categories[]")

        return data

    def _write_registry(self, data: dict) -> None:
        """原子写入事实源"""
        self.root.mkdir(parents=True, exist_ok=True)
        tmp = self.registry_path.with_suffix(".json.tmp")
        tmp.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
        os.replace(tmp, self.registry_path)

    # ---------------------------------------------------------------- 路径

    def page_dir(self, category: str, slug: str) -> Path:
        """页面目录"""
        return self.root / category / slug

    def page_entry(self, category: str, slug: str) -> Path:
        """页面入口文件"""
        return self.page_dir(category, slug) / PAGE_ENTRY

    @staticmethod
    def _resolve_within(root: Path, relative: str) -> Optional[Path]:
        """
        把相对路径解析到允许根内

        先拼接再 `resolve()`，然后用「是否仍在根内」判定——`resolve()` 会展开符号链接
        与 `..`，绝对路径在拼接时会丢弃左边的根，三种逃逸方式因此收敛成同一句判定，
        不需要另外枚举禁止模式。

        Args:
            root: 允许的根目录
            relative: 客户端给出的相对路径

        Returns:
            解析后的文件路径；越出根、不是普通文件或根不存在时返回 None
        """
        try:
            root_resolved = root.resolve(strict=True)
        except (OSError, RuntimeError):
            return None

        if not root_resolved.is_dir():
            return None

        try:
            candidate = (root_resolved / relative).resolve()
        except (OSError, RuntimeError):
            return None

        if not candidate.is_relative_to(root_resolved):
            return None

        if not candidate.is_file():
            return None

        return candidate

    def resolve_page_resource(self, category: str, slug: str, resource: str) -> Optional[Path]:
        """页面内的资源文件；越出该页面目录时返回 None"""
        return self._resolve_within(self.page_dir(category, slug), resource)

    def resolve_shared_asset(self, resource: str) -> Optional[Path]:
        """共享资源文件；越出共享资源目录时返回 None"""
        return self._resolve_within(self.assets_root, resource)

    # ---------------------------------------------------------------- 一致性

    def validate_consistency(self, registry: dict) -> list[str]:
        """
        双向校验事实源与落盘

        Args:
            registry: 路由事实源

        Returns:
            不一致项的描述列表；空列表表示一致
        """
        problems: list[str] = []
        registered: set[str] = set()

        for category in registry.get("categories", []):
            for page in category.get("pages", []):
                path = page.get("path", "")
                registered.add(path)
                if not (self.root / path / PAGE_ENTRY).is_file():
                    problems.append(f"事实源登记但落盘不存在：{path}")

        if self.root.is_dir():
            for category_dir in sorted(self.root.iterdir()):
                if not category_dir.is_dir() or category_dir.name == ASSETS_DIRNAME:
                    continue
                for page_dir in sorted(category_dir.iterdir()):
                    if not page_dir.is_dir() or page_dir.name.startswith("."):
                        continue
                    relative = f"{category_dir.name}/{page_dir.name}/"
                    if (page_dir / PAGE_ENTRY).is_file() and relative not in registered:
                        problems.append(f"落盘存在但事实源未登记：{relative}")

        return problems

    # ---------------------------------------------------------------- 发布

    def publish(
        self,
        meta: dict,
        html: Optional[str] = None,
        bundle: Optional[bytes] = None,
    ) -> dict:
        """
        发布一个页面

        正文可以是直接给出的 HTML 字符串，也可以是解压后即页面目录的 zip 包。

        Args:
            meta: 页面元信息（category/slug/title/desc/tags/date/...）
            html: HTML 正文（单文件页面）
            bundle: zip 包内容（多文件页面）

        Returns:
            {"url": ..., "category_url": ...}，均为站内相对路径

        Raises:
            PageError: 入参不合法、事实源与落盘不一致、或自检未通过
        """
        category_slug = str(meta.get("category") or "").strip()
        slug = str(meta.get("slug") or "").strip()
        title = str(meta.get("title") or "").strip()
        desc = str(meta.get("desc") or "").strip()
        tags = meta.get("tags") or []
        published_on = str(meta.get("date") or date.today().isoformat()).strip()

        if not SLUG_RE.match(category_slug):
            raise PageError("category 需为 kebab-case")
        if category_slug == ASSETS_DIRNAME:
            raise PageError(f"{ASSETS_DIRNAME} 是共享资源的保留分类名")
        if not SLUG_RE.match(slug):
            raise PageError("slug 需为 kebab-case")
        if not title:
            raise PageError("title 不能为空")
        if not desc:
            raise PageError("desc 不能为空")
        if not isinstance(tags, list):
            raise PageError("tags 需为数组")

        has_html = bool(html and html.strip())
        has_bundle = bool(bundle)
        if has_html == has_bundle:
            raise PageError("html 与 bundle 必须且只能提供一个")

        # 写盘前先校验当前一致性：已有脏数据在此拦下，不进入写入阶段
        registry = self.load_registry()
        problems = self.validate_consistency(registry)
        if problems:
            raise PageError("路由事实源与落盘不一致，拒绝发布：" + "；".join(problems))

        categories = registry["categories"]
        category = next((c for c in categories if c.get("slug") == category_slug), None)
        if category is None:
            category_name = str(meta.get("category_name") or "").strip()
            if not category_name:
                raise PageError(f"分类 {category_slug} 不存在，需同时提供 category_name")
            category = {
                "slug": category_slug,
                "name": category_name,
                "description": str(meta.get("category_description") or "").strip(),
                "pages": [],
            }
            categories.append(category)

        path = f"{category_slug}/{slug}/"
        entry = {
            "slug": slug,
            "title": title,
            "desc": desc,
            "path": path,
            "date": published_on,
            "tags": tags,
        }
        pages = [p for p in category.get("pages", []) if p.get("path") != path]
        category["pages"] = pages + [entry]

        target = self.page_dir(category_slug, slug)
        tmp = target.parent / f".{slug}.tmp"
        backup = target.parent / f".{slug}.old"
        existed = target.is_dir()

        previous_registry = (
            self.registry_path.read_text(encoding="utf-8") if self.registry_path.is_file() else None
        )

        try:
            shutil.rmtree(tmp, ignore_errors=True)
            shutil.rmtree(backup, ignore_errors=True)

            target.parent.mkdir(parents=True, exist_ok=True)
            if has_bundle:
                self._extract_bundle(bundle, tmp)
            else:
                tmp.mkdir(parents=True, exist_ok=True)
                (tmp / PAGE_ENTRY).write_text(html, encoding="utf-8")

            if existed:
                os.replace(target, backup)
            os.replace(tmp, target)

            self._write_registry(registry)

            problems = self.validate_consistency(self.load_registry())
            if problems:
                raise PageError("发布后一致性校验失败：" + "；".join(problems))

            self._verify(category_slug, slug, title, path)
        except Exception:
            self._restore_page(target, tmp, backup, existed)
            self._restore_registry(previous_registry)
            raise
        else:
            shutil.rmtree(backup, ignore_errors=True)

        return {"url": f"/pages/{path}", "category_url": f"/pages/{category_slug}/"}

    def _extract_bundle(self, bundle: bytes, target: Path) -> None:
        """
        解压页面 zip 到目标目录

        成员路径逐条校验：拒绝绝对路径、上跳段与符号链接成员；
        解压总量受上限约束，防止 zip 炸弹。

        Raises:
            PageError: 包内容不合法
        """
        try:
            archive = zipfile.ZipFile(io.BytesIO(bundle))
        except zipfile.BadZipFile as e:
            raise PageError(f"bundle 不是合法的 zip：{e}")

        with archive:
            members = []
            total = 0

            for info in archive.infolist():
                name = info.filename
                if name.endswith("/"):
                    continue

                parts = PurePosixPath(name).parts
                if name.startswith("/") or any(p in ("..", "") for p in parts):
                    raise PageError(f"zip 成员路径不合法：{name}")

                # unix 权限位里的文件类型：符号链接成员一律拒绝
                if (info.external_attr >> 16) & 0o170000 == 0o120000:
                    raise PageError(f"zip 成员不能是符号链接：{name}")

                total += info.file_size
                if total > self.max_page_size:
                    raise PageError("zip 解压后超出大小上限")

                members.append(name)

            if PAGE_ENTRY not in members:
                raise PageError(f"zip 根目录下缺少 {PAGE_ENTRY}")

            target.mkdir(parents=True, exist_ok=True)
            for name in members:
                destination = target / PurePosixPath(name)
                destination.parent.mkdir(parents=True, exist_ok=True)
                with archive.open(name) as src, open(destination, "wb") as out:
                    shutil.copyfileobj(src, out)

    def publish_asset(self, relative_path: str, content: bytes) -> str:
        """
        发布共享资源

        Args:
            relative_path: 相对共享资源目录的路径
            content: 文件内容

        Returns:
            该资源的站内相对路径

        Raises:
            PageError: 路径不合法或超出大小上限
        """
        relative_path = (relative_path or "").strip()
        if not relative_path or relative_path.startswith("/"):
            raise PageError("资源路径不能为空或以 / 开头")

        parts = PurePosixPath(relative_path).parts
        if any(p in ("..", "") for p in parts):
            raise PageError("资源路径不能含上跳段")

        if len(content) > self.max_page_size:
            raise PageError("共享资源超出大小上限")

        destination = self.assets_root / PurePosixPath(relative_path)
        destination.parent.mkdir(parents=True, exist_ok=True)

        tmp = destination.parent / f"{destination.name}.tmp"
        tmp.write_bytes(content)
        os.replace(tmp, destination)

        return f"/pages/{ASSETS_DIRNAME}/{relative_path}"

    # ---------------------------------------------------------------- 回滚

    def _restore_page(self, target: Path, tmp: Path, backup: Path, existed: bool) -> None:
        """把页面目录恢复到发布前状态"""
        shutil.rmtree(tmp, ignore_errors=True)

        if backup.is_dir():
            shutil.rmtree(target, ignore_errors=True)
            backup.rename(target)
        elif not existed:
            shutil.rmtree(target, ignore_errors=True)

    def _restore_registry(self, previous_registry: Optional[str]) -> None:
        """把事实源恢复到发布前状态"""
        if previous_registry is None:
            self.registry_path.unlink(missing_ok=True)
        else:
            self.registry_path.write_text(previous_registry, encoding="utf-8")

    # ---------------------------------------------------------------- 自检

    def _verify(self, category_slug: str, slug: str, title: str, path: str) -> None:
        """
        发布后自检公开可用性

        断言页面入口非空、事实源含该条目、索引页与分类页的渲染结果中
        均出现该页面的标题与路径。
        """
        entry = self.page_entry(category_slug, slug)
        if not entry.is_file() or not entry.read_text(encoding="utf-8").strip():
            raise PageError("验活失败：页面入口缺失或为空")

        registry = self.load_registry()
        registered = [
            p.get("path") for category in registry["categories"] for p in category.get("pages", [])
        ]
        if path not in registered:
            raise PageError("验活失败：事实源缺少该条目")

        expected = (html_module.escape(title), html_module.escape(path))
        rendered = {
            "索引页": render_index_page(registry),
            "分类页": render_category_page(registry, category_slug) or "",
        }
        for page_name, page in rendered.items():
            for value in expected:
                if value not in page:
                    raise PageError(f"验活失败：{page_name}未呈现该页面的标题与路径")


# 全局页面托管服务实例
pages_service = PagesService()
