# 使用示例

本文档提供文件中转服务的详细使用示例。

## 启动服务

### 方式 1: 使用 Docker Compose（推荐）

```bash
docker-compose up -d
```

### 方式 2: 使用 Docker

```bash
docker build -t transit:latest .
docker run -d -p 9201:9201 -p 9202:9202 -p 9200:9200 -v $(pwd)/data:/app/data transit:latest
```

**端口说明**：
- `9200`: 服务端口（同时支持读写，推荐使用）
- `9201`: 读端口（仅 GET/HEAD）
- `9202`: 写端口（仅 POST/PUT）

### 方式 3: 本地开发

```bash
pip install -e .
python run_dev.py
```

或使用 FastAPI CLI：

```bash
fastapi dev src/transit/main.py
```

## 页面托管

把 HTML 页面发布到服务上，按分类组织，发布后公开可浏览。一个页面就是一个目录，可以带静态资源；多个页面共用集中存放的共享资源。

### 发布单文件页面

```bash
curl -X POST http://localhost:9200/pages/publish \
  -H "Authorization: Bearer <write-token>" \
  -F category=guide \
  -F slug=getting-started \
  -F title=上手指南 \
  -F desc=一句话摘要 \
  -F category_name=指南 \
  --form-string html='<!DOCTYPE html><html lang="zh-CN"><body><h1>正文</h1></body></html>'

# 返回示例
{"url":"http://localhost:9200/pages/guide/getting-started/","category_url":"http://localhost:9200/pages/guide/"}
```

HTML 字段用 `--form-string` 而不是 `-F`：`-F` 里以 `<` 开头的值会被 curl 当成「从文件读取」（curl 直接报错退出 26），想从文件读可以显式写 `-F 'html=<page.html'`。

### 发布带资源的页面

把页面目录打成 zip 传上去。包内即页面目录，入口固定为 `index.html`，其余文件按原相对路径落盘。

```bash
# page/index.html、page/style.css、page/assets/logo.png
cd page && zip -r ../page.zip . && cd ..

curl -X POST http://localhost:9200/pages/publish \
  -H "Authorization: Bearer <write-token>" \
  -F category=guide \
  -F slug=with-assets \
  -F title=带资源的页面 \
  -F desc=一句话摘要 \
  -F category_name=指南 \
  -F bundle=@page.zip

# 页面内 ./style.css 会解析到这里
curl http://localhost:9200/pages/guide/with-assets/style.css
```

`category_name` 只在分类尚不存在时需要。`category` 与 `slug` 必须是 kebab-case，`assets` 是保留分类名。

### 发布共享资源

共享资源集中放在 `/pages/assets/` 下，所有页面用绝对路径引用，彼此之间不互相引用。

```bash
curl -X POST http://localhost:9200/pages/assets \
  -H "Authorization: Bearer <write-token>" \
  -F path=theme/main.css \
  -F file=@main.css

# 页面里这样引用：<link rel="stylesheet" href="/pages/assets/theme/main.css">
curl http://localhost:9200/pages/assets/theme/main.css
```

### 浏览

```bash
# 索引页：列出全部分类与已发布页面
curl http://localhost:9200/pages/

# 分类页
curl http://localhost:9200/pages/guide/

# 页面入口：返回发布时的 HTML
curl http://localhost:9200/pages/guide/getting-started/

# 不带尾斜杠的分类路径会 307 重定向到带尾斜杠版本
curl -i http://localhost:9200/pages/guide
```

都不需要凭据。

### 资源访问的边界

每个资源请求解析出的真实路径必须落在该页面自己的目录内（共享资源则限于共享资源目录）。以下请求一律 404：

- 用 `..` 上跳去读别的页面或数据目录（含写成 `%2e%2e`、`..%2F` 的编码形式）
- 绝对路径
- 页面目录内指向根外的符号链接

这条边界不是可选项：数据目录里的 `.meta.<文件名>.json` 存着每个上传文件的访问凭据，页面路由能读到它就等于凭据泄露。

### 发布失败的情形

发布会在写入前校验分类结构与磁盘内容是否一致，写入后还会用索引页与分类页的渲染结果自检。以下情况会被拒绝：

- 缺少写凭据（401），或分类/页面标识不是 kebab-case、分类名用了保留的 `assets`（400）
- 分类不存在且未提供 `category_name`（400）
- `html` 与 `bundle` 同时给或都没给（400）
- zip 根目录下没有 `index.html`，成员路径含 `..` 或绝对路径，或含符号链接成员（400）
- 事实源里登记的页面在磁盘上不存在，或磁盘上有未登记的页面目录（400）
- 自检未通过（400）

被拒绝时不会留下半成品；替换已有页面时若中途失败，原内容会被恢复。

## 文件上传

**注意**：以下示例使用端口 `8000`（本地开发）。Docker 部署请使用 `9200`（服务端口）或 `9202`（写端口）。

### 方式 1: 使用 curl --upload-file（推荐）

```bash
# 上传文件（本地开发）
curl --upload-file myfile.txt http://localhost:8000

# 上传文件（Docker 部署）
curl --upload-file myfile.txt http://localhost:9200

# 返回示例（简化）
{"download_url":"http://localhost:9200/f/8Kd2mQx1vTb7nR4pZ0aLcA/myfile.txt"}
```

返回链接中间那段是该文件专属的访问凭据。拿到链接就能取到文件，不需要再带认证头，服务开启认证时也一样。

### 方式 2: 使用 curl POST 方法

