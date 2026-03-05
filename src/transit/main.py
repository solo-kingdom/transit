"""
FastAPI 主应用
文件中转服务入口
"""

import time
import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request, Response
from fastapi.middleware.cors import CORSMiddleware

from .config import settings
from .routers.files import router as files_router

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger(__name__)


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


# 访问日志中间件
@app.middleware("http")
async def access_log_middleware(request: Request, call_next):
    """
    访问日志中间件
    记录所有请求的重点信息
    """
    # 记录开始时间
    start_time = time.time()

    # 获取客户端 IP
    forwarded_for = request.headers.get("x-forwarded-for")
    if forwarded_for:
        client_ip = forwarded_for.split(",")[0].strip()
    else:
        client_ip = request.client.host if request.client else "unknown"

    # 获取请求信息
    method = request.method
    path = request.url.path

    # 执行请求
    response = await call_next(request)

    # 计算处理时间
    process_time = time.time() - start_time

    # 获取响应信息
    status_code = response.status_code

    # 构建日志消息
    log_parts = [
        f"client={client_ip}",
        f"method={method}",
        f"path={path}",
        f"status={status_code}",
        f"time={process_time:.3f}s",
    ]

    # 添加文件大小信息（如果有）
    if "content-length" in response.headers:
        content_length = int(response.headers["content-length"])
        if content_length > 0:
            # 格式化文件大小
            if content_length < 1024:
                size_str = f"{content_length}B"
            elif content_length < 1024 * 1024:
                size_str = f"{content_length / 1024:.2f}KB"
            elif content_length < 1024 * 1024 * 1024:
                size_str = f"{content_length / (1024 * 1024):.2f}MB"
            else:
                size_str = f"{content_length / (1024 * 1024 * 1024):.2f}GB"
            log_parts.append(f"size={size_str}")

    # 根据状态码选择日志级别
    if status_code < 400:
        log_level = logging.INFO
    elif status_code < 500:
        log_level = logging.WARNING
    else:
        log_level = logging.ERROR

    # 记录日志
    logger.log(log_level, " | ".join(log_parts))

    # 添加处理时间到响应头
    response.headers["X-Process-Time"] = f"{process_time:.3f}"

    return response


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
