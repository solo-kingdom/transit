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

## 学习内容托管

把 HTML 学习页发布到服务上，按分类组织，发布后公开可浏览。

### 发布专题

```bash
# 发布（Docker 部署）
curl -X POST http://localhost:9200/learn/publish \
  -H "Authorization: Bearer <write-token>" \
  -H "Content-Type: application/json" \
  -d '{
    "category": "ai-agent",
    "slug": "my-article",
    "title": "文章标题",
    "desc": "卡片上的一句话摘要",
    "html": "<!DOCTYPE html><html lang=\"zh-CN\"><body><h1>正文</h1></body></html>",
    "tags": ["demo"],
    "date": "2026-10-17",
    "category_name": "AI Agent 体系"
  }'

# 返回示例
{"url":"http://localhost:9200/learn/ai-agent/my-article/","category_url":"http://localhost:9200/learn/ai-agent/"}
```

`category_name` 只在分类尚不存在时需要。`category` 与 `slug` 必须是 kebab-case。

### 浏览

```bash
# 索引页：列出全部分类与已发布专题
curl http://localhost:9200/learn/

# 分类页
curl http://localhost:9200/learn/ai-agent/

# 专题页：返回发布时的 HTML
curl http://localhost:9200/learn/ai-agent/my-article/

# 不带尾斜杠的分类路径会 307 重定向到带尾斜杠版本
curl -i http://localhost:9200/learn/ai-agent
```

三者都不需要凭据。

### 发布失败的情形

发布会在写入前校验分类结构与磁盘内容是否一致，写入后还会用索引页与分类页的渲染结果自检。以下情况会被拒绝：

- 缺少写凭据（401），或分类/专题标识不是 kebab-case（400）
- 分类不存在且未提供 `category_name`（400）
- 事实源里登记的专题在磁盘上不存在，或磁盘上有未登记的专题目录（400）
- 自检未通过（400）

被拒绝时不会留下半成品；替换已有专题时若中途失败，原内容会被恢复。

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
