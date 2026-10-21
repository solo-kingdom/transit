"""
访问命名空间决策

上传 / 发布时可同时给出「访问路径」与「是否受保护」；二者皆可选，按下列规则收敛：

- 都省略：文件默认 /protect；页面默认 /pages
- 只给 path：由前缀推算 protected
- 只给 protected：推算 path
- 都给：校验一致，否则 400

公开前缀：/public（文件）、/pages（页面）
受保护前缀：/protect
"""

from dataclasses import dataclass
from typing import Literal, Optional

from fastapi import HTTPException

Kind = Literal["file", "page"]

PUBLIC_FILE = "/public"
PROTECT = "/protect"
PUBLIC_PAGE = "/pages"


@dataclass(frozen=True)
class AccessIntent:
    """一次上传/发布收敛后的访问意图"""

    # 命名空间前缀：/public | /protect | /pages
    namespace: str
    # 是否需要资源级 token 才能读
    protected: bool


def _normalize_path(raw: Optional[str]) -> Optional[str]:
    """规范化访问路径：去空白、补前导斜杠、去尾斜杠（根前缀除外）"""
    if raw is None:
        return None
    text = str(raw).strip()
    if not text:
        return None
    if not text.startswith("/"):
        text = "/" + text
    # 允许只写前缀，或前缀加后续段；统一去掉末尾 /
    if len(text) > 1:
        text = text.rstrip("/")
    return text


def _namespace_of(path: str) -> Optional[str]:
    """从完整 path 取出已知命名空间前缀"""
    for prefix in (PROTECT, PUBLIC_FILE, PUBLIC_PAGE):
        if path == prefix or path.startswith(prefix + "/"):
            return prefix
    return None


def _protected_of_namespace(namespace: str) -> bool:
    return namespace == PROTECT


def _allowed_namespaces(kind: Kind) -> set[str]:
    if kind == "file":
        return {PUBLIC_FILE, PROTECT}
    return {PUBLIC_PAGE, PROTECT}


def _default_intent(kind: Kind) -> AccessIntent:
    if kind == "file":
        return AccessIntent(namespace=PROTECT, protected=True)
    return AccessIntent(namespace=PUBLIC_PAGE, protected=False)


def resolve_access_intent(
    kind: Kind,
    path: Optional[str] = None,
    protected: Optional[bool] = None,
) -> AccessIntent:
    """
    收敛 path / protected 为唯一访问意图

    Args:
        kind: file 或 page（决定合法命名空间与双空默认）
        path: 访问路径（如 /public、/protect/foo）
        protected: 是否受保护；None 表示未传

    Returns:
        收敛后的 AccessIntent

    Raises:
        HTTPException: 未知命名空间、或 path 与 protected 不一致时 400
    """
    normalized = _normalize_path(path)
    allowed = _allowed_namespaces(kind)

    if normalized is None and protected is None:
        return _default_intent(kind)

    if normalized is None:
        # 只填 protected → 推算 path
        if protected:
            return AccessIntent(namespace=PROTECT, protected=True)
        # 公开：文件 → /public，页面 → /pages
        namespace = PUBLIC_FILE if kind == "file" else PUBLIC_PAGE
        return AccessIntent(namespace=namespace, protected=False)

    namespace = _namespace_of(normalized)
    if namespace is None or namespace not in allowed:
        allowed_text = "、".join(sorted(allowed))
        raise HTTPException(
            status_code=400,
            detail=f"path must start with one of: {allowed_text}",
        )

    inferred = _protected_of_namespace(namespace)

    if protected is None:
        return AccessIntent(namespace=namespace, protected=inferred)

    if protected != inferred:
        raise HTTPException(
            status_code=400,
            detail=(
                f"path {normalized} implies protected={str(inferred).lower()}, "
                f"but protected={str(protected).lower()}"
            ),
        )

    return AccessIntent(namespace=namespace, protected=inferred)


def parse_optional_bool(raw) -> Optional[bool]:
    """
    解析可选布尔（表单 / query 常为字符串）

    None / 空串 → None（表示未传）；无法识别 → 400
    """
    if raw is None:
        return None
    if isinstance(raw, bool):
        return raw
    text = str(raw).strip()
    if not text:
        return None
    lowered = text.lower()
    if lowered in ("true", "1", "yes", "on"):
        return True
    if lowered in ("false", "0", "no", "off"):
        return False
    raise HTTPException(status_code=400, detail="protected must be a boolean")
