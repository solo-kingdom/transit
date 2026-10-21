"""
定位并读取仓内 Agent Skill 正文

落地页与 GET /skill.md 都读同一文件，避免文案双份漂移。
"""

from functools import lru_cache
from pathlib import Path
from typing import Optional

# 相对仓库根 / 镜像 /app 的约定路径
SKILL_REL = Path(".agents/skills/transit/SKILL.md")


def _candidates() -> list[Path]:
    """按优先级列出可能的 SKILL.md 路径"""
    paths: list[Path] = []

    # 1) 显式覆盖（测试或非常规布局）
    import os

    env = os.environ.get("TRANSIT_SKILL_PATH", "").strip()
    if env:
        paths.append(Path(env))

    # 2) 镜像约定：WORKDIR=/app
    paths.append(Path("/app") / SKILL_REL)

    # 3) 从本文件向上找仓库根（开发树：src/transit/skill_doc.py → 根）
    here = Path(__file__).resolve()
    for parent in here.parents:
        candidate = parent / SKILL_REL
        paths.append(candidate)
        if (parent / "pyproject.toml").is_file():
            break

    # 4) 当前工作目录（pytest / 本地 uvicorn）
    paths.append(Path.cwd() / SKILL_REL)

    return paths


def resolve_skill_path() -> Optional[Path]:
    """返回第一个存在的 SKILL.md；都没有则 None"""
    seen: set[Path] = set()
    for path in _candidates():
        try:
            resolved = path.resolve()
        except OSError:
            continue
        if resolved in seen:
            continue
        seen.add(resolved)
        if resolved.is_file():
            return resolved
    return None


@lru_cache(maxsize=1)
def load_skill_markdown() -> str:
    """
    读取 skill 正文

    进程内缓存；文件缺失时返回简短占位（开发未挂载 skill 时仍可起服务）。
    测试可通过 load_skill_markdown.cache_clear() 失效缓存。
    """
    path = resolve_skill_path()
    if path is None:
        return (
            "# transit skill\n\n"
            "SKILL.md not packaged with this build. "
            "See the transit repository: `.agents/skills/transit/SKILL.md`.\n"
        )
    return path.read_text(encoding="utf-8")
