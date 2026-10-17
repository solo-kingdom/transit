"""
学习内容托管测试

覆盖发布鉴权、事实源与落盘的双向校验、替换场景的回滚、公开浏览与无尾斜杠重定向。
"""

from fastapi.testclient import TestClient

from transit.config import settings
from transit.main import app
from transit.services.learn_service import LearnError, learn_service

client = TestClient(app)

CATEGORY = "test-cat"


def publish(slug: str, title: str = "示例专题", html: str = "<h1>正文</h1>", **overrides) -> dict:
    """构造并发出一次发布请求"""
    body = {
        "category": CATEGORY,
        "slug": slug,
        "title": title,
        "desc": "一句话摘要",
        "html": html,
        "tags": ["demo"],
        "date": "2026-10-17",
        # 分类已存在时该字段被忽略；首次发布时用它建分类
        "category_name": "测试分类",
    }
    body.update(overrides)
    return client.post("/learn/publish", json=body)


def orphan_dir(name: str = "orphan-topic"):
    """在落盘造一个未登记进事实源的专题目录"""
    target = learn_service.root / CATEGORY / name
    target.mkdir(parents=True, exist_ok=True)
    (target / "index.html").write_text("<h1>orphan</h1>", encoding="utf-8")
    return target


def cleanup_orphan(name: str = "orphan-topic"):
    import shutil

    shutil.rmtree(learn_service.root / CATEGORY / name, ignore_errors=True)


# ---------------------------------------------------------------- 发布鉴权


def test_publish_requires_write_token(monkeypatch):
    """缺写凭据与写凭据错误均被拒，且不产生落盘变更"""
    monkeypatch.setattr(settings, "auth_enabled", True)
    monkeypatch.setattr(settings, "write_tokens", "write-secret")

    def snapshot():
        if not learn_service.root.is_dir():
            return set()
        return {str(p.relative_to(learn_service.root)) for p in learn_service.root.rglob("*")}

    before = snapshot()

    missing = client.post(
        "/learn/publish",
        json={
            "category": CATEGORY,
            "slug": "denied",
            "title": "t",
            "desc": "d",
            "html": "<p>x</p>",
        },
    )
    assert missing.status_code == 401

    wrong = client.post(
        "/learn/publish",
        json={
            "category": CATEGORY,
            "slug": "denied",
            "title": "t",
            "desc": "d",
            "html": "<p>x</p>",
        },
        headers={"Authorization": "Bearer nope"},
    )
    assert wrong.status_code == 401

    assert snapshot() == before


# ---------------------------------------------------------------- 入参校验


def test_publish_rejects_non_kebab_case():
    """分类与专题标识必须是 kebab-case"""
    assert publish("Bad_Slug").status_code == 400
    assert publish("ok-slug", category="Bad_Cat").status_code == 400


def test_publish_rejects_empty_required_fields():
    """标题、摘要与正文都不能为空"""
    assert publish("empty-title", title="").status_code == 400
    assert publish("empty-desc", desc="").status_code == 400
    assert publish("empty-html", html="   ").status_code == 400


def test_publish_new_category_requires_display_name():
    """分类不存在且未提供显示名时报错"""
    response = publish("brand-new", category="brand-new-cat", category_name=None)
    assert response.status_code == 400
    assert "category_name" in response.json()["detail"]

    # 报错后不留下半成品
    assert not learn_service.topic_file("brand-new-cat", "brand-new").is_file()


# ---------------------------------------------------------------- 发布主流程


def test_publish_new_topic():
    """发布一篇新专题并登记进事实源"""
    response = publish("first-topic", title="第一篇")
    assert response.status_code == 200

    body = response.json()
    assert body["url"].endswith(f"/learn/{CATEGORY}/first-topic/")
    assert body["category_url"].endswith(f"/learn/{CATEGORY}/")

    registry = learn_service.load_registry()
    paths = [t["path"] for c in registry["categories"] for t in c["topics"]]
    assert f"{CATEGORY}/first-topic/" in paths
    assert learn_service.topic_file(CATEGORY, "first-topic").is_file()


def test_publish_creates_category_with_display_name():
    """分类不存在但提供了显示名时，分类被一并登记"""
    response = publish(
        "under-new-cat", category="fresh-cat", category_name="新分类", category_description="说明"
    )
    assert response.status_code == 200

    registry = learn_service.load_registry()
    category = next(c for c in registry["categories"] if c["slug"] == "fresh-cat")
    assert category["name"] == "新分类"
    assert category["description"] == "说明"


def test_replacing_topic_keeps_single_registry_entry():
    """对同一专题重复发布时事实源仍只有一条登记"""
    publish("repeat-topic", title="旧标题", html="<h1>v1</h1>")
    response = publish("repeat-topic", title="新标题", html="<h1>v2</h1>")
    assert response.status_code == 200

    registry = learn_service.load_registry()
    entries = [
        t
        for c in registry["categories"]
        for t in c["topics"]
        if t["path"] == f"{CATEGORY}/repeat-topic/"
    ]
    assert len(entries) == 1
    assert entries[0]["title"] == "新标题"
    assert b"v2" in client.get(f"/learn/{CATEGORY}/repeat-topic/").content


