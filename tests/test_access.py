"""
文件访问测试

覆盖 per-file 访问凭据、按内容类型分流、分段请求与元信息脱敏。
"""

import json
from datetime import datetime, timedelta

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
    """上传默认走 /protect，链接自带凭据，直接 GET 即可取到文件"""
    content = b"hello self sufficient link"
    data = upload("note.txt", content)

    assert "/protect/" in data["download_url"]

    response = client.get(path_of(data["download_url"]))
    assert response.status_code == 200
    assert response.content == content


def test_upload_default_is_protect():
    """path 与 protected 都省略时默认 /protect"""
    data = upload("default.txt", b"default protect")
    assert "/protect/" in data["download_url"]
    assert "/public/" not in data["download_url"]


def test_upload_public_via_path():
    """只填 path=/public 时走公开链接，无需 token 段"""
    response = client.post(
        "/",
        files={"file": ("open.txt", b"public content", "text/plain")},
        data={"path": "/public"},
    )
    assert response.status_code == 200
    data = response.json()
    assert "/public/" in data["download_url"]
    assert client.get(path_of(data["download_url"])).content == b"public content"


def test_upload_public_via_protected_false():
    """只填 protected=false 时推算 /public"""
    response = client.post(
        "/",
        files={"file": ("open2.txt", b"via flag", "text/plain")},
        data={"protected": "false"},
    )
    assert response.status_code == 200
    assert "/public/" in response.json()["download_url"]


def test_upload_path_protected_mismatch_returns_400():
    """path 与 protected 不一致时 400"""
    response = client.post(
        "/",
        files={"file": ("bad.txt", b"x", "text/plain")},
        data={"path": "/public", "protected": "true"},
    )
    assert response.status_code == 400


def test_public_file_not_readable_via_encoded_guess_when_protected():
    """受保护文件不能借 /public/{encoded}/ 绕过"""
    data = upload("secret.txt", b"nope")
    token = data["download_url"].split("/protect/", 1)[1].split("/", 1)[0]
    encoded = file_service.find_by_token(token)
    assert encoded
    assert client.get(f"/public/{encoded}/secret.txt").status_code == 404


def test_legacy_f_alias_still_works():
    """旧 /f/{token}/... 链接仍可用"""
    data = upload("legacy.txt", b"via f alias")
    protect_path = path_of(data["download_url"])
    assert "/protect/" in protect_path
    legacy_path = "/f/" + protect_path.split("/protect/", 1)[1]
    response = client.get(legacy_path)
    assert response.status_code == 200
    assert response.content == b"via f alias"


def test_declared_type_does_not_override_extension():
    """上传方声明 text/html 也不能让 .txt 变成 HTML"""
    data = upload("plain.txt", b"<script>alert(1)</script>", declared="text/html")

    response = client.get(path_of(data["download_url"]))
    assert response.headers["content-type"].startswith("text/plain")
    assert response.headers["content-disposition"].startswith("inline")


# ---------------------------------------------------------------- 访问凭据


def test_access_with_unknown_token_returns_404():
    """凭据不匹配返回 404"""
    response = client.get("/protect/not-a-real-token/whatever.txt")
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


# ---------------------------------------------------------------- 凭据来源


def test_upload_accepts_x_auth_token_header(monkeypatch):
    """开启认证后，X-Auth-Token 头与 Authorization 头等价"""
    monkeypatch.setattr(settings, "auth_enabled", True)
    monkeypatch.setattr(settings, "write_tokens", "write-secret")

    response = client.post(
        "/",
        files={"file": ("x.txt", b"via-x-header", "text/plain")},
        headers={"X-Auth-Token": "write-secret"},
    )
    assert response.status_code == 200


def test_upload_accepts_form_token(monkeypatch):
    """开启认证后，表单字段 token 可作为凭据"""
    monkeypatch.setattr(settings, "auth_enabled", True)
    monkeypatch.setattr(settings, "write_tokens", "write-secret")

    response = client.post(
        "/",
        files={"file": ("form.txt", b"via-form", "text/plain")},
        data={"token": "write-secret"},
    )
    assert response.status_code == 200


def test_upload_accepts_query_token(monkeypatch):
    """开启认证后，query 参数 token 可作为凭据"""
    monkeypatch.setattr(settings, "auth_enabled", True)
    monkeypatch.setattr(settings, "write_tokens", "write-secret")

    response = client.post(
        "/?token=write-secret",
        files={"file": ("query.txt", b"via-query", "text/plain")},
    )
    assert response.status_code == 200


