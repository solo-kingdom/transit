"""访问命名空间决策单测"""

import pytest
from fastapi import HTTPException

from transit.access_intent import resolve_access_intent


def test_file_default_is_protect():
    intent = resolve_access_intent("file")
    assert intent.namespace == "/protect"
    assert intent.protected is True


def test_page_default_is_pages():
    intent = resolve_access_intent("page")
    assert intent.namespace == "/pages"
    assert intent.protected is False


def test_infer_from_path_only():
    assert resolve_access_intent("file", path="/public").protected is False
    assert resolve_access_intent("file", path="/protect").protected is True
    assert resolve_access_intent("page", path="/pages").protected is False


def test_infer_path_from_protected_only():
    assert resolve_access_intent("file", protected=False).namespace == "/public"
    assert resolve_access_intent("file", protected=True).namespace == "/protect"
    assert resolve_access_intent("page", protected=False).namespace == "/pages"


def test_mismatch_raises_400():
    with pytest.raises(HTTPException) as exc:
        resolve_access_intent("file", path="/public", protected=True)
    assert exc.value.status_code == 400


def test_unknown_namespace_raises_400():
    with pytest.raises(HTTPException) as exc:
        resolve_access_intent("file", path="/pages")
    assert exc.value.status_code == 400
