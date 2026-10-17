"""
文件访问测试

覆盖 per-file 访问凭据、按内容类型分流、分段请求与元信息脱敏。
"""

import json
from datetime import datetime

from fastapi.testclient import TestClient

from transit.config import settings
from transit.content import detect_content_type, is_inline
from transit.main import app
from transit.services.file_service import file_service

client = TestClient(app)


def upload(filename: str, content: bytes, declared: str = "application/octet-stream") -> dict:
    """上传一个文件并返回响应体"""
    response = client.post("/", files={"file": (filename, content, declared)})
    assert response.status_code == 200
    return response.json()


def path_of(url: str) -> str:
    """把完整链接转成相对路径，便于 TestClient 访问"""
    path = url.split("://", 1)[-1]
    return path[path.find("/") :]


# ---------------------------------------------------------------- 内容类型判定


def test_detect_content_type_prefers_extension_over_declared():
    """扩展名优先：上传方声明的类型不覆盖扩展名推导结果"""
    assert detect_content_type("report.txt", "text/html") == "text/plain"
    assert detect_content_type("page.html", "text/plain") == "text/html"


def test_detect_content_type_falls_back_to_declared():
    """扩展名推导不出时才采用声明的类型"""
    assert detect_content_type("noext", "application/x-custom") == "application/x-custom"
    # 声明的类型是通用二进制时视为未指定
    assert detect_content_type("noext", "application/octet-stream") == "application/octet-stream"


def test_is_inline_whitelist():
    """内联白名单：文本、图片（矢量图除外）、音视频、PDF 内联；其余下载"""
    for content_type in (
        "text/plain",
        "text/html",
        "image/png",
        "video/mp4",
        "audio/mpeg",
        "application/pdf",
    ):
        assert is_inline(content_type), content_type

    for content_type in ("image/svg+xml", "application/zip", "application/octet-stream"):
        assert not is_inline(content_type), content_type


# ---------------------------------------------------------------- 上传响应


def test_upload_returns_self_sufficient_link():
    """上传返回的链接自带凭据，直接 GET 即可取到文件"""
    content = b"hello self sufficient link"
    data = upload("note.txt", content)

    assert "/f/" in data["download_url"]

    response = client.get(path_of(data["download_url"]))
    assert response.status_code == 200
    assert response.content == content


def test_declared_type_does_not_override_extension():
    """上传方声明 text/html 也不能让 .txt 变成 HTML"""
    data = upload("plain.txt", b"<script>alert(1)</script>", declared="text/html")

    response = client.get(path_of(data["download_url"]))
    assert response.headers["content-type"].startswith("text/plain")
    assert response.headers["content-disposition"].startswith("inline")


# ---------------------------------------------------------------- 访问凭据


def test_access_with_unknown_token_returns_404():
    """凭据不匹配返回 404"""
    response = client.get("/f/not-a-real-token/whatever.txt")
    assert response.status_code == 404


def test_access_link_works_without_authorization_when_auth_enabled(monkeypatch):
    """服务启用认证时，仅凭链接仍可取到文件"""
    monkeypatch.setattr(settings, "auth_enabled", True)
    monkeypatch.setattr(settings, "read_tokens", "read-secret")
    monkeypatch.setattr(settings, "write_tokens", "write-secret")

    content = b"self sufficient under auth"
    response = client.post(
        "/",
        files={"file": ("auth.txt", content, "text/plain")},
        headers={"Authorization": "Bearer write-secret"},
    )
    assert response.status_code == 200

    # 不带任何认证头
    response = client.get(path_of(response.json()["download_url"]))
    assert response.status_code == 200
    assert response.content == content


def test_upload_requires_write_token_when_auth_enabled(monkeypatch):
    """服务启用认证时，缺写凭据与写凭据错误均被拒"""
    monkeypatch.setattr(settings, "auth_enabled", True)
    monkeypatch.setattr(settings, "write_tokens", "write-secret")

    missing = client.post("/", files={"file": ("a.txt", b"x", "text/plain")})
    assert missing.status_code == 401

    wrong = client.post(
        "/",
        files={"file": ("a.txt", b"x", "text/plain")},
        headers={"Authorization": "Bearer nope"},
    )
    assert wrong.status_code == 401


# ---------------------------------------------------------------- 类型分流


def test_content_disposition_per_type():
    """六类内容的分流与响应头"""
    cases = [
        ("a.html", "text/html", "inline"),
        ("a.png", "image/png", "inline"),
        ("a.mp4", "video/mp4", "inline"),
        ("a.pdf", "application/pdf", "inline"),
        ("a.svg", "image/svg+xml", "attachment"),
        ("a.zip", "application/zip", "attachment"),
    ]

    for filename, expected_type, expected_disposition in cases:
        data = upload(filename, b"payload")
        response = client.get(path_of(data["download_url"]))

        assert response.status_code == 200, filename
        assert response.headers["content-type"].startswith(expected_type), filename
        assert response.headers["content-disposition"].startswith(expected_disposition), filename
        assert response.headers["x-content-type-options"] == "nosniff", filename


# ---------------------------------------------------------------- 分段请求


def test_range_requests_are_supported():
    """分段请求返回 206 与所请求的字节范围"""
    content = b"0123456789abcdef"
    data = upload("range.bin", content)

    full = client.get(path_of(data["download_url"]))
    assert full.status_code == 200
    assert full.headers["accept-ranges"] == "bytes"
    # 自定义响应头未被框架覆盖
    assert full.headers["content-disposition"].startswith("attachment")
    assert full.headers["x-content-type-options"] == "nosniff"

    partial = client.get(path_of(data["download_url"]), headers={"Range": "bytes=0-9"})
    assert partial.status_code == 206
    assert partial.headers["content-range"] == f"bytes 0-9/{len(content)}"
    assert partial.content == content[:10]


# ---------------------------------------------------------------- 元信息脱敏


def test_meta_response_hides_access_token():
    """元信息响应不暴露 per-file 凭据"""
    data = upload("secret.txt", b"payload")
    token = data["download_url"].split("/f/", 1)[1].split("/", 1)[0]
    encoded = file_service.find_by_token(token)

    response = client.get(f"/{encoded}/secret.txt/meta")
    assert response.status_code == 200

    meta = response.json()["meta"]
    assert "token" not in meta
    assert meta["original_filename"] == "secret.txt"
    assert meta["content_type"] == "text/plain"


# ---------------------------------------------------------------- 旧数据兼容


def test_legacy_meta_without_new_fields_is_readable(tmp_path):
    """变更前写入的元信息文件（无新字段）仍可解析"""
    encoded = "legacy-file.txt"
    legacy = {
        "encoded_filename": encoded,
        "original_filename": "legacy-file.txt",
        "upload_time": datetime.now().isoformat(),
        "remote_address": "127.0.0.1",
        "file_size": 3,
    }
    meta_path = file_service.get_meta_path(encoded)
    meta_path.write_text(json.dumps(legacy), encoding="utf-8")

    try:
        meta = file_service.get_meta(encoded)
        assert meta is not None
        assert meta.token == ""
        assert meta.content_type == ""
    finally:
        meta_path.unlink(missing_ok=True)


def test_token_reverse_lookup():
    """凭据反查：命中、未命中，且新上传立即可反查"""
    data = upload("lookup.txt", b"payload")
    token = data["download_url"].split("/f/", 1)[1].split("/", 1)[0]

    assert file_service.find_by_token(token) is not None
    assert file_service.find_by_token("no-such-token") is None
    assert file_service.find_by_token("") is None
