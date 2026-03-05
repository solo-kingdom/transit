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
docker run -d -p 8000:8000 -v $(pwd)/data:/app/data transit:latest
```

### 方式 3: 本地开发

```bash
pip install -e .
python run_dev.py
```

或使用 FastAPI CLI：

```bash
fastapi dev src/transit/main.py
```

## 文件上传

### 方式 1: 使用 curl --upload-file（推荐）

```bash
# 上传文件
curl --upload-file myfile.txt http://localhost:8000/username

# 返回示例
{"message":"File uploaded successfully","download_path":"/username/AbCdEf123456","filename":"AbCdEf123456"}
```

### 方式 2: 使用 curl POST 方法

```bash
# 上传文件
curl -X POST -F "file=@myfile.txt" http://localhost:8000/username

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

# 上传文件
with open('myfile.txt', 'rb') as f:
    response = requests.post(
        'http://localhost:8000/username',
        files={'file': f}
    )
    
print(response.json())
# {'message': 'File uploaded successfully', 'download_path': '/username/AbCdEf123456.txt', 'filename': 'AbCdEf123456.txt'}
```

## 文件下载

### 方式 1: 使用 wget（推荐）

```bash
# 下载文件
wget http://localhost:8000/username/AbCdEf123456

# 或指定输出文件名
wget -O downloaded_file.txt http://localhost:8000/username/AbCdEf123456
```

### 方式 2: 使用 curl

```bash
# 下载文件
curl -O http://localhost:8000/username/AbCdEf123456

# 或指定输出文件名
curl -o downloaded_file.txt http://localhost:8000/username/AbCdEf123456
```

### 方式 3: 使用 Python

```python
import requests

# 下载文件
response = requests.get('http://localhost:8000/username/AbCdEf123456')

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

- Swagger UI: http://localhost:8000/docs
- ReDoc: http://localhost:8000/redoc

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
