"""
页面托管测试

覆盖发布鉴权、事实源与落盘的双向校验、zip 发布、页面资源、共享资源、
资源越权防护、替换场景的回滚、公开浏览与无尾斜杠重定向。
"""

import asyncio
import io
import zipfile

import pytest
from fastapi import HTTPException
from fastapi.testclient import TestClient

from transit.config import settings
from transit.main import app
from transit.routers.pages import page_resource
from transit.services.pages_service import PageError, pages_service

client = TestClient(app)

CATEGORY = "test-cat"


def publish(slug: str, title: str = "示例页面", html: str = "<h1>正文</h1>", **overrides):
    """以表单形式发出一次单文件页面发布"""
    data = {
        "category": CATEGORY,
        "slug": slug,
        "title": title,
        "desc": "一句话摘要",
        "html": html,
        "date": "2026-10-17",
        # 分类已存在时该字段被忽略；首次发布时用它建分类
        "category_name": "测试分类",
    }
    data.update(overrides)
    return client.post("/pages/publish", data=data)


def make_zip(files: dict[str, bytes]) -> bytes:
    """构造一个内存 zip"""
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w") as archive:
        for name, content in files.items():
            archive.writestr(name, content)
    return buffer.getvalue()


def publish_bundle(slug: str, files: dict[str, bytes], **overrides):
    """以 zip 形式发出一次多文件页面发布"""
    data = {
        "category": CATEGORY,
        "slug": slug,
        "title": "带资源的页面",
        "desc": "一句话摘要",
        "date": "2026-10-17",
        "category_name": "测试分类",
    }
    data.update(overrides)
    payload = make_zip(files)
    return client.post(
        "/pages/publish",
        data=data,
        files={"bundle": ("page.zip", payload, "application/zip")},
    )


def snapshot() -> set[str]:
    """数据目录下页面托管部分的当前文件集合"""
    if not pages_service.root.is_dir():
        return set()
    return {str(p.relative_to(pages_service.root)) for p in pages_service.root.rglob("*")}


# ---------------------------------------------------------------- 发布鉴权


def test_publish_requires_write_token(monkeypatch):
    """缺写凭据与写凭据错误均被拒，且不产生落盘变更"""
    monkeypatch.setattr(settings, "auth_enabled", True)
    monkeypatch.setattr(settings, "write_tokens", "write-secret")

    before = snapshot()
    body = {"category": CATEGORY, "slug": "denied", "title": "t", "desc": "d", "html": "<p>x</p>"}

    assert client.post("/pages/publish", data=body).status_code == 401
    assert (
        client.post(
            "/pages/publish", data=body, headers={"Authorization": "Bearer nope"}
        ).status_code
        == 401
    )

    assert snapshot() == before


# ---------------------------------------------------------------- 入参校验


def test_publish_rejects_non_kebab_case_and_reserved_category():
    """分类与页面标识必须是 kebab-case；assets 是保留分类名"""
    assert publish("Bad_Slug").status_code == 400
    assert publish("ok-slug", category="Bad_Cat").status_code == 400
    response = publish("ok-slug", category="assets")
    assert response.status_code == 400
    assert "保留" in response.json()["detail"]


def test_publish_rejects_empty_required_fields():
    """标题、摘要不能为空，正文与包必须二选一（缺字段由框架拦为 422，业务校验拦为 400）"""
    assert publish("empty-title", title="").status_code in (400, 422)
    assert publish("empty-desc", desc="").status_code in (400, 422)
    assert publish("empty-html", html="   ").status_code == 400


def test_publish_new_category_requires_display_name():
    """分类不存在且未提供显示名时报错，且不留半成品"""
    response = publish("brand-new", category="brand-new-cat", category_name=None)
    assert response.status_code == 400
    assert "category_name" in response.json()["detail"]
    assert not pages_service.page_entry("brand-new-cat", "brand-new").is_file()


# ---------------------------------------------------------------- 发布主流程


def test_publish_new_page():
    """发布一篇单文件页面并登记进事实源"""
    response = publish("first-page", title="第一篇")
    assert response.status_code == 200

    body = response.json()
    assert body["url"].endswith(f"/pages/{CATEGORY}/first-page/")
    assert body["category_url"].endswith(f"/pages/{CATEGORY}/")

    registry = pages_service.load_registry()
    paths = [p["path"] for c in registry["categories"] for p in c["pages"]]
    assert f"{CATEGORY}/first-page/" in paths

    entry = client.get(f"/pages/{CATEGORY}/first-page/")
    assert entry.status_code == 200
    assert entry.headers["content-type"].startswith("text/html")
    assert "正文" in entry.text


