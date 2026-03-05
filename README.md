# Transit - 文件中转服务

一个安全、便捷的文件中转服务，解决多地域网络连通、内外网安全性等问题。

## 特性

- 🔒 **读写分离** - 支持读写端口分离，增强安全性
- 🐳 **一体化镜像** - Caddy 已集成到镜像中，简化部署
- 🔐 **Token 认证** - 支持读写分离的 token 认证，可配置多个 token
- 🎲 **UUID 文件名** - 使用 UUID 生成唯一文件名，保护隐私
- 🔗 **完整 URL** - 自动生成包含主机地址的完整下载 URL
- 📊 **元信息管理** - 记录文件上传时间、来源 IP、文件大小等元信息
- 🛠️ **管理工具** - 提供命令行管理工具，支持统计、清理等功能
- 🛡️ **安全防护** - 自动移除文件执行权限，防止恶意文件
- 📁 **灵活存储** - 支持自定义数据保存路径
- 🚀 **容器化部署** - 支持 Docker 和 Docker Compose
- ⚡ **高性能** - 基于 FastAPI 和 uvicorn，性能优异

## 技术栈

- **语言**: Python 3.10+
- **框架**: FastAPI
- **服务器**: Uvicorn
- **部署**: Docker

## 快速开始

### 使用 Makefile（最简单）

1. 克隆项目
```bash
git clone <repository-url>
cd transit
```

2. 构建并启动服务
```bash
make build
make up
```

3. 查看日志
```bash
make logs
```

4. 停止服务
```bash
make down
```

**其他常用命令**：
- `make help` - 查看所有可用命令
- `make test` - 启动测试服务（前台运行）
- `make restart` - 重启服务
- `make clean` - 清理未使用的 Docker 资源

### 使用 Docker Compose（推荐）

1. 克隆项目
```bash
git clone <repository-url>
cd transit
```

2. 启动服务
```bash
docker-compose up -d
```

3. 查看日志
```bash
docker-compose logs -f
```

### 使用 Docker

1. 构建镜像
```bash
docker build -t transit:latest .
```

2. 运行容器
```bash
docker run -d \
  --name transit \
  -p 8000:8000 \
  -p 8001:8001 \
  -p 8080:8080 \
  -v $(pwd)/data:/app/data \
  transit:latest
```

**端口说明**：
- `8000`: Caddy 写端口（仅允许 POST/PUT 方法）
- `8001`: Caddy 读端口（仅允许 GET/HEAD 方法）
- `8080`: 读写端口（同时支持所有方法）

### 本地开发

1. 安装依赖
```bash
pip install -e ".[dev]"
```

2. 配置环境变量（可选）
```bash
cp .env.example .env
# 编辑 .env 文件配置参数
```

3. 运行开发服务器
```bash
fastapi dev src/transit/main.py
```

或使用 uvicorn：
```bash
uvicorn transit.main:app --reload --host 0.0.0.0 --port 8000
```

## 使用方法

### 上传文件

使用 curl 上传文件：

```bash
curl --upload-file /path/to/file http://localhost:8000
```

返回示例：
```json
{
  "download_url": "http://192.168.1.100:8000/AbCdEf123456.txt/file.txt"
}
```

**注意**：
- `download_url` 包含完整的 URL（包含自动检测的本机 IP 或配置的 host）
### 下载文件

使用 wget 或 curl 下载文件：

```bash
# wget：直接使用 URL 末尾的原始文件名
wget http://localhost:8000/AbCdEf123456.txt/file.txt
```

或

```bash
# curl：直接使用 URL 末尾的原始文件名
curl -O http://localhost:8000/AbCdEf123456.txt/file.txt
```

### 查询文件元信息

获取文件的详细元信息：

```bash
curl http://localhost:8000/AbCdEf123456.txt/file.txt/meta
```

返回示例：
```json
{
  "message": "File metadata retrieved successfully",
  "meta": {
    "encoded_filename": "AbCdEf123456.txt",
    "original_filename": "file.txt",
    "upload_time": "2026-03-05T13:30:00.123456",
    "remote_address": "192.168.1.50",
    "file_size": 1024,
    "username": "username",
    "file_path": "username/AbCdEf123456.txt"
  }
}
```

### API 端点

- `POST /` - 上传文件（multipart/form-data 格式）
- `PUT /` 和 `PUT /{path}` - 上传文件（原始文件内容，支持 curl --upload-file）
- `GET /{encoded_filename}/{original_filename}` - 下载文件
- `GET /{encoded_filename}/{original_filename}/meta` - 获取文件元信息
- `GET /` - 服务信息
- `GET /health` - 健康检查


## 配置

### 环境变量

| 变量名 | 说明 | 默认值 |
|--------|------|--------|
| `APP_NAME` | 应用名称 | File Transit Service |
| `APP_VERSION` | 应用版本 | 0.1.0 |
| `DATA_DIR` | 数据存储路径 | ./data |
| `PORT` | 服务端口（内部） | 8000 |
| `DOWNLOAD_HOST` | 下载 URL 的主机地址 | 自动检测本机 IP |
| `MAX_FILE_SIZE` | 最大文件大小（字节） | 5368709120 (5GB) |
| `REMOVE_EXEC_PERMISSION` | 移除执行权限 | true |
| `AUTH_ENABLED` | 是否启用认证 | false |
| `READ_TOKENS` | 读 token 列表（逗号分隔） | - |
| `WRITE_TOKENS` | 写 token 列表（逗号分隔） | - |

