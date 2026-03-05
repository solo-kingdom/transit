1. 文件上传: 可以在配置中指定下载 host，默认读取当前机器 ip，返回下载的完整 url
   wii 🌐 msa ~ via 🐍 v3.13.3 on ☁️ (us-east-1) ❯ curl -T check.py 127.0.0.1:8000/szk
   % Total % Received % Xferd Average Speed Time Time Time Current
   Dload Upload Total Spent Left Speed
   100 991 100 122 100 869 11713 83437 0
   {"message":"File uploaded successfully","download_path":"/szk/\_uKVaIxKlroMpOEWO4sSlg","filename":"\_uKVaIxKlroMpOEWO4sSlg"}%

2. 为每个文件生成对应的 meta 信息，保存上传时间、remote address
   等必要信息，并提供查询接口（和读文件相同的权限控制）
