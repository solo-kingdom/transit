# Transit 文件中转服务 - 功能说明

## 核心功能

### 1. 文件上传与下载

**上传接口**
- `POST /{username}` - 上传文件（multipart/form-data 格式）
- `PUT /{username}` - 上传文件（原始文件内容，支持 curl --upload-file）

**下载接口**
- `GET /{username}/{filename}` - 下载文件
- `GET /{username}/{filename}/meta` - 获取文件元信息

**其他接口**
- `GET /` - 服务信息
- `GET /health` - 健康检查

### 2. 读写分离架构

通过 Caddy 反向代理实现端口级别的读写分离：

- **8000 端口（写端口）**：仅允许 POST/PUT 方法
- **8001 端口（读端口）**：仅允许 GET/HEAD 方法
- **8080 端口（读写端口）**：同时支持所有 HTTP 方法

### 3. 一体化容器部署

- Caddy 和 Transit 集成到单一 Docker 镜像
- 使用 Supervisor 管理多进程（transit + caddy）
- 镜像暴露三个端口（8000, 8001, 8080）
- 简化部署，无需额外配置反向代理

### 4. 安全特性

**文件名处理**
- 使用 UUID 生成随机文件名，保护隐私
- 保留原始文件名记录在元信息中

**权限控制**
- 自动移除上传文件的执行权限
- 防止恶意脚本执行

**文件大小限制**
- 默认限制 5GB
- 可通过环境变量配置

**Token 认证**（可选）
- 支持读写分离的 token 认证
- 可配置多个读 token 和写 token
- 读 token：用于下载文件和查询元信息
- 写 token：用于上传文件
- 通过 `Authorization: Bearer <token>` 请求头携带

### 5. 元信息管理

为每个上传的文件记录元信息：
- 编码后的文件名（UUID）
- 原始文件名
- 上传时间
- 上传者 IP 地址
- 文件大小
- 用户名
- 文件存储路径

### 6. 管理工具

提供命令行管理工具 `scripts/manage.py`，在容器内运行：

**统计功能**
- 统计所有/指定用户的文件数量和总大小
- 显示详细的文件列表

**清理功能**
- 清理所有文件
- 清理指定用户的文件
- 按时间清理（清理 N 天前的文件）
- 支持强制清理模式

### 7. Makefile 命令

提供 Makefile 简化常用操作：

**常用命令**
- `make help` - 查看所有可用命令
- `make build` - 构建 Docker 镜像
- `make up` - 启动服务（后台运行）
- `make down` - 停止并删除服务
- `make restart` - 重启服务
- `make logs` - 查看服务日志
- `make test` - 启动测试服务（前台运行）
- `make clean` - 清理未使用的 Docker 资源

### 8. 灵活配置

**环境变量配置**
- `DATA_DIR` - 数据存储路径（默认 ./data）
- `DOWNLOAD_HOST` - 下载 URL 的主机地址（默认自动检测本机 IP）
- `MAX_FILE_SIZE` - 最大文件大小限制
- `AUTH_ENABLED` - 是否启用认证
- `READ_TOKENS` - 读 token 列表
- `WRITE_TOKENS` - 写 token 列表

**配置特点**
- 支持自动检测本机 IP
- 支持域名或 IP 地址配置
- 适用于容器和反向代理环境

## 技术架构

**技术栈**
- Python 3.13
- FastAPI（Web 框架）
- Uvicorn（ASGI 服务器）
- Caddy 2（反向代理）
- Supervisor（进程管理）
- Docker（容器化部署）

**服务架构**
- 后端服务：Transit（监听 127.0.0.1:8000）
- 反向代理：Caddy（监听 8000, 8001, 8080）
- 进程管理：Supervisor

**数据存储**
- 文件存储在本地文件系统
- 元信息以 JSON 格式存储
- 支持按用户分目录存储

## 项目结构

```
transit/
├── src/transit/              # 源代码目录
│   ├── auth.py              # 认证模块
│   ├── config.py            # 配置管理
│   ├── main.py              # FastAPI 应用入口
│   ├── models/              # 数据模型
│   ├── routers/             # 路由模块
│   └── services/            # 服务模块
├── config/                   # 配置文件目录
│   ├── Caddyfile            # Caddy 配置
│   └── supervisord.conf     # Supervisor 配置
├── scripts/                  # 脚本目录
│   ├── manage.py            # 管理工具
│   └── run_dev.py           # 开发运行脚本
├── tests/                    # 测试文件
├── docs/                     # 文档目录
├── data/                     # 数据存储目录
├── Dockerfile
├── docker-compose.yml
├── Makefile                  # Make 命令集合
└── pyproject.toml
```