**端口说明**：
- 镜像内部 transit 服务监听 `127.0.0.1:8000`
- Caddy 作为反向代理，暴露三个端口：
  - `8000`: 写端口（仅允许 POST/PUT）
  - `8001`: 读端口（仅允许 GET/HEAD）
  - `8080`: 读写端口（同时支持所有方法）

**DOWNLOAD_HOST 配置说明**：
- 如果不设置，系统会自动检测本机 IP 地址
- 可以设置为域名（如 `example.com`）或 IP 地址（如 `192.168.1.100`）
- 在容器环境或反向代理后，建议显式设置此参数

### 认证配置

启用 token 认证后，需要在请求头中携带 token：

```bash
# 启用认证
export AUTH_ENABLED=true
export READ_TOKENS=read123,read456
export WRITE_TOKENS=write123,write456

# 上传文件（需要写 token）
curl -H "Authorization: Bearer write123" --upload-file file.txt http://localhost:8000/user

# 下载文件（需要读 token）
curl -H "Authorization: Bearer read123" http://localhost:8000/user/filename
```

**认证说明**：
- `READ_TOKENS`：用于下载文件和查询元信息
- `WRITE_TOKENS`：用于上传文件
- 多个 token 用逗号分隔
- token 在请求头中以 `Authorization: Bearer <token>` 格式携带

### 读写分离架构

服务默认启用读写分离，通过 Caddy 反向代理实现：

**端口说明**：
- **8000 端口（写端口）**：仅允许 POST/PUT 方法
  - 用于上传文件
  - 自动拒绝 GET/HEAD 请求（除了 /health 和 / 路径）
  
- **8001 端口（读端口）**：仅允许 GET/HEAD 方法
  - 用于下载文件和查询元信息
  - 自动拒绝 POST/PUT 请求
  
- **8080 端口（读写端口）**：同时支持所有方法
  - 适用于需要完整功能的场景
  - 不限制请求方法

**使用示例**：
```bash
# 使用写端口上传文件
curl --upload-file file.txt http://localhost:8000/user

# 使用读端口下载文件
curl http://localhost:8001/user/filename

# 使用读写端口（完整功能）
curl --upload-file file.txt http://localhost:8080/user
curl http://localhost:8080/user/filename
```

## 项目结构

```
transit/
├── src/
│   └── transit/
│       ├── __init__.py
│       ├── auth.py             # 认证模块
│       ├── config.py          # 配置管理
│       ├── main.py            # FastAPI 应用入口
│       ├── models/            # 数据模型
│       │   ├── __init__.py
│       │   └── meta.py        # 文件元信息模型
│       ├── routers/
│       │   ├── __init__.py
│       │   └── files.py       # 文件路由
│       └── services/
│           ├── __init__.py
│           └── file_service.py # 文件处理服务
├── config/                     # 配置文件目录
│   ├── Caddyfile              # Caddy 配置文件
│   └── supervisord.conf       # Supervisor 配置文件
├── scripts/                    # 脚本目录
│   ├── manage.py              # 管理工具
│   └── run_dev.py             # 开发运行脚本
├── tests/                      # 测试文件
├── docs/                       # 文档目录
├── data/                       # 数据存储目录
├── Dockerfile
├── docker-compose.yml
├── Makefile                    # Make 命令集合
├── pyproject.toml
└── README.md
```

## 管理工具

项目提供命令行管理工具 `scripts/manage.py`，用于统计和清理文件。

### 统计文件信息

```bash
# 统计所有文件信息
python scripts/manage.py stats

# 统计指定用户的文件信息
python scripts/manage.py stats -u username

# 统计所有用户的详细信息
python scripts/manage.py stats --detail
```

### 列出文件

```bash
# 列出所有文件
python scripts/manage.py list

# 列出指定用户的文件
python scripts/manage.py list -u username
```

### 清理文件

```bash
# 清理所有文件（需要确认）
python scripts/manage.py clean

# 清理指定用户的文件
python scripts/manage.py clean -u username

# 清理 7 天前的所有文件
python manage.py clean --days 7

# 清理指定用户 30 天前的文件
python manage.py clean -u username --days 30

# 强制清理（不需要确认）
python manage.py clean --force
```

### 在 Docker 容器中使用

```bash
# 进入容器
docker exec -it transit-write bash

# 运行管理工具
python manage.py stats
python manage.py clean --days 30 --force
```

## 安全特性

1. **UUID 文件名** - 上传的文件使用 UUID 重命名，防止文件名泄露
2. **Token 认证** - 支持读写分离的 token 认证，保护接口安全
3. **移除执行权限** - 自动移除上传文件的执行权限，防止恶意脚本执行
4. **文件大小限制** - 限制上传文件大小，防止 DoS 攻击
5. **读写分离** - 通过 Caddy 实现读写端口分离，增强访问控制
6. **一体化部署** - Caddy 集成到镜像中，减少攻击面，简化安全配置

## 开发

### 运行测试

```bash
pytest
```

### 代码格式化

```bash
black src/ tests/
```

### 代码检查

```bash
ruff check src/ tests/
```

## License

MIT License
