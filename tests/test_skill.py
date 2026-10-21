"""Agent Skill 嵌入与 /skill.md 同源"""

from pathlib import Path

from fastapi.testclient import TestClient

from transit.main import app
from transit.skill_doc import load_skill_markdown, resolve_skill_path

client = TestClient(app)

REPO_SKILL = (
    Path(__file__).resolve().parents[1] / ".agents" / "skills" / "transit" / "SKILL.md"
)


def setup_function():
    load_skill_markdown.cache_clear()


def test_resolve_skill_path_finds_repo_file():
    path = resolve_skill_path()
    assert path is not None
    assert path.resolve() == REPO_SKILL.resolve()


def test_skill_md_endpoint_returns_repo_file():
    response = client.get("/skill.md")
    assert response.status_code == 200
    assert "text/markdown" in response.headers["content-type"]
    assert response.text == REPO_SKILL.read_text(encoding="utf-8")
    assert "name: transit" in response.text
    assert "多实例台账" in response.text


def test_skill_alias_endpoint():
    assert client.get("/skill").text == client.get("/skill.md").text


def test_landing_embeds_skill_file():
    """根路径嵌入的是文件内容，不是另写的摘要"""
    body = client.get("/").text
    skill = REPO_SKILL.read_text(encoding="utf-8")
    # HTML 转义后仍应保留 skill 标题与关键片段
    assert "Agent Skill" in body
    assert "/skill.md" in body
    assert "transit — 文件中转与页面托管" in body or "文件中转与页面托管" in body
    assert "GET {base}/skill.md" in body or "skill.md" in body
    # 与文件同源：取一段不易被模板写死的原文
    assert "instances.example.md" in skill
    assert "instances.example.md" in body