def test_publish_creates_category_with_display_name():
    """分类不存在但提供了显示名时，分类被一并登记"""
    response = publish(
        "under-new-cat", category="fresh-cat", category_name="新分类", category_description="说明"
    )
    assert response.status_code == 200

    registry = pages_service.load_registry()
    category = next(c for c in registry["categories"] if c["slug"] == "fresh-cat")
    assert category["name"] == "新分类"
    assert category["description"] == "说明"


# ---------------------------------------------------------------- 页面静态资源


def test_publish_bundle_serves_relative_assets():
    """zip 发布后，页面内资源可按相对路径取到"""
    response = publish_bundle(
        "bundled",
        {
            "index.html": b'<html><head><link rel="stylesheet" href="./style.css"></head></html>',
            "style.css": b"body{color:red}",
            "assets/logo.svg": b"<svg></svg>",
        },
    )
    assert response.status_code == 200

    entry = client.get(f"/pages/{CATEGORY}/bundled/")
    assert entry.status_code == 200
    assert "./style.css" in entry.text

    style = client.get(f"/pages/{CATEGORY}/bundled/style.css")
    assert style.status_code == 200
    assert style.headers["content-type"].startswith("text/css")
    assert style.text == "body{color:red}"

    logo = client.get(f"/pages/{CATEGORY}/bundled/assets/logo.svg")
    assert logo.status_code == 200
    assert logo.headers["content-type"].startswith("image/svg+xml")
    assert logo.headers["content-security-policy"] == "sandbox"


def test_bundle_without_entry_is_rejected():
    """zip 根目录下缺少 index.html 时发布失败且不留半成品"""
    before = snapshot()
    response = publish_bundle("no-entry", {"other.html": b"<html></html>"})
    assert response.status_code == 400
    assert "index.html" in response.json()["detail"]
    assert snapshot() == before


def test_bundle_with_traversal_member_is_rejected():
    """zip 含上跳成员时发布失败"""
    before = snapshot()
    response = publish_bundle("evil", {"index.html": b"<html></html>", "../../escape.txt": b"x"})
    assert response.status_code == 400
    assert snapshot() == before


def test_missing_page_resource_returns_404():
    """页面目录下不存在的资源返回 404"""
    publish("no-resource")
    assert client.get(f"/pages/{CATEGORY}/no-resource/missing.css").status_code == 404


# ---------------------------------------------------------------- 共享资源


def test_shared_asset_requires_write_token(monkeypatch):
    """发布共享资源需要写凭据"""
    monkeypatch.setattr(settings, "auth_enabled", True)
    monkeypatch.setattr(settings, "write_tokens", "write-secret")

    response = client.post(
        "/pages/assets", data={"path": "theme.css"}, files={"file": ("theme.css", b"a{}")}
    )
    assert response.status_code == 401


def test_shared_asset_publish_and_read():
    """共享资源发布后可按绝对路径取到，嵌套路径也能命中共享资源路由"""
    response = client.post(
        "/pages/assets", data={"path": "theme/main.css"}, files={"file": ("main.css", b"body{}")}
    )
    assert response.status_code == 200
    assert response.json()["url"].endswith("/pages/assets/theme/main.css")

    asset = client.get("/pages/assets/theme/main.css")
    assert asset.status_code == 200
    assert asset.text == "body{}"

    assert client.get("/pages/assets/theme/missing.css").status_code == 404


def test_shared_asset_rejects_traversal_path():
    """共享资源的发布路径不能上跳"""
    response = client.post(
        "/pages/assets", data={"path": "../escape.css"}, files={"file": ("x.css", b"x")}
    )
    assert response.status_code == 400


# ---------------------------------------------------------------- 资源越权


def test_resource_resolver_confines_to_root():
    """路径解析把上跳、绝对路径与符号链接逃逸都收敛成越界"""
    publish("confine")
    page_dir = pages_service.page_dir(CATEGORY, "confine")

    assert pages_service._resolve_within(page_dir, "../other-page/index.html") is None
    assert pages_service._resolve_within(page_dir, "/etc/passwd") is None
    assert pages_service._resolve_within(page_dir, "../../../.meta.whatever.json") is None
    assert pages_service._resolve_within(page_dir, "index.html") is not None


def test_symlink_escaping_page_dir_is_rejected():
    """页面目录内指向根外的符号链接不能被解析"""
    publish("symlinked")
    page_dir = pages_service.page_dir(CATEGORY, "symlinked")
    link = page_dir / "escape.txt"
    link.symlink_to("/etc/hostname")

    assert pages_service._resolve_within(page_dir, "escape.txt") is None


