"""
FastAPI 主应用
文件中转服务入口
"""

from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .config import settings
from .routers.files import router as files_router


@asynccontextmanager
async def lifespan(app: FastAPI):
    """应用生命周期管理"""
    # 启动时
    print(f"🚀 {settings.app_name} v{settings.app_version} starting...")
    print(f"📁 Data directory: {settings.data_dir.absolute()}")
    print(f"🔌 Service port: {settings.port}")

    yield

    # 关闭时
    print(f"👋 {settings.app_name} shutting down...")


# 创建 FastAPI 应用实例
app = FastAPI(
    title=settings.app_name,
    version=settings.app_version,
    description="A secure file transit service for multi-region network connectivity",
    lifespan=lifespan,
)

# 配置 CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # 生产环境应配置具体域名
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 注册路由
app.include_router(files_router, tags=["files"])


@app.get("/")
async def root():
    """根路径"""
    return {"service": settings.app_name, "version": settings.app_version, "status": "running"}


@app.get("/health")
async def health():
    """健康检查端点"""
    return {"status": "healthy"}