def test_token_precedence_header_over_form(monkeypatch):
    """Authorization 头优先于表单 token：头里错、表单里对，仍按头判定为错"""
    monkeypatch.setattr(settings, "auth_enabled", True)
    monkeypatch.setattr(settings, "write_tokens", "write-secret")

    response = client.post(
        "/",
        files={"file": ("p.txt", b"x", "text/plain")},
        data={"token": "write-secret"},
        headers={"Authorization": "Bearer nope"},
    )
    assert response.status_code == 401


def test_wrong_token_rejected_from_any_source(monkeypatch):
    """任一来源给出错误 token 都被拒"""
    monkeypatch.setattr(settings, "auth_enabled", True)
    monkeypatch.setattr(settings, "write_tokens", "write-secret")

    for kwargs in (
        {"headers": {"X-Auth-Token": "nope"}},
        {"data": {"token": "nope"}},
    ):
        response = client.post(
            "/", files={"file": ("w.txt", b"x", "text/plain")}, **kwargs
        )
        assert response.status_code == 401


def test_put_bare_body_not_consumed_by_auth(monkeypatch):
    """
    裸 body PUT 的请求体不能被鉴权提前消费

    回归：token 来自 query 时，若鉴权逻辑按 content-type 去读表单，会把 body 流读空，
    上传端随后拿到 "Stream consumed" 报 500。curl --data-binary 默认发
    application/x-www-form-urlencoded，是触发该问题的真实路径。
    """
    monkeypatch.setattr(settings, "auth_enabled", True)
    monkeypatch.setattr(settings, "write_tokens", "write-secret")

    response = client.put(
        "/put-test.txt?token=write-secret",
        content=b"raw-bytes",
        headers={"Content-Type": "application/x-www-form-urlencoded"},
    )
    assert response.status_code == 200


def test_put_body_intact_when_token_in_header(monkeypatch):
    """PUT 用头传 token 时 body 同样完整可读"""
    monkeypatch.setattr(settings, "auth_enabled", True)
    monkeypatch.setattr(settings, "write_tokens", "write-secret")

    response = client.put(
        "/put-hdr.txt",
        content=b"body-via-header",
        headers={"X-Auth-Token": "write-secret", "Content-Type": "application/octet-stream"},
    )
    assert response.status_code == 200


def test_publish_page_accepts_form_token(monkeypatch):
    """页面发布接口同样支持表单 token（原本就是 multipart 表单）"""
    monkeypatch.setattr(settings, "auth_enabled", True)
    monkeypatch.setattr(settings, "write_tokens", "write-secret")

    response = client.post(
        "/pages/publish",
        data={
            "category": "auth-cat",
            "slug": "auth-page",
            "title": "鉴权页",
            "desc": "摘要",
            "html": "<h1>hi</h1>",
            "category_name": "鉴权分类",
            "token": "write-secret",
        },
    )
    assert response.status_code == 200


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
    token = data["download_url"].split("/protect/", 1)[1].split("/", 1)[0]
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
    token = data["download_url"].split("/protect/", 1)[1].split("/", 1)[0]

    assert file_service.find_by_token(token) is not None
    assert file_service.find_by_token("no-such-token") is None
    assert file_service.find_by_token("") is None


# ---------------------------------------------------------------- 读取路径收口


def test_meta_file_cannot_be_downloaded_as_a_file():
    """元信息文件带 per-file 凭据，不得作为普通文件被取走"""
    upload("secret.txt", b"payload")

    meta_files = sorted(file_service.data_dir.glob(".meta.*.json"))
    assert meta_files, "上传后应产生元信息文件"
    meta_name = meta_files[-1].name

    response = client.get(f"/{meta_name}/anything.txt")
    assert response.status_code == 404
    assert "token" not in response.text


def test_encoded_name_outside_data_dir_is_rejected():
    """越出数据目录或不是单个路径段的编码名一律按不存在处理"""
    for name in ("../outside.txt", "../../etc/passwd", "/etc/passwd", "sub/dir.txt", "", ".", ".."):
        assert file_service.get_file_path(name) is None, name
        assert file_service.read_file(name) is None, name
        assert file_service.file_exists(name) is False, name
        assert file_service.get_meta(name) is None, name


def test_meta_prefixed_name_is_rejected():
    """编码名以 .meta. 开头时直接拒绝"""
    assert file_service.get_file_path(".meta.something.json") is None