def test_http_traversal_cannot_reach_data_dir_meta():
    """
    经页面资源路径无法读到数据目录下的元信息文件

    注意：httpx 会在客户端归一化 URL 里的 `..`，走不到服务端，所以这里直接调用
    路由处理函数（等价于服务端收到该路径后的行为），另用百分号编码路径走一次真实 HTTP。
    """
    publish("guarded")

    # 放一个带标记的诱饵元信息文件，确认它确实读不到
    decoy = settings.data_dir / ".meta.decoy.json"
    decoy.write_text('{"token": "DECOY-TOKEN-MARKER"}', encoding="utf-8")

    try:
        # 页面目录是 DATA_DIR/pages/<cat>/<slug>，三层 .. 正好落到数据目录根，
        # 也就是存放 .meta.*.json（含 per-file 凭据）的那一层
        data_dir_escape = "../../../.meta.decoy.json"
        assert (
            pages_service.page_dir(CATEGORY, "guarded") / data_dir_escape
        ).resolve() == decoy.resolve(), "用例本身要确认这个路径确实指向诱饵文件"

        for attempt in (
            data_dir_escape,
            "../../../../.meta.decoy.json",
            "/etc/passwd",
        ):
            with pytest.raises(HTTPException) as excinfo:
                asyncio.run(page_resource(category=CATEGORY, slug="guarded", resource_path=attempt))
            assert excinfo.value.status_code == 404, attempt

        # 真实 HTTP：百分号编码的 ..%2F 会作为路径段送到服务端
        response = client.get(f"/pages/{CATEGORY}/guarded/..%2F..%2F..%2F.meta.decoy.json")
        assert response.status_code == 404
        assert "DECOY-TOKEN-MARKER" not in response.text
    finally:
        decoy.unlink(missing_ok=True)


def test_cross_page_resource_is_not_reachable():
    """页面 A 不能经上跳路径读到页面 B 的内容"""
    publish("page-a", html="<h1>A</h1>")
    publish("page-b", html="<h1>PAGE-B-SECRET</h1>")

    with pytest.raises(HTTPException) as excinfo:
        asyncio.run(
            page_resource(category=CATEGORY, slug="page-a", resource_path="../page-b/index.html")
        )
    assert excinfo.value.status_code == 404


# ---------------------------------------------------------------- 一致性与回滚


def test_publish_rejected_when_disk_has_unregistered_page():
    """落盘存在但事实源未登记时，发布被拒"""
    publish("consistent-page")
    orphan = pages_service.page_dir(CATEGORY, "orphan-page")
    orphan.mkdir(parents=True, exist_ok=True)
    (orphan / "index.html").write_text("<h1>orphan</h1>", encoding="utf-8")

    try:
        response = publish("another-page")
        assert response.status_code == 400
        assert "未登记" in response.json()["detail"]
    finally:
        import shutil

        shutil.rmtree(orphan, ignore_errors=True)


def test_publish_rejected_when_registered_page_missing_on_disk():
    """事实源登记但落盘不存在时，发布被拒"""
    publish("vanishing-page")
    entry = pages_service.page_entry(CATEGORY, "vanishing-page")
    content = entry.read_text(encoding="utf-8")
    entry.unlink()

    try:
        response = publish("yet-another-page")
        assert response.status_code == 400
        assert "落盘不存在" in response.json()["detail"]
    finally:
        entry.write_text(content, encoding="utf-8")


def test_failed_replace_keeps_previous_content(monkeypatch):
    """替换已有页面失败时，公开链接仍可访问且内容为发布前版本"""

    def boom(*args, **kwargs):
        raise PageError("注入的验活失败")

    publish("rollback-page", title="原版", html="<h1>original</h1>")
    monkeypatch.setattr(pages_service, "_verify", boom)
    response = publish("rollback-page", title="新版", html="<h1>replacement</h1>")
    assert response.status_code == 400
    monkeypatch.undo()

    page = client.get(f"/pages/{CATEGORY}/rollback-page/")
    assert page.status_code == 200
    assert "original" in page.text

    registry = pages_service.load_registry()
    entries = [
        p
        for c in registry["categories"]
        for p in c["pages"]
        if p["path"] == f"{CATEGORY}/rollback-page/"
    ]
    assert len(entries) == 1
    assert entries[0]["title"] == "原版"


def test_publish_fails_when_self_check_cannot_see_page(monkeypatch):
    """索引页呈现不出该页面时，发布失败且不留半成品"""
    monkeypatch.setattr(
        "transit.services.pages_service.render_index_page", lambda registry: "<html>空</html>"
    )

    response = publish("invisible-page")
    assert response.status_code == 400
    assert "验活失败" in response.json()["detail"]

    assert not pages_service.page_entry(CATEGORY, "invisible-page").is_file()


