"""
学习内容托管服务

维护「分类 → 专题」的路由事实源，把发布的 HTML 学习页落盘，并保证事实源与落盘一致。
发布走「写盘前先校验 → 原子替换 → 快照回滚」，避免替换已有专题时因回滚把旧内容删掉。
"""

import html
import json
import os
import re
from datetime import date
from pathlib import Path
from typing import Optional

from ..config import settings
from ..learn_pages import render_category_page, render_index_page

SLUG_RE = re.compile(r"^[a-z0-9]+(-[a-z0-9]+)*$")

REGISTRY_FILENAME = "registry.json"
TOPIC_FILENAME = "index.html"


class LearnError(Exception):
    """发布流程中的可预期错误（入参不合法、事实源与落盘不一致等）"""


class LearnService:
    """学习内容服务类"""

    def __init__(self):
        self.root = settings.data_dir / "learn"
        self.registry_path = self.root / REGISTRY_FILENAME

    # ---------------------------------------------------------------- 事实源

    def load_registry(self) -> dict:
        """
        读取路由事实源

        Returns:
            事实源内容；尚未发布过任何内容时返回空结构

        Raises:
            LearnError: 文件存在但无法解析
        """
        if not self.registry_path.is_file():
            return {"categories": []}

        try:
            with open(self.registry_path, "r", encoding="utf-8") as f:
                data = json.load(f)
        except (OSError, json.JSONDecodeError) as e:
            raise LearnError(f"路由事实源读取失败：{e}")

        if not isinstance(data.get("categories"), list):
            raise LearnError("路由事实源缺少 categories[]")

        return data

    def _write_registry(self, data: dict) -> None:
        """原子写入事实源"""
        self.root.mkdir(parents=True, exist_ok=True)
        tmp = self.registry_path.with_suffix(".json.tmp")
        tmp.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
        os.replace(tmp, self.registry_path)

    # ---------------------------------------------------------------- 路径

    def topic_file(self, category: str, slug: str) -> Path:
        """专题正文的落盘路径"""
        return self.root / category / slug / TOPIC_FILENAME

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
            for topic in category.get("topics", []):
                path = topic.get("path", "")
                registered.add(path)
                target = (
                    self.root / path / TOPIC_FILENAME if path.endswith("/") else self.root / path
                )
                if not target.is_file():
                    problems.append(f"事实源登记但落盘不存在：{path}")

        if self.root.is_dir():
            for category_dir in sorted(self.root.iterdir()):
                if not category_dir.is_dir():
                    continue
                for topic_dir in sorted(category_dir.iterdir()):
                    if not topic_dir.is_dir():
                        continue
                    if not (topic_dir / TOPIC_FILENAME).is_file():
                        continue
                    relative = f"{category_dir.name}/{topic_dir.name}/"
                    if relative not in registered:
                        problems.append(f"落盘存在但事实源未登记：{relative}")

        return problems

    # ---------------------------------------------------------------- 发布

    def publish(self, payload: dict) -> dict:
        """
        发布一篇学习专题

        Args:
            payload: 发布请求体

        Returns:
            {"url": ..., "category_url": ...}，均为站内相对路径

        Raises:
            LearnError: 入参不合法、事实源与落盘不一致、或自检未通过
        """
        category_slug = str(payload.get("category") or "").strip()
        slug = str(payload.get("slug") or "").strip()
        title = str(payload.get("title") or "").strip()
        desc = str(payload.get("desc") or "").strip()
        html_body = payload.get("html") or ""
        tags = payload.get("tags") or []
        published_on = str(payload.get("date") or date.today().isoformat()).strip()

        if not SLUG_RE.match(category_slug):
            raise LearnError("category 需为 kebab-case")
        if not SLUG_RE.match(slug):
            raise LearnError("slug 需为 kebab-case")
        if not title:
            raise LearnError("title 不能为空")
        if not desc:
            raise LearnError("desc 不能为空")
        if not html_body.strip():
            raise LearnError("html 不能为空")
        if not isinstance(tags, list):
            raise LearnError("tags 需为数组")

        # 写盘前先校验当前一致性：已有脏数据在此拦下，不进入写入阶段
        registry = self.load_registry()
        problems = self.validate_consistency(registry)
        if problems:
            raise LearnError("路由事实源与落盘不一致，拒绝发布：" + "；".join(problems))

        categories = registry["categories"]
        category = next((c for c in categories if c.get("slug") == category_slug), None)
        if category is None:
            category_name = str(payload.get("category_name") or "").strip()
            if not category_name:
                raise LearnError(f"分类 {category_slug} 不存在，需同时提供 category_name")
            category = {
                "slug": category_slug,
                "name": category_name,
                "description": str(payload.get("category_description") or "").strip(),
                "topics": [],
            }
            categories.append(category)

        path = f"{category_slug}/{slug}/"
        topic = {
            "slug": slug,
            "title": title,
            "desc": desc,
            "path": path,
            "date": published_on,
            "tags": tags,
        }
        topics = [t for t in category.get("topics", []) if t.get("path") != path]
        category["topics"] = topics + [topic]

        target = self.topic_file(category_slug, slug)
        previous_html = target.read_text(encoding="utf-8") if target.is_file() else None
        previous_registry = (
            self.registry_path.read_text(encoding="utf-8") if self.registry_path.is_file() else None
        )

        try:
            target.parent.mkdir(parents=True, exist_ok=True)
            tmp = target.with_suffix(".html.tmp")
            tmp.write_text(html_body, encoding="utf-8")
            os.replace(tmp, target)

            self._write_registry(registry)

            problems = self.validate_consistency(self.load_registry())
            if problems:
                raise LearnError("发布后一致性校验失败：" + "；".join(problems))

            self._verify(category_slug, slug, title, path)
        except Exception:
            self._rollback(target, previous_html, previous_registry)
            raise

        return {"url": f"/learn/{path}", "category_url": f"/learn/{category_slug}/"}

    def _verify(self, category_slug: str, slug: str, title: str, path: str) -> None:
        """
        发布后自检公开可用性

        断言落盘文件非空、事实源含该条目、索引页与分类页的渲染结果中
        均出现该专题的标题与路径。
        """
        target = self.topic_file(category_slug, slug)
        if not target.is_file() or not target.read_text(encoding="utf-8").strip():
            raise LearnError("验活失败：落盘文件缺失或为空")

        registry = self.load_registry()
        registered = [
            t.get("path") for category in registry["categories"] for t in category.get("topics", [])
        ]
        if path not in registered:
            raise LearnError("验活失败：事实源缺少该条目")

        expected = (html.escape(title), html.escape(path))
        pages = {
            "索引页": render_index_page(registry),
            "分类页": render_category_page(registry, category_slug) or "",
        }
        for page_name, page in pages.items():
            for value in expected:
                if value not in page:
                    raise LearnError(f"验活失败：{page_name}未呈现该专题的标题与路径")

    def _rollback(
        self, target: Path, previous_html: Optional[str], previous_registry: Optional[str]
    ) -> None:
        """
        回滚到发布前状态

        正文有旧内容则恢复、仅新建的才删除——不对已有专题 unlink，
        否则替换场景下回滚会把那篇旧文章删掉且无从恢复。
        """
        if previous_html is None:
            target.unlink(missing_ok=True)
        else:
            target.write_text(previous_html, encoding="utf-8")

        if previous_registry is None:
            self.registry_path.unlink(missing_ok=True)
        else:
            self.registry_path.write_text(previous_registry, encoding="utf-8")


# 全局学习内容服务实例
learn_service = LearnService()