# ---------------------------------------------------------------- 一致性校验


def test_publish_rejected_when_disk_has_unregistered_topic():
    """落盘存在但事实源未登记时，发布被拒"""
    publish("consistent-topic")
    orphan_dir()

    try:
        response = publish("another-topic")
        assert response.status_code == 400
        assert "未登记" in response.json()["detail"]
    finally:
        cleanup_orphan()


def test_publish_rejected_when_registered_topic_missing_on_disk():
    """事实源登记但落盘不存在时，发布被拒"""
    publish("vanishing-topic")
    target = learn_service.topic_file(CATEGORY, "vanishing-topic")
    content = target.read_text(encoding="utf-8")
    target.unlink()

    try:
        response = publish("yet-another-topic")
        assert response.status_code == 400
        assert "落盘不存在" in response.json()["detail"]
    finally:
        target.write_text(content, encoding="utf-8")


# ---------------------------------------------------------------- 回滚


def test_failed_replace_keeps_previous_content(monkeypatch):
    """替换已有专题失败时，公开链接仍可访问且内容为发布前版本"""
    publish("rollback-topic", title="原版", html="<h1>original</h1>")

    def boom(*args, **kwargs):
        raise LearnError("注入的验活失败")

    monkeypatch.setattr(learn_service, "_verify", boom)
    response = publish("rollback-topic", title="新版", html="<h1>replacement</h1>")
    assert response.status_code == 400
    monkeypatch.undo()

    page = client.get(f"/learn/{CATEGORY}/rollback-topic/")
    assert page.status_code == 200
    assert b"original" in page.content

    registry = learn_service.load_registry()
    entries = [
        t
        for c in registry["categories"]
        for t in c["topics"]
        if t["path"] == f"{CATEGORY}/rollback-topic/"
    ]
    assert len(entries) == 1
    assert entries[0]["title"] == "原版"


def test_publish_fails_when_self_check_cannot_see_topic(monkeypatch):
    """索引页与分类页呈现不出该专题时，发布失败"""
    monkeypatch.setattr(
        "transit.services.learn_service.render_index_page", lambda registry: "<html>空</html>"
    )

    response = publish("invisible-topic")
    assert response.status_code == 400
    assert "验活失败" in response.json()["detail"]

    # 失败后不留半成品
    assert not learn_service.topic_file(CATEGORY, "invisible-topic").is_file()
    registry = learn_service.load_registry()
    paths = [t["path"] for c in registry["categories"] for t in c["topics"]]
    assert f"{CATEGORY}/invisible-topic/" not in paths


# ---------------------------------------------------------------- 公开浏览


def test_index_and_category_pages_are_public():
    """索引页与分类页不需凭据，且呈现专题标题与路径"""
    publish("public-topic", title="公开专题标题")

    for path in ("/learn/", f"/learn/{CATEGORY}/"):
        response = client.get(path)
        assert response.status_code == 200, path
        assert response.headers["x-content-type-options"] == "nosniff", path
        assert "公开专题标题" in response.text, path
        assert f"{CATEGORY}/public-topic/" in response.text, path


def test_topic_page_serves_published_html():
    """专题页返回发布时的 HTML"""
    publish("served-topic", html="<h1>已发布正文</h1>")

    response = client.get(f"/learn/{CATEGORY}/served-topic/")
    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/html")
    assert response.headers["x-content-type-options"] == "nosniff"
    assert "已发布正文" in response.text


def test_unpublished_paths_return_404():
    """未发布过的专题与不存在的分类返回 404"""
    assert client.get(f"/learn/{CATEGORY}/never-published/").status_code == 404
    assert client.get("/learn/no-such-category/").status_code == 404


def test_category_without_trailing_slash_redirects():
    """无尾斜杠的分类路径重定向到带尾斜杠版本"""
    response = client.get(f"/learn/{CATEGORY}", follow_redirects=False)
    assert response.status_code == 307
    assert response.headers["location"].endswith(f"/learn/{CATEGORY}/")


def test_learn_paths_are_not_swallowed_by_file_routes():
    """学习内容路径命中自己的路由，而非被按编码文件名下载的变量路由吃掉"""
    publish("routed-topic", html="<h1>路由验证正文</h1>")

    category_page = client.get(f"/learn/{CATEGORY}/")
    assert category_page.status_code == 200
    assert category_page.headers["content-type"].startswith("text/html")

    topic_page = client.get(f"/learn/{CATEGORY}/routed-topic/")
    assert topic_page.status_code == 200
    assert "路由验证正文" in topic_page.text