# ---------------------------------------------------------------- 公开浏览与前缀


def test_index_and_category_pages_are_public():
    """索引页与分类页不需凭据，且呈现页面标题与路径"""
    publish("public-page", title="公开页面标题")

    for path in ("/pages/", f"/pages/{CATEGORY}/"):
        response = client.get(path)
        assert response.status_code == 200, path
        assert response.headers["x-content-type-options"] == "nosniff", path
        assert "公开页面标题" in response.text, path
        assert f"{CATEGORY}/public-page/" in response.text, path


def test_unpublished_paths_return_404():
    """未发布的页面与不存在的分类返回 404"""
    assert client.get(f"/pages/{CATEGORY}/never-published/").status_code == 404
    assert client.get("/pages/no-such-category/").status_code == 404


def test_category_without_trailing_slash_redirects():
    """无尾斜杠的分类路径重定向到带尾斜杠版本"""
    response = client.get(f"/pages/{CATEGORY}", follow_redirects=False)
    assert response.status_code == 307
    assert response.headers["location"].endswith(f"/pages/{CATEGORY}/")


def test_learn_prefix_is_gone():
    """旧的 learn 前缀不再由页面托管响应（落到文件路由的 PUT 捕获上即为 405）"""
    response = client.get("/learn/")
    assert response.status_code in (404, 405)
    assert "页面站" not in response.text


def test_pages_paths_are_not_swallowed_by_file_routes():
    """页面路径命中自己的路由，而非被按编码文件名下载的变量路由吃掉"""
    publish("routed-page", html="<h1>路由验证正文</h1>")

    category_page = client.get(f"/pages/{CATEGORY}/")
    assert category_page.status_code == 200
    assert category_page.headers["content-type"].startswith("text/html")

    entry = client.get(f"/pages/{CATEGORY}/routed-page/")
    assert entry.status_code == 200
    assert "路由验证正文" in entry.text


# ---------------------------------------------------------------- 受保护页面


def test_publish_protected_page():
    """受保护页返回 /protect 链接；公开路径 404；凭据路径可读；不进公开索引"""
    response = publish("secret-page", title="机密页", html="<h1>机密正文</h1>", protected="true")
    assert response.status_code == 200
    body = response.json()
    assert "/protect/" in body["url"]
    assert "token" in body

    assert client.get(f"/pages/{CATEGORY}/secret-page/").status_code == 404

    from urllib.parse import urlparse

    protect_path = urlparse(body["url"]).path
    entry = client.get(protect_path)
    assert entry.status_code == 200
    assert "机密正文" in entry.text

    index = client.get("/pages/")
    assert index.status_code == 200
    assert "机密页" not in index.text


def test_publish_protected_bundle_serves_relative_assets():
    """受保护多文件：一个 token 罩住入口与相对静态资源；公开路径不可绕过"""
    from urllib.parse import urlparse

    response = publish_bundle(
        "secret-bundle",
        {
            "index.html": (
                b'<html><link rel="stylesheet" href="./style.css">'
                b"<h1>secret-bundle</h1></html>"
            ),
            "style.css": b"body{color:navy}",
            "assets/logo.svg": b"<svg></svg>",
        },
        protected="true",
        title="secret-bundle-page",
    )
    assert response.status_code == 200
    body = response.json()
    base = urlparse(body["url"]).path.rstrip("/") + "/"

    assert client.get(f"/pages/{CATEGORY}/secret-bundle/").status_code == 404
    assert client.get(f"/pages/{CATEGORY}/secret-bundle/style.css").status_code == 404

    entry = client.get(base)
    assert entry.status_code == 200
    assert "secret-bundle" in entry.text

    style = client.get(base + "style.css")
    assert style.status_code == 200
    assert style.content == b"body{color:navy}"

    logo = client.get(base + "assets/logo.svg")
    assert logo.status_code == 200
    assert logo.content == b"<svg></svg>"

    # 错 token 不能读
    assert client.get(f"/protect/not-the-token/{CATEGORY}/secret-bundle/").status_code == 404
    assert client.get(f"/protect/not-the-token/{CATEGORY}/secret-bundle/style.css").status_code == 404


def test_publish_path_protect_infers_protected():
    """只填 path=/protect 时推算受保护"""
    response = publish("via-path", html="<h1>x</h1>", path="/protect")
    assert response.status_code == 200
    assert "/protect/" in response.json()["url"]


def test_publish_path_protected_mismatch():
    """path=/pages 与 protected=true 不一致时 400"""
    response = publish("mismatch", html="<h1>x</h1>", path="/pages", protected="true")
    assert response.status_code == 400
