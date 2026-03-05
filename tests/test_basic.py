"""
基本功能测试
"""

import pytest
from fastapi.testclient import TestClient
from transit.main import app


client = TestClient(app)


def test_root():
    """测试根路径"""
    response = client.get("/")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "running"
    assert "service" in data
    assert "version" in data


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
    response = client.post("/testuser", files=files)

    assert response.status_code == 200
    data = response.json()
    assert "download_path" in data
    assert "filename" in data

    # 下载文件
    download_path = data["download_path"]
    response = client.get(download_path)

    assert response.status_code == 200
    assert response.content == file_content


def test_upload_with_put():
    """测试使用 PUT 方法上传文件"""
    file_content = b"Test file content via PUT"
    response = client.put("/testuser2", content=file_content)

    assert response.status_code == 200
    data = response.json()
    assert "download_path" in data
    assert "filename" in data

    # 下载文件
    download_path = data["download_path"]
    response = client.get(download_path)

    assert response.status_code == 200
    assert response.content == file_content


def test_download_nonexistent_file():
    """测试下载不存在的文件"""
    response = client.get("/nonexistent/user/file.txt")
    assert response.status_code == 404
