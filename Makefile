.PHONY: help build up down restart logs logs-transit logs-caddy logs-files test clean docker-push docker-tag

# 从 VERSION 文件读取版本号
VERSION := $(shell cat VERSION 2>/dev/null || echo "0.0.1")
IMAGE_NAME := sunzhenkai/transit

# 默认目标
help:
	@echo "Transit 文件中转服务 - Makefile 命令"
	@echo ""
	@echo "使用方法: make [命令]"
	@echo ""
	@echo "可用命令:"
	@echo "  build        - 构建 Docker 镜像"
	@echo "  up           - 启动服务（后台运行）"
	@echo "  down         - 停止并删除服务"
	@echo "  restart      - 重启服务"
	@echo "  logs         - 查看所有服务日志（实时）"
	@echo "  logs-transit - 查看后端服务日志（实时）"
	@echo "  logs-caddy   - 查看 Caddy 日志（实时）"
	@echo "  logs-files   - 查看容器内日志文件"
	@echo "  test         - 启动测试服务（前台运行）"
	@echo "  clean        - 清理未使用的 Docker 资源"
	@echo "  docker-push  - 构建并推送镜像到 Docker Hub"
	@echo "  docker-tag    - 给镜像打标签"
	@echo "  help         - 显示此帮助信息"

# 构建 Docker 镜像
build:
	@echo "🔨 构建 Docker 镜像..."
	docker-compose build

# 启动服务（后台运行）
up:
	@echo "🚀 启动服务..."
	docker-compose up -d
	@echo "✅ 服务已启动"
	@echo ""
	@echo "端口说明:"
	@echo "  - 8000: 写端口 (POST/PUT)"
	@echo "  - 8001: 读端口 (GET/HEAD)"
	@echo "  - 8080: 读写端口 (所有方法)"
	@echo ""
	@echo "查看日志: make logs"
	@echo "停止服务: make down"

# 停止并删除服务
down:
	@echo "🛑 停止服务..."
	docker-compose down
	@echo "✅ 服务已停止"

# 重启服务
restart: down up

# 查看所有服务日志（实时）
logs:
	docker-compose logs -f

# 查看后端服务日志（实时）
logs-transit:
	@echo "📋 查看 Transit 后端服务日志（按 Ctrl+C 退出）..."
	docker exec transit tail -f /var/log/supervisor/transit.out.log /var/log/supervisor/transit.err.log

# 查看 Caddy 日志（实时）
logs-caddy:
	@echo "📋 查看 Caddy 日志（按 Ctrl+C 退出）..."
	docker exec transit tail -f /var/log/supervisor/caddy.out.log /var/log/supervisor/caddy.err.log

# 查看容器内日志文件
logs-files:
	@echo "📋 容器内日志文件列表："
	@echo ""
	@docker exec transit ls -lh /var/log/supervisor/
	@echo ""
	@echo "查看特定日志文件："
	@echo "  docker exec transit tail -f /var/log/supervisor/transit.out.log"
	@echo "  docker exec transit tail -f /var/log/supervisor/transit.err.log"
	@echo "  docker exec transit tail -f /var/log/supervisor/caddy.out.log"
	@echo "  docker exec transit tail -f /var/log/supervisor/caddy.err.log"
	@echo "  docker exec transit tail -f /var/log/supervisor/supervisord.log"

# 启动测试服务（前台运行）
test:
	@echo "🧪 启动测试服务（前台运行）..."
	@echo "按 Ctrl+C 停止服务"
	@echo ""
	docker-compose up

# 清理未使用的 Docker 资源
clean:
	@echo "🧹 清理未使用的 Docker 资源..."
	docker system prune -f
	@echo "✅ 清理完成"

# 给镜像打标签
docker-tag:
	@echo "🏷️  给镜像打标签..."
	docker tag transit-transit:latest $(IMAGE_NAME):$(VERSION)
	docker tag transit-transit:latest $(IMAGE_NAME):latest
	@echo "✅ 标签完成"
	@echo ""
	@echo "镜像标签："
	@echo "  - $(IMAGE_NAME):$(VERSION)"
	@echo "  - $(IMAGE_NAME):latest"

# 构建并推送镜像到 Docker Hub
docker-push: build docker-tag
	@echo "🚀 推送镜像到 Docker Hub..."
	docker push $(IMAGE_NAME):$(VERSION)
	docker push $(IMAGE_NAME):latest
	@echo "✅ 推送完成！"
	@echo ""
	@echo "镜像地址："
	@echo "  - docker pull $(IMAGE_NAME):$(VERSION)"
	@echo "  - docker pull $(IMAGE_NAME):latest"

