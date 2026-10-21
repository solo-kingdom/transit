"""
基本功能测试
"""

import pytest
from fastapi.testclient import TestClient
from transit.main import app
from transit.services.file_service import file_service


client = TestClient(app)


def test_root_zh():
    """根路径默认渲染中文产品说明页"""
    response = client.get("/")
    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/html")
    body = response.text
    assert "文件" in body
    assert "Agent Skill" in body
    for url in ("exploring.fun", "wii.pub", "solo.wii.pub", "dove.wii.pub"):
        assert url in body


def test_root_en():
    """根路径带 lang=en 时渲染英文版"""
    response = client.get("/?lang=en")
    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/html")
    body = response.text
    assert '<html lang="en">' in body
    assert "hosted by transit" in body
    for url in ("exploring.fun", "wii.pub", "solo.wii.pub", "dove.wii.pub"):
        assert url in body


def test_root_falls_back_to_zh():
    """未知语言回落到中文"""
    response = client.get("/?lang=fr")
    assert response.status_code == 200
    assert '<html lang="zh-CN">' in response.text


def test_health():
    """测试健康检查"""
    response = client.get("/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "healthy"


def test_upload_and_download_file():
    """测试文件上传和下载"""
    # 上传文件
    file_content = b"Test file content"
    files = {"file": ("test.txt", file_content, "text/plain")}
    response = client.post("/", files=files)

    assert response.status_code == 200
    data = response.json()
    assert "download_url" in data  # 仅检查完整 URL

    # 下载文件
    download_url = data["download_url"]
    # 去掉 host 部分，转成相对路径以便通过 TestClient 访问
    path = download_url.split("://", 1)[-1]
    path = path[path.find("/") :]
    response = client.get(path)

    assert response.status_code == 200
    assert response.content == file_content


def test_upload_with_put():
    """测试使用 PUT 方法上传文件"""
    file_content = b"Test file content via PUT"
    response = client.put("/", content=file_content)

    assert response.status_code == 200
    data = response.json()
    assert "download_url" in data  # 仅检查完整 URL

    # 下载文件
    download_url = data["download_url"]
    path = download_url.split("://", 1)[-1]
    path = path[path.find("/") :]
    response = client.get(path)

    assert response.status_code == 200
    assert response.content == file_content


def test_download_nonexistent_file():
    """测试下载不存在的文件"""
    response = client.get("/nonexistent-file/nonexistent.txt")
    assert response.status_code == 404


def test_get_file_meta():
    """测试获取文件元信息"""
    # 先上传文件
    file_content = b"Test file for meta"
    files = {"file": ("meta_test.txt", file_content, "text/plain")}
    upload_response = client.post("/", files=files)

    assert upload_response.status_code == 200
    upload_data = upload_response.json()
    download_url = upload_data["download_url"]

    # 下载链接只携带访问凭据，不再暴露编码文件名；
    # 元信息路由按编码文件名定位，故用凭据反查
    token = download_url.split("/protect/", 1)[1].split("/", 1)[0]
    encoded = file_service.find_by_token(token)
    assert encoded is not None
    original = "meta_test.txt"

    # 获取元信息
    meta_response = client.get(f"/{encoded}/{original}/meta")

    assert meta_response.status_code == 200
    meta_data = meta_response.json()
    assert "message" in meta_data
    assert "meta" in meta_data

    # 验证元信息内容
    meta = meta_data["meta"]
    assert meta["encoded_filename"] == encoded
    assert meta["original_filename"] == "meta_test.txt"
    assert meta["file_size"] == len(file_content)
    assert "upload_time" in meta
    assert "remote_address" in meta


def test_get_meta_nonexistent_file():
    """测试获取不存在文件的元信息"""
    response = client.get("/nonexistent-file/nonexistent.txt/meta")
    assert response.status_code == 404


def test_download_url_format():
    """测试下载 URL 格式"""
    file_content = b"Test URL format"
    files = {"file": ("url_test.txt", file_content, "text/plain")}
    response = client.post("/", files=files)

    assert response.status_code == 200
    data = response.json()

    # 检查 download_url 是否包含协议和 host
    download_url = data["download_url"]
    assert download_url.startswith("http://")
