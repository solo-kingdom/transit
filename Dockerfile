# 使用 Python 3.13 官方镜像作为基础镜像
FROM python:3.13-slim

# 设置工作目录
WORKDIR /app

# 设置环境变量
ENV PYTHONUNBUFFERED=1 \
  PYTHONDONTWRITEBYTECODE=1 \
  PIP_NO_CACHE_DIR=1 \
  PIP_DISABLE_PIP_VERSION_CHECK=1

# 替换为阿里云镜像源（加速 apt-get）
RUN sed -i 's/deb.debian.org/mirrors.aliyun.com/g' /etc/apt/sources.list.d/debian.sources \
    && sed -i 's/security.debian.org/mirrors.aliyun.com/g' /etc/apt/sources.list.d/debian.sources

# 安装系统依赖和 Caddy
RUN apt-get update && apt-get install -y --no-install-recommends \
  curl \
  supervisor \
  gnupg \
  && curl -1sLf 'https://dl.cloudsmith.io/public/caddy/stable/gpg.key' | gpg --dearmor -o /usr/share/keyrings/caddy-stable-archive-keyring.gpg \
  && curl -1sLf 'https://dl.cloudsmith.io/public/caddy/stable/debian.deb.txt' | tee /etc/apt/sources.list.d/caddy-stable.list \
  && apt-get update \
  && apt-get install -y --no-install-recommends caddy \
  && rm -rf /var/lib/apt/lists/*

# 复制配置文件
COPY config/pip.conf /root/.pip/pip.conf
COPY config/Caddyfile /etc/caddy/Caddyfile
COPY config/supervisord.conf /etc/supervisor/conf.d/supervisord.conf

# 复制项目文件（pip install -e . 需要这些文件）
COPY pyproject.toml README.md ./
COPY src/ ./src/

# 安装 Python 依赖
RUN pip install --no-cache-dir -e .

# 复制管理脚本
COPY scripts/ ./scripts/

# 创建必要的目录
RUN mkdir -p /app/data /var/log/supervisor

# 暴露端口
# 9201: 读端口（仅 GET/HEAD）
# 9202: 写端口（仅 POST/PUT）
# 9200: 服务端口（同时支持读写）
EXPOSE 9201 9202 9200

# 健康检查（访问后端服务）
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
  CMD python -c "import httpx; httpx.get('http://127.0.0.1:9000/health')" || exit 1

# 使用 supervisor 启动服务
CMD ["/usr/bin/supervisord", "-c", "/etc/supervisor/conf.d/supervisord.conf"]
