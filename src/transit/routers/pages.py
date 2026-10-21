"""
页面托管路由

发布页面与共享资源需写凭据。
读路径：/pages 公开；受保护页走 /protect/{token}/{category}/{slug}/...。
"""

from typing import List, Optional

from fastapi import (
    APIRouter,
    Depends,
    File,
    Form,
    HTTPException,
    Path as PathParam,
    Request,
    UploadFile,
)
from fastapi.responses import FileResponse, HTMLResponse, RedirectResponse

from ..access_intent import parse_optional_bool, resolve_access_intent
from ..auth import verify_write_token
from ..content import detect_content_type
from ..pages_render import render_category_page, render_index_page
from ..services.pages_service import PageError, pages_service
from .files import get_download_base_url

router = APIRouter()

NOSNIFF = {"X-Content-Type-Options": "nosniff"}

# 直接打开时会在本服务域名下执行脚本的文档类型，额外加沙箱
SANDBOXED_TYPES = {"image/svg+xml"}


def _asset_response(target, content_type: str) -> FileResponse:
    """构造资源响应：按扩展名给内容类型，禁止嗅探，可执行文档加沙箱"""
    headers = dict(NOSNIFF)
    if content_type in SANDBOXED_TYPES:
        headers["Content-Security-Policy"] = "sandbox"

    return FileResponse(target, media_type=content_type, headers=headers)


@router.post("/pages/publish")
async def publish_page(
    request: Request,
    category: str = Form(..., description="分类标识"),
    slug: str = Form(..., description="页面标识"),
    title: str = Form(..., description="标题"),
    desc: str = Form(..., description="摘要"),
    html: Optional[str] = Form(None, description="HTML 正文（单文件页面）"),
    bundle: Optional[UploadFile] = File(None, description="页面 zip 包（多文件页面）"),
    tags: List[str] = Form([], description="标签，可重复"),
    date: Optional[str] = Form(None, description="发布日期，缺省为当天"),
    category_name: Optional[str] = Form(None, description="分类显示名（分类尚不存在时需要）"),
    category_description: Optional[str] = Form(None, description="分类简介"),
    path: Optional[str] = Form(None, description="访问路径：/pages 或 /protect；可省略"),
    protected: Optional[str] = Form(
        None, description="是否受保护；可省略。与 path 都省略时默认 /pages（公开）"
    ),
    token: Optional[str] = Depends(verify_write_token),
):
    """
    发布一个页面

    正文二选一：直接给 HTML 字符串（单文件页面），或给一个 zip 包
    （解压后即页面目录，入口固定 index.html，页面内可带任意静态资源）。

    可选 path / protected：默认公开（/pages）；受保护时返回 /protect/{token}/...。

    Returns:
        该页面与所属分类的链接；受保护时含 token
    """
    intent = resolve_access_intent(
        "page",
        path=path,
        protected=parse_optional_bool(protected),
    )
    meta = {
        "category": category,
        "slug": slug,
        "title": title,
        "desc": desc,
        "tags": tags,
        "date": date,
        "category_name": category_name,
        "category_description": category_description,
    }
    bundle_bytes = await bundle.read() if bundle is not None else None

    try:
        result = pages_service.publish(
            meta,
            html=html,
            bundle=bundle_bytes,
            protected=intent.protected,
        )
    except PageError as e:
        raise HTTPException(status_code=400, detail=str(e))

    base = get_download_base_url(request)
    payload = {
        "url": f"{base}{result['url']}",
        "category_url": f"{base}{result['category_url']}",
    }
    if "token" in result:
        payload["token"] = result["token"]
    return payload


@router.post("/pages/assets")
async def publish_shared_asset(
    request: Request,
    path: str = Form(..., description="相对共享资源目录的路径"),
    file: UploadFile = File(..., description="资源文件"),
    token: Optional[str] = Depends(verify_write_token),
):
    """
    发布一个共享资源

    共享资源集中存放，所有页面用绝对路径 `/pages/assets/<路径>` 引用。

    Returns:
        该资源的公开链接
    """
    content = await file.read()

    try:
        relative = pages_service.publish_asset(path, content)
    except PageError as e:
        raise HTTPException(status_code=400, detail=str(e))

    return {"url": f"{get_download_base_url(request)}{relative}"}


