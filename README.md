# Transit - 文件中转服务

一个安全、便捷的文件中转服务，解决多地域网络连通、内外网安全性等问题。

## 特性

- 🔒 **读写分离** - 支持读写端口分离，增强安全性
- 🐳 **一体化镜像** - Caddy 已集成到镜像中，简化部署
- 🔐 **Token 认证** - 支持读写分离的 token 认证，可配置多个 token
- 🎲 **UUID 文件名** - 使用 UUID 生成唯一文件名，保护隐私
- 🔗 **访问命名空间** - `/public` 与 `/pages` 公开可读；`/protect` 需资源级 token；上传默认 `/protect`
- 🤖 **Agent Skill** - 仓内 `.agents/skills/transit/SKILL.md`；运行中 `GET /skill.md`，根路径嵌入同一文件
- ⏳ **可设有效期** - 上传时可指定保留时长，过期后链接返回 `410 Gone`；默认永不过期
- 📄 **按类型展示** - 文本、图片、音视频与 PDF 在浏览器直接展示或播放，其余触发下载；音视频支持分段请求（Range）
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

4. 停止服务

```bash
docker-compose down
```

**端口说明**：

- `9200`: 服务端口（同时支持读写，推荐使用）
- `9201`: Caddy 读端口（仅允许 GET/HEAD 方法）
- `9202`: Caddy 写端口（仅允许 POST/PUT 方法）

**常用操作**：

```bash
# 查看运行状态
docker-compose ps

# 重启服务
docker-compose restart

# 停止并删除容器
docker-compose down

# 停止并删除容器、网络、镜像
docker-compose down --rmi all

# 进入容器
docker exec -it transit bash

# 查看实时日志
docker-compose logs -f

# 查看最近 100 行日志
docker-compose logs --tail=100
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
  -p 9201:9201 \
  -p 9202:9202 \
  -p 9200:9200 \
  -v $(pwd)/data:/app/data \
  transit:latest
```

**端口说明**：

- `9200`: 服务端口（同时支持读写，推荐使用）
- `9201`: 读端口（仅允许 GET/HEAD 方法）
- `9202`: 写端口（仅允许 POST/PUT 方法）

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
curl --upload-file /path/to/file http://localhost:9200
```

返回示例：

```json
{
  "download_url": "http://192.168.1.100:9200/protect/8Kd2mQx1vTb7nR4pZ0aLcA/file.txt"
}
```

**注意**：

- `download_url` 包含完整的 URL（包含自动检测的本机 IP 或配置的 host）
- 默认走 **`/protect/{token}/...`**：中间一段是该文件专属访问凭据，拿到链接即可取，不必再带全局认证头
- 需要公开文件时传 `path=/public` 或 `protected=false`，得到 `/public/{encoded}/...`
- 旧链接 `/f/{token}/...` 仍可用，语义同 `/protect`

### 设置有效期

上传时可选传 `expires_in`（秒，正整数），**不传则永不过期**。POST 用表单字段，PUT 用 query 参数（PUT 的请求体就是文件本身）：

```bash
# POST：保留 1 小时
curl -X POST http://localhost:9200/ -F file=@report.pdf -F expires_in=3600

# PUT：保留 7 天
curl -T report.pdf "http://localhost:9200/report.pdf?expires_in=604800"
```

设置成功时，上传响应会多一个 `expires_at`（ISO 时间）：

```json
{
  "download_url": "http://localhost:9200/protect/8Kd2mQx1vTb7nR4pZ0aLcA/report.pdf",
  "expires_at": "2026-10-19T20:35:09"
}
```

- 过期后，访问链接与按编码名下载 / 查元信息都返回 **`410 Gone`**（区分「过期」与「不存在」的 404）
- 过期文件不会被自动删除，需要空间时可再用 `scripts/manage.py clean --days N` 清理
- `expires_in` 不是正整数时返回 `400`
- 升级前上传、元信息里没有 `expires_at` 的老文件视为永不过期

### 访问文件

把返回的 `download_url` 直接交给浏览器、wget 或 curl 即可：

```bash
# wget
wget http://localhost:9200/protect/8Kd2mQx1vTb7nR4pZ0aLcA/file.txt

