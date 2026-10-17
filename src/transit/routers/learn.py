"""
学习内容路由

发布需写凭据；索引、分类与专题页公开可读，不需凭据。
"""

from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Path as PathParam, Request
from fastapi.responses import FileResponse, HTMLResponse, RedirectResponse
from pydantic import BaseModel

from ..auth import verify_write_token
from ..learn_pages import render_category_page, render_index_page
from ..services.learn_service import LearnError, learn_service
from .files import get_download_base_url

router = APIRouter()

NOSNIFF = {"X-Content-Type-Options": "nosniff"}


class PublishRequest(BaseModel):
    """发布请求体"""

    category: str
    slug: str
    title: str
    desc: str
    html: str
    tags: List[str] = []
    date: Optional[str] = None
    category_name: Optional[str] = None
    category_description: Optional[str] = None


@router.post("/learn/publish")
async def publish_topic(
    request: Request,
    payload: PublishRequest,
    token: Optional[str] = Depends(verify_write_token),
):
    """
    发布一篇学习专题

    发布成功即公开可浏览，无审核环节。

    Args:
        request: 请求对象
        payload: 发布请求体
        token: 写凭据（如果启用认证）

    Returns:
        该专题与所属分类的公开链接
    """
    try:
        result = learn_service.publish(payload.model_dump())
    except LearnError as e:
        raise HTTPException(status_code=400, detail=str(e))

    base = get_download_base_url(request)

    return {"url": f"{base}{result['url']}", "category_url": f"{base}{result['category_url']}"}


@router.get("/learn/")
async def learn_index():
    """学习站索引页（公开，无需凭据）"""
    return HTMLResponse(render_index_page(learn_service.load_registry()), headers=NOSNIFF)


@router.get("/learn/{category}")
async def learn_category_redirect(category: str = PathParam(..., description="分类标识")):
    """
    分类路径的无尾斜杠形式

    该形态是精确的两段路径，会直接命中按编码文件名下载的变量路由，
    故显式重定向到带尾斜杠的分类页。
    """
    return RedirectResponse(url=f"/learn/{category}/", status_code=307)


@router.get("/learn/{category}/")
async def learn_category(category: str = PathParam(..., description="分类标识")):
    """分类页（公开，无需凭据）"""
    page = render_category_page(learn_service.load_registry(), category)
    if page is None:
        raise HTTPException(status_code=404, detail="Category not found")

    return HTMLResponse(page, headers=NOSNIFF)


@router.get("/learn/{category}/{slug}/")
async def learn_topic(
    category: str = PathParam(..., description="分类标识"),
    slug: str = PathParam(..., description="专题标识"),
):
    """专题页（公开，无需凭据）"""
    target = learn_service.topic_file(category, slug)
    if not target.is_file():
        raise HTTPException(status_code=404, detail="Topic not found")

    return FileResponse(target, media_type="text/html", headers=NOSNIFF)
