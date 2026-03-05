# 使用 Python 3.13 官方镜像作为基础镜像
FROM python:3.13-slim

# 设置工作目录
WORKDIR /app

# 设置环境变量
ENV PYTHONUNBUFFERED=1 \
  PYTHONDONTWRITEBYTECODE=1 \
  PIP_NO_CACHE_DIR=1 \
  PIP_DISABLE_PIP_VERSION_CHECK=1

# 安装系统依赖和 Caddy
RUN apt-get update && apt-get install -y --no-install-recommends \
  curl \
  supervisor \
  && curl -1sLf 'https://dl.cloudsmith.io/public/caddy/stable/gpg.key' | gpg --dearmor -o /usr/share/keyrings/caddy-stable-archive-keyring.gpg \
  && curl -1sLf 'https://dl.cloudsmith.io/public/caddy/stable/debian.deb.txt' | tee /etc/apt/sources.list.d/caddy-stable.list \
  && apt-get update \
  && apt-get install -y --no-install-recommends caddy \
  && rm -rf /var/lib/apt/lists/*

# 复制项目依赖文件
COPY pyproject.toml ./

# 安装 Python 依赖
RUN pip install --no-cache-dir -e .

# 复制项目代码
COPY src/ ./src/
COPY README.md ./

# 复制 Caddy 配置文件
COPY Caddyfile /etc/caddy/Caddyfile

# 复制 Supervisor 配置文件
COPY supervisord.conf /etc/supervisor/conf.d/supervisord.conf

# 创建必要的目录
RUN mkdir -p /app/data /var/log/supervisor

# 暴露端口
# 8000: Caddy 写端口（仅 POST/PUT）
# 8001: Caddy 读端口（仅 GET/HEAD）
# 8080: 读写端口（同时支持读写）
EXPOSE 8000 8001 8080

# 健康检查
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
  CMD python -c "import httpx; httpx.get('http://127.0.0.1:8000/health')" || exit 1

# 使用 supervisor 启动服务
CMD ["/usr/bin/supervisord", "-c", "/etc/supervisor/conf.d/supervisord.conf"]