```bash
# 上传文件（本地开发）
curl -X POST -F "file=@myfile.txt" http://localhost:8000

# 上传文件（Docker 部署）
curl -X POST -F "file=@myfile.txt" http://localhost:9200

# 返回示例
{"message":"File uploaded successfully","download_path":"/username/XyZ789.txt","filename":"XyZ789.txt"}
```

### 方式 3: 使用 wget

```bash
# wget 不支持文件上传，请使用 curl 或其他工具
```

### 方式 4: 使用 Python

```python
import requests

# 上传文件（本地开发）
with open('myfile.txt', 'rb') as f:
    response = requests.post(
        'http://localhost:8000',
        files={'file': f}
    )

# 上传文件（Docker 部署）
with open('myfile.txt', 'rb') as f:
    response = requests.post(
        'http://localhost:9200',
        files={'file': f}
    )
    
print(response.json())
# {'message': 'File uploaded successfully', 'download_path': '/username/AbCdEf123456.txt', 'filename': 'AbCdEf123456.txt'}
```

## 访问文件

**注意**：以下示例使用端口 `8000`（本地开发）。Docker 部署请使用 `9200`（服务端口）或 `9201`（读端口）。

访问地址就是上传返回的 `download_url`，其中的凭据段按实际返回的替换。

### 返回处置按内容类型决定

| 内容类型 | 行为 |
| -------- | ---- |
| `text/*`（含 HTML）、`image/*`（矢量图除外）、`video/*`、`audio/*`、`application/pdf` | 内联展示 |
| `image/svg+xml`、压缩包及其余二进制 | 触发下载 |

内容类型以文件名扩展名判定，上传请求里声明的类型不覆盖它。音视频支持分段请求，可在播放器里拖动进度。

### 方式 1: 使用 wget

```bash
# 访问文件（本地开发）
wget http://localhost:8000/f/8Kd2mQx1vTb7nR4pZ0aLcA/myfile.txt

# 访问文件（Docker 部署）
wget http://localhost:9200/f/8Kd2mQx1vTb7nR4pZ0aLcA/myfile.txt

# 或指定输出文件名
wget -O downloaded_file.txt http://localhost:9200/f/8Kd2mQx1vTb7nR4pZ0aLcA/myfile.txt
```

### 方式 2: 使用 curl

```bash
# 访问文件（本地开发）
curl -O http://localhost:8000/f/8Kd2mQx1vTb7nR4pZ0aLcA/myfile.txt

# 访问文件（Docker 部署）
curl -O http://localhost:9200/f/8Kd2mQx1vTb7nR4pZ0aLcA/myfile.txt

# 只取前 1KB（分段请求，音视频拖动进度走的就是这个）
curl -H "Range: bytes=0-1023" http://localhost:9200/f/8Kd2mQx1vTb7nR4pZ0aLcA/myfile.txt
```

### 方式 3: 使用 Python

```python
import requests

# 访问文件（本地开发）
response = requests.get('http://localhost:8000/f/8Kd2mQx1vTb7nR4pZ0aLcA/myfile.txt')

# 访问文件（Docker 部署）
response = requests.get('http://localhost:9200/f/8Kd2mQx1vTb7nR4pZ0aLcA/myfile.txt')

# 保存到本地
with open('downloaded_file.txt', 'wb') as f:
    f.write(response.content)
```

## 完整工作流程示例

### 场景 1: 在不同服务器间传输文件

**服务器 A（上传）:**
```bash
# 上传文件到中转服务
curl --upload-file large_data.tar.gz http://transit.example.com/team-alpha

# 返回
{"message":"File uploaded successfully","download_path":"/team-alpha/RandomString123","filename":"RandomString123"}
```

**服务器 B（下载）:**
```bash
# 从中转服务下载文件
wget http://transit.example.com/team-alpha/RandomString123
```

### 场景 2: 分享临时文件

1. 上传文件：
```bash
curl --upload-file document.pdf http://transit.example.com/share
# 返回: /share/XyZ789AbCdEf
```

2. 分享下载链接：
```
http://transit.example.com/share/XyZ789AbCdEf
```

3. 接收方下载：
```bash
wget http://transit.example.com/share/XyZ789AbCdEf
```

## API 文档

启动服务后，访问以下地址查看交互式 API 文档：

**本地开发**：
- Swagger UI: http://localhost:8000/docs
- ReDoc: http://localhost:8000/redoc

**Docker 部署**：
- Swagger UI: http://localhost:9200/docs
- ReDoc: http://localhost:9200/redoc

## 常见问题

### Q: 文件大小限制是多少？

A: 默认限制为 100MB。可以通过环境变量 `MAX_FILE_SIZE` 调整。

### Q: 文件会保存多久？

A: 文件会永久保存，直到手动删除。建议定期清理 `data` 目录。

### Q: 如何限制访问权限？

A: 
1. 使用读写端口分离（修改 docker-compose.yml）
2. 配置防火墙规则
3. 添加反向代理进行认证

### Q: 文件名编码有什么作用？

A: 
1. 保护原始文件名隐私
2. 防止文件名冲突
3. 增加安全性（难以猜测）

### Q: 如何备份文件？

A: 直接备份 `data` 目录即可：
```bash
tar -czf backup.tar.gz data/
```

## 高级配置

### 自定义数据目录

```bash
export DATA_DIR=/path/to/custom/data
python run_dev.py
```

### 修改文件大小限制

```bash
export MAX_FILE_SIZE=209715200  # 200MB
python run_dev.py
```

### 禁用执行权限移除

```bash
export REMOVE_EXEC_PERMISSION=false
python run_dev.py
```
