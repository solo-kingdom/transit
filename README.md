# Transit - 文件中转服务

一个安全、便捷的文件中转服务，解决多地域网络连通、内外网安全性等问题。

## 特性

- 🔒 **读写分离** - 支持读写端口分离，增强安全性
- 🎲 **文件名编码** - 使用随机字符串编码文件名，保护隐私
- 🔗 **完整 URL** - 自动生成包含主机地址的完整下载 URL
- 📊 **元信息管理** - 记录文件上传时间、来源 IP、文件大小等元信息
- 🛡️ **安全防护** - 自动移除文件执行权限，防止恶意文件
- 📁 **灵活存储** - 支持自定义数据保存路径
- 🐳 **容器化部署** - 支持 Docker 和 Docker Compose
- ⚡ **高性能** - 基于 FastAPI 和 uvicorn，性能优异

## 技术栈

- **语言**: Python 3.10+
- **框架**: FastAPI
- **服务器**: Uvicorn
- **部署**: Docker

## 快速开始

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
  -v $(pwd)/data:/app/data \
  transit:latest
```

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
curl --upload-file /path/to/file http://localhost:8000/username
```

返回示例：
```json
{
  "message": "File uploaded successfully",
  "download_url": "http://192.168.1.100:8000/username/AbCdEf123456.txt",
  "download_path": "/username/AbCdEf123456.txt",
  "filename": "AbCdEf123456.txt",
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

**注意**：
- `download_url` 包含完整的 URL（包含自动检测的本机 IP 或配置的 host）
- `meta` 包含文件的元信息（上传时间、上传者 IP、文件大小等）

### 下载文件

使用 wget 或 curl 下载文件：

```bash
wget http://localhost:8000/username/AbCdEf123456.txt
```

或

```bash
curl -O http://localhost:8000/username/AbCdEf123456.txt
```

### 查询文件元信息

获取文件的详细元信息：

```bash
curl http://localhost:8000/username/AbCdEf123456.txt/meta
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

- `POST /{username}` - 上传文件（multipart/form-data 格式）
- `PUT /{username}` - 上传文件（原始文件内容，支持 curl --upload-file）
- `GET /{username}/{encoded_filename}` - 下载文件
- `GET /{username}/{encoded_filename}/meta` - 获取文件元信息
- `GET /` - 服务信息
- `GET /health` - 健康检查


## 配置

### 环境变量

| 变量名 | 说明 | 默认值 |
|--------|------|--------|
| `APP_NAME` | 应用名称 | File Transit Service |
| `APP_VERSION` | 应用版本 | 0.1.0 |
| `DATA_DIR` | 数据存储路径 | ./data |
| `WRITE_PORT` | 写端口（上传） | 8000 |
| `READ_PORT` | 读端口（下载） | None（使用同一端口） |
| `DOWNLOAD_HOST` | 下载 URL 的主机地址 | 自动检测本机 IP |
| `ENCODE_LENGTH` | 文件名编码长度 | 16 |
| `MAX_FILE_SIZE` | 最大文件大小（字节） | 104857600 (100MB) |
| `REMOVE_EXEC_PERMISSION` | 移除执行权限 | true |

**DOWNLOAD_HOST 配置说明**：
- 如果不设置，系统会自动检测本机 IP 地址
- 可以设置为域名（如 `example.com`）或 IP 地址（如 `192.168.1.100`）
- 在容器环境或反向代理后，建议显式设置此参数

### 读写分离配置

如需启用读写分离，编辑 `docker-compose.yml`，取消注释 `transit-read` 服务配置：

```yaml
services:
  transit-write:
    ports:
      - "8000:8000"
    # 写服务配置...

  transit-read:
    ports:
      - "8001:8000"
    # 读服务配置...
```

## 项目结构

```
transit/
├── src/
│   └── transit/
│       ├── __init__.py
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
├── tests/                     # 测试文件
├── data/                      # 数据存储目录
├── Dockerfile
├── docker-compose.yml
├── pyproject.toml
└── README.md
```

## 安全特性

1. **文件名随机编码** - 上传的文件会被重命名为随机字符串，防止文件名泄露
2. **移除执行权限** - 自动移除上传文件的执行权限，防止恶意脚本执行
3. **文件大小限制** - 限制上传文件大小，防止 DoS 攻击
4. **读写分离** - 可选的读写端口分离，增强访问控制

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