@router.get("/pages/")
async def pages_index():
    """页面站索引页（公开，无需凭据）"""
    return HTMLResponse(render_index_page(pages_service.load_registry()), headers=NOSNIFF)


@router.get("/pages/{category}")
async def pages_category_redirect(category: str = PathParam(..., description="分类标识")):
    """
    分类路径的无尾斜杠形式

    该形态是精确的两段路径，会直接命中按编码文件名下载的变量路由，
    故显式重定向到带尾斜杠的分类页。
    """
    return RedirectResponse(url=f"/pages/{category}/", status_code=307)


@router.get("/pages/{category}/")
async def pages_category(category: str = PathParam(..., description="分类标识")):
    """分类页（公开，无需凭据）"""
    page = render_category_page(pages_service.load_registry(), category)
    if page is None:
        raise HTTPException(status_code=404, detail="Category not found")

    return HTMLResponse(page, headers=NOSNIFF)


# 顺序敏感：/pages/assets/... 与 /pages/{category}/{slug}/{resource} 形状重叠，
# 共享资源必须先注册，否则 assets 会被当成分类名
@router.get("/pages/assets/{asset_path:path}")
async def shared_asset(asset_path: str = PathParam(..., description="相对共享资源目录的路径")):
    """共享资源（公开，无需凭据）"""
    target = pages_service.resolve_shared_asset(asset_path)
    if target is None:
        raise HTTPException(status_code=404, detail="Asset not found")

    return _asset_response(target, detect_content_type(target.name))


def _reject_if_protected(category: str, slug: str) -> None:
    """公开 /pages 入口不得读受保护页"""
    entry = pages_service.get_page_entry(category, slug)
    if entry is not None and entry.get("protected"):
        raise HTTPException(status_code=404, detail="Page not found")


@router.get("/pages/{category}/{slug}/")
async def page_entry(
    category: str = PathParam(..., description="分类标识"),
    slug: str = PathParam(..., description="页面标识"),
):
    """页面入口（公开；受保护页请走 /protect/{token}/...）"""
    _reject_if_protected(category, slug)
    target = pages_service.resolve_page_resource(category, slug, "index.html")
    if target is None:
        raise HTTPException(status_code=404, detail="Page not found")

    return FileResponse(target, media_type="text/html", headers=NOSNIFF)


@router.get("/pages/{category}/{slug}/{resource_path:path}")
async def page_resource(
    category: str = PathParam(..., description="分类标识"),
    slug: str = PathParam(..., description="页面标识"),
    resource_path: str = PathParam(..., description="页面内的资源路径"),
):
    """页面内资源（公开；受保护页请走 /protect/{token}/...）"""
    _reject_if_protected(category, slug)
    target = pages_service.resolve_page_resource(category, slug, resource_path)
    if target is None:
        raise HTTPException(status_code=404, detail="Resource not found")

    return _asset_response(target, detect_content_type(target.name))


@router.get("/protect/{token}/{category}/{slug}/")
async def protected_page_entry(
    token: str = PathParam(..., description="页面访问凭据"),
    category: str = PathParam(..., description="分类标识"),
    slug: str = PathParam(..., description="页面标识"),
):
    """受保护页面入口：路径内 token 须与该页凭据一致"""
    found = pages_service.find_by_token(token)
    if found is None or found[0] != category or found[1] != slug:
        raise HTTPException(status_code=404, detail="Page not found")

    target = pages_service.resolve_page_resource(category, slug, "index.html")
    if target is None:
        raise HTTPException(status_code=404, detail="Page not found")

    return FileResponse(target, media_type="text/html", headers=NOSNIFF)


@router.get("/protect/{token}/{category}/{slug}/{resource_path:path}")
async def protected_page_resource(
    token: str = PathParam(..., description="页面访问凭据"),
    category: str = PathParam(..., description="分类标识"),
    slug: str = PathParam(..., description="页面标识"),
    resource_path: str = PathParam(..., description="页面内的资源路径"),
):
    """受保护页面内资源"""
    found = pages_service.find_by_token(token)
    if found is None or found[0] != category or found[1] != slug:
        raise HTTPException(status_code=404, detail="Page not found")

    target = pages_service.resolve_page_resource(category, slug, resource_path)
    if target is None:
        raise HTTPException(status_code=404, detail="Resource not found")

    return _asset_response(target, detect_content_type(target.name))
