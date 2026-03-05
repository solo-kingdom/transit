.PHONY: help build up down restart logs test clean

# 默认目标
help:
	@echo "Transit 文件中转服务 - Makefile 命令"
	@echo ""
	@echo "使用方法: make [命令]"
	@echo ""
	@echo "可用命令:"
	@echo "  build    - 构建 Docker 镜像"
	@echo "  up       - 启动服务（后台运行）"
	@echo "  down     - 停止并删除服务"
	@echo "  restart  - 重启服务"
	@echo "  logs     - 查看服务日志"
	@echo "  test     - 启动测试服务（前台运行）"
	@echo "  clean    - 清理未使用的 Docker 资源"
	@echo "  help     - 显示此帮助信息"

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

# 查看服务日志
logs:
	docker-compose logs -f

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