# curl
curl -O http://localhost:9200/protect/8Kd2mQx1vTb7nR4pZ0aLcA/file.txt
```

**返回处置按内容类型决定**：

| 内容类型 | 行为 |
| -------- | ---- |
| `text/*`（含 HTML）、`image/*`（矢量图除外）、`video/*`、`audio/*`、`application/pdf` | 内联展示（浏览器直接渲染 / 播放） |
| `image/svg+xml`、压缩包及其余二进制 | 触发下载 |

内容类型以**文件名扩展名**为准：上传方在请求里声明的类型不会覆盖它，避免用改扩展名的方式让任意内容变成可执行的 HTML。

音视频支持分段请求（HTTP Range），可在播放器里拖动进度。

### 查询文件元信息

获取文件的详细元信息：

```bash
curl http://localhost:9200/AbCdEf123456.txt/file.txt/meta
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
    "content_type": "text/plain"
  }
}
```

**注意**：该接口按编码文件名定位，而上传返回的链接只带访问凭据、不再暴露编码文件名。要查元信息需另行知道编码文件名（例如从服务日志里取）。响应中**不含访问凭据**，避免持有全局读 token 的人把每个文件的凭据读出来。

### API 端点

- `POST /` - 上传文件（multipart；可选 `expires_in` / `path` / `protected`）
- `PUT /` 和 `PUT /{upload_path}` - 上传文件（裸 body；可选 query `expires_in` / `path` / `protected`）
- `GET /protect/{token}/{original_filename}` - 受保护文件（上传默认返回形态）
- `GET /public/{encoded_filename}/{original_filename}` - 公开文件
- `GET /f/{token}/{original_filename}` - `/protect` 的兼容别名
- `GET /protect/{token}/{category}/{slug}/` - 受保护页面入口
- `GET /{encoded_filename}/{original_filename}` - 按编码文件名下载文件（旧链接，仍可用）
- `GET /{encoded_filename}/{original_filename}/meta` - 获取文件元信息
- `POST /pages/publish` - 发布页面，单文件传 HTML 字符串、带资源传 zip 包（需写凭据）
- `POST /pages/assets` - 发布共享资源（需写凭据）
- `GET /pages/` - 页面站索引页（公开，无需凭据）
- `GET /pages/{category}/` - 页面站分类页（公开）
- `GET /pages/{category}/{slug}/` - 页面入口（公开）
- `GET /pages/{category}/{slug}/{资源路径}` - 页面内的静态资源（公开）
- `GET /pages/assets/{资源路径}` - 共享资源（公开）
- `GET /` - 根路径产品说明页（中英文，`?lang=en` 切英文）
- `GET /health` - 健康检查
- `GET /skill.md`（别名 `/skill`）- Agent Skill 原文（与根路径嵌入、仓内 `.agents/skills/transit/SKILL.md` 同一文件）

### 页面托管

服务可以托管按分类组织的 HTML 页面：默认发布到 `/pages` 公开可浏览；也可 `protected=true` 或 `path=/protect` 发布到受保护命名空间。一个页面就是一个目录，可以带任意静态资源；多个页面共用集中存放的共享资源。

**发布单文件页面**（只有 HTML，没有别的资源）：

```bash
curl -X POST http://localhost:9200/pages/publish \
  -H "Authorization: Bearer <write-token>" \
  -F category=guide \
  -F slug=getting-started \
  -F title=上手指南 \
  -F desc=卡片上的一句话摘要 \
  -F category_name=指南 \
  --form-string html='<!DOCTYPE html><html lang="zh-CN"><body><h1>正文</h1></body></html>'
```

> HTML 字段用 `--form-string` 而不是 `-F`：`-F` 里以 `<` 开头的值会被 curl 当成「从文件读取」，会直接报错或读到别的内容。也可以写成 `-F 'html=<page.html'` 明确从文件读。

**发布带资源的页面（多文件一次上传）**：把页面目录打成 zip，入口固定 `index.html`。  
这是 **HTML + 静态资源作为一次上传** 的正路径——公开走 `/pages`，受保护加 `protected=true`（或 `path=/protect`），**一个 token 罩住整包**，不另做文件侧 bundle API。

```bash
# 目录结构：page/index.html、page/style.css、page/assets/logo.png
cd page && zip -r ../page.zip . && cd ..

# 公开多文件页
curl -X POST http://localhost:9200/pages/publish \
  -H "Authorization: Bearer <write-token>" \
  -F category=guide \
  -F slug=with-assets \
  -F title=带资源的页面 \
  -F desc=一句话摘要 \
  -F category_name=指南 \
  -F bundle=@page.zip

# 受保护多文件页（同一 zip，多一个 protected）
curl -X POST http://localhost:9200/pages/publish \
  -H "Authorization: Bearer <write-token>" \
  -F category=guide \
  -F slug=private-site \
  -F title=私享页 \
  -F desc=一句话摘要 \
  -F category_name=指南 \
  -F protected=true \
  -F bundle=@page.zip
```

相对路径引用资源即可：

- 公开：`./style.css` → `/pages/guide/with-assets/style.css`
- 受保护：`./style.css` → `/protect/{token}/guide/private-site/style.css`（与入口共用同一 token）

受保护响应示例：

```json
{
  "url": "http://localhost:9200/protect/<token>/guide/private-site/",
  "category_url": "http://localhost:9200/pages/guide/",
  "token": "<token>"
}
```

公开响应则是 `/pages/guide/with-assets/`，无 `token` 字段。受保护页**不出现在** `/pages/` 索引，也不能从 `/pages/{cat}/{slug}/` 绕过。

**发布共享资源**（所有页面都能用绝对路径 `/pages/assets/<路径>` 引用）：

```bash
curl -X POST http://localhost:9200/pages/assets \
  -H "Authorization: Bearer <write-token>" \
  -F path=theme/main.css \
  -F file=@main.css
```

`category_name` 只在分类尚不存在时需要；分类已存在时忽略。

**浏览**：打开返回的 `url` 即页面；公开站还有 `/pages/` 索引与 `/pages/<category>/` 分类页。

**约定与行为**：

- `category` 与 `slug` 必须是 kebab-case（小写字母、数字与连字符）；`assets` 是共享资源的保留分类名
- 公开路径一律带尾斜杠；不带尾斜杠的 `/pages/<category>` 会重定向到带尾斜杠版本
- 发布时会校验分类结构与磁盘内容一致（登记了却没有文件、有文件却没登记，都会拒绝发布）；公开页还会用索引/分类渲染做自检
- 替换已有页面是原子的；若发布中途失败，原内容会被恢复，不会把已发布的页面弄丢
- 页面存在数据目录的 `pages/` 子目录下，与普通上传的文件分开
- **资源访问有边界**：每个资源请求解析出的真实路径必须落在该页面自己的目录（共享资源则限于共享资源目录）内。`..` 上跳、绝对路径、符号链接逃逸一律拒绝
- 写凭据持有者可直接发布；默认进公开 `/pages`，需要链接自足保密时用 `protected=true`

## 配置

### 环境变量

| 变量名                   | 说明                      | 默认值               |
| ------------------------ | ------------------------- | -------------------- |
| `APP_NAME`               | 应用名称                  | File Transit Service |
| `APP_VERSION`            | 应用版本                  | 0.1.0                |
| `DATA_DIR`               | 数据存储路径              | /app/transit/data    |
| `PORT`                   | 服务端口（内部）          | 8000                 |
| `DOWNLOAD_HOST`          | 下载 URL 的主机地址       | 自动检测本机 IP      |
| `MAX_FILE_SIZE`          | 最大文件大小（字节）      | 5368709120 (5GB)     |
| `REMOVE_EXEC_PERMISSION` | 移除执行权限              | true                 |
| `AUTH_ENABLED`           | 是否启用认证              | false                |
| `READ_TOKENS`            | 读 token 列表（逗号分隔） | -                    |
| `WRITE_TOKENS`           | 写 token 列表（逗号分隔） | -                    |

**端口说明**：

- 镜像内部 transit 服务监听 `127.0.0.1:9000`
- Caddy 作为反向代理，暴露三个端口：
  - `9202`: 写端口（仅允许 POST/PUT）
  - `9201`: 读端口（仅允许 GET/HEAD）
  - `9200`: 服务端口（同时支持所有方法）

**DOWNLOAD_HOST 配置说明**：

- 如果不设置，系统会自动检测本机 IP 地址
- 可以设置为域名（如 `example.com`）或 IP 地址（如 `192.168.1.100`）
- 在容器环境或反向代理后，建议显式设置此参数

### 认证配置

默认不开启认证（`AUTH_ENABLED=false`），任何人都能上传。开启后，**上传、发布页面、按旧路径下载与查询元信息**都需要携带预设 token。

```bash
# 启用认证
export AUTH_ENABLED=true
export READ_TOKENS=read123,read456
export WRITE_TOKENS=write123,write456
```

token 可从四个位置传入，按以下顺序命中第一个非空值，四种传法完全等价：

| 顺序 | 位置 | 示例 |
| --- | --- | --- |
| 1 | `Authorization` 头 | `-H "Authorization: Bearer write123"` |
| 2 | `X-Auth-Token` 头 | `-H "X-Auth-Token: write123"` |
| 3 | 表单字段 `token` | `-F token=write123`（multipart / urlencoded） |
| 4 | 查询参数 `token` | `?token=write123` |

```bash
# 上传文件（写 token，任选一种传法）
curl -H "Authorization: Bearer write123" --upload-file file.txt http://localhost:9200/
curl -H "X-Auth-Token: write123" --upload-file file.txt http://localhost:9200/
curl --upload-file file.txt "http://localhost:9200/?token=write123"
curl -F token=write123 -F file=@file.txt http://localhost:9200/

# 下载文件（读 token，旧路径）
curl -H "Authorization: Bearer read123" http://localhost:9200/AbCdEf123456.txt/filename
```

**认证说明**：

- `READ_TOKENS`：按编码文件名下载（旧路径）与查询 `/meta` 时使用（**meta 受保护状态不变**）
- `WRITE_TOKENS`：上传文件、发布页面 / 共享资源时使用
- 多个 token 用逗号分隔；命中第一个非空来源即用它校验，不叠加
- 缺凭据返回 `401 Missing authentication token`，凭据不在白名单返回 `401 Invalid <read|write> token`
- 裸 body 的 `PUT /{upload_path}` 上传请求体就是文件本身，鉴权不会去读它，因此只能走请求头或 query，不能用表单 `token`
- `/protect/{token}/...`（及旧 `/f/...`）**不需要**全局读 token：路径里的凭据就是访问方式
- `/public/...` 与 `/pages/...` 公开可读；受保护页面不得从 `/pages/{cat}/{slug}/` 绕过
- ⚠️ query 传写 token 会进入访问日志、浏览器历史与 `Referer`，仅在确实不便设头 / 表单时使用

### 多文件（HTML + 静态资源）怎么传

| 场景 | 做法 |
| --- | --- |
| 单文件（任意类型） | `POST /` / `PUT /`，默认 `/protect/{token}/文件名` |
| HTML + 若干静态资源，一次上传 | `POST /pages/publish` + `bundle=@site.zip`；要保密则再加 `protected=true` |
| 不要做 | 对每个资源各传一次 `POST /` 再手拼链接（token 对不齐，相对路径也断） |

### 访问路径与 `protected` 参数

上传文件（POST 表单 / PUT query）与发布页面（表单）均可选传：

| 参数 | 含义 |
| --- | --- |
| `path` | 访问命名空间：文件用 `/public` 或 `/protect`；页面用 `/pages` 或 `/protect` |
| `protected` | 是否受保护（`true` / `false`） |

规则（二者皆可选）：

| path | protected | 结果 |
| --- | --- | --- |
| 省略 | 省略 | 文件 → `/protect`；页面 → `/pages` |
| 有 | 省略 | 由前缀推算是否保护 |
| 省略 | 有 | `true`→`/protect`；`false`→文件 `/public` / 页面 `/pages` |
| 有 | 有 | 必须一致，否则 `400` |

```bash
# 默认受保护
curl -F file=@a.txt http://localhost:9200/

# 公开文件
curl -F file=@a.txt -F path=/public http://localhost:9200/
curl -F file=@a.txt -F protected=false http://localhost:9200/

# 受保护页面
curl -F category=guide -F slug=private -F title=密 -F desc=摘要 \
  -F html='<h1>hi</h1>' -F category_name=指南 -F protected=true \
  http://localhost:9200/pages/publish
```

### 读写分离架构

服务默认启用读写分离，通过 Caddy 反向代理实现：

**端口说明**：

- **9202 端口（写端口）**：仅允许 POST/PUT 方法
  - 用于上传文件
  - 自动拒绝 GET/HEAD 请求（除了 /health 和 / 路径）
- **9201 端口（读端口）**：仅允许 GET/HEAD 方法
  - 用于下载文件和查询元信息
  - 自动拒绝 POST/PUT 请求
- **9200 端口（服务端口）**：同时支持所有方法
  - 适用于需要完整功能的场景
  - 不限制请求方法
  - 推荐使用此端口

**使用示例**：

```bash
# 使用写端口上传文件
curl --upload-file file.txt http://localhost:9202/user

# 使用读端口下载文件
curl http://localhost:9201/user/filename

# 使用服务端口（完整功能，推荐）
curl --upload-file file.txt http://localhost:9200/user
curl http://localhost:9200/user/filename
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