def test_symlink_escaping_data_dir_is_rejected(tmp_path):
    """数据目录内指向外部的符号链接不可读"""
    outside = tmp_path / "outside.txt"
    outside.write_text("outside the data dir", encoding="utf-8")

    link = file_service.data_dir / "escape-link.txt"
    link.unlink(missing_ok=True)
    link.symlink_to(outside)

    try:
        assert file_service.get_file_path("escape-link.txt") is None
        assert client.get("/escape-link.txt/whatever.txt").status_code == 404
    finally:
        link.unlink(missing_ok=True)


def test_legacy_paths_still_work_and_meta_stays_unreachable():
    """正常链路不回归：按编码名下载与查元信息仍可用，元信息文件本身取不走"""
    data = upload("payload.txt", b"payload")
    token = data["download_url"].split("/protect/", 1)[1].split("/", 1)[0]
    encoded = file_service.find_by_token(token)
    assert encoded is not None

    assert client.get(f"/{encoded}/payload.txt").status_code == 200
    assert client.get(f"/{encoded}/payload.txt/meta").status_code == 200

    meta_name = f".meta.{encoded}.json"
    response = client.get(f"/{meta_name}/payload.txt")
    assert response.status_code == 404
    assert "token" not in response.text


# ---------------------------------------------------------------- 有效期


def _expire_now(data: dict) -> str:
    """把已上传文件的过期时间改到过去，返回其编码文件名"""
    token = data["download_url"].split("/protect/", 1)[1].split("/", 1)[0]
    encoded = file_service.find_by_token(token)
    assert encoded is not None

    meta_path = file_service.get_meta_path(encoded)
    payload = json.loads(meta_path.read_text(encoding="utf-8"))
    payload["expires_at"] = (datetime.now() - timedelta(seconds=1)).isoformat()
    meta_path.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")
    return encoded


def test_upload_without_expiry_never_expires():
    """默认不设有效期：响应不含 expires_at，元信息里也为 None"""
    response = client.post("/", files={"file": ("keep.txt", b"keep", "text/plain")})
    assert response.status_code == 200
    assert "expires_at" not in response.json()

    token = response.json()["download_url"].split("/protect/", 1)[1].split("/", 1)[0]
    encoded = file_service.find_by_token(token)
    meta = file_service.get_meta(encoded)
    assert meta is not None
    assert meta.expires_at is None
    assert not file_service.is_expired(meta)


def test_upload_with_expiry_records_expires_at():
    """表单设置 expires_in 后，响应与元信息都带上过期时间"""
    response = client.post(
        "/",
        files={"file": ("ttl.txt", b"ttl", "text/plain")},
        data={"expires_in": "3600"},
    )
    assert response.status_code == 200
    body = response.json()
    assert "expires_at" in body

    token = body["download_url"].split("/protect/", 1)[1].split("/", 1)[0]
    meta = file_service.get_meta(file_service.find_by_token(token))
    assert meta is not None
    assert meta.expires_at is not None
    # 大约是一小时后（允许几秒误差）
    remaining = (meta.expires_at - datetime.now()).total_seconds()
    assert 3590 < remaining <= 3600


def test_put_upload_accepts_expires_in_query():
    """PUT 裸 body 上传通过 query 设置有效期"""
    response = client.put("/ttl-put.txt?expires_in=60", content=b"raw")
    assert response.status_code == 200
    assert "expires_at" in response.json()


def test_invalid_expires_in_is_rejected():
    """非正整数有效期返回 400，且不能悄悄退回不过期"""
    for bad in ("0", "-5", "abc", "1.5"):
        response = client.post(
            "/",
            files={"file": ("bad.txt", b"x", "text/plain")},
            data={"expires_in": bad},
        )
        assert response.status_code == 400, bad
        assert "expires_in" in response.text


def test_expired_file_returns_410_on_access_link():
    """过期后自足链接返回 410，而不是 404"""
    data = upload("gone.txt", b"bye")
    path = path_of(data["download_url"])
    assert client.get(path).status_code == 200

    encoded = _expire_now(data)
    assert client.get(path).status_code == 410
    assert encoded


def test_expired_file_returns_410_on_legacy_paths():
    """过期后按编码名下载与查元信息都返回 410"""
    data = upload("legacy-gone.txt", b"bye")
    encoded = _expire_now(data)

    assert client.get(f"/{encoded}/legacy-gone.txt").status_code == 410
    assert client.get(f"/{encoded}/legacy-gone.txt/meta").status_code == 410


def test_expiry_does_not_affect_other_files():
    """过期判定只看自己的元信息，不影响其他文件"""
    old = upload("one.txt", b"one")
    fresh = upload("two.txt", b"two")
    _expire_now(old)

    assert client.get(path_of(old["download_url"])).status_code == 410
    assert client.get(path_of(fresh["download_url"])).status_code == 200
