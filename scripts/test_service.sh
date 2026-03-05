#!/bin/bash
#
# 快速测试脚本
# 用于验证文件中转服务是否正常工作
#

set -e

HOST="${1:-http://localhost:8000}"
TEST_FILE="/tmp/transit_test_$$"

echo "🧪 测试文件中转服务: $HOST"
echo "================================"

# 创建测试文件
echo "📝 创建测试文件..."
echo "Hello, Transit! Test file content." > "$TEST_FILE"

# 测试 1: 健康检查
echo ""
echo "1️⃣  测试健康检查..."
HEALTH=$(curl -s "$HOST/health")
if echo "$HEALTH" | grep -q "healthy"; then
    echo "✅ 健康检查通过"
else
    echo "❌ 健康检查失败"
    exit 1
fi

# 测试 2: 上传文件（PUT 方法）
echo ""
echo "2️⃣  测试文件上传（PUT 方法）..."
UPLOAD_RESPONSE=$(curl -s --upload-file "$TEST_FILE" "$HOST/testuser")
DOWNLOAD_URL=$(echo "$UPLOAD_RESPONSE" | grep -o '"download_url":"[^"]*"' | cut -d'"' -f4)
DOWNLOAD_PATH=$(echo "$UPLOAD_RESPONSE" | grep -o '"download_path":"[^"]*"' | cut -d'"' -f4)

if [ -n "$DOWNLOAD_URL" ] && [ -n "$DOWNLOAD_PATH" ]; then
    echo "✅ 文件上传成功"
    echo "   完整 URL: $DOWNLOAD_URL"
    echo "   下载路径: $DOWNLOAD_PATH"
else
    echo "❌ 文件上传失败"
    echo "   响应: $UPLOAD_RESPONSE"
    exit 1
fi

# 提取文件名
FILENAME=$(echo "$UPLOAD_RESPONSE" | grep -o '"filename":"[^"]*"' | cut -d'"' -f4)

# 测试 3: 下载文件
echo ""
echo "3️⃣  测试文件下载..."
DOWNLOADED_CONTENT=$(curl -s "$HOST$DOWNLOAD_PATH")
EXPECTED_CONTENT="Hello, Transit! Test file content."

if [ "$DOWNLOADED_CONTENT" = "$EXPECTED_CONTENT" ]; then
    echo "✅ 文件下载成功，内容匹配"
else
    echo "❌ 文件内容不匹配"
    echo "   期望: $EXPECTED_CONTENT"
    echo "   实际: $DOWNLOADED_CONTENT"
    exit 1
fi

# 测试 3.5: 查询文件元信息
echo ""
echo "3.5️⃣  测试查询文件元信息..."
META_RESPONSE=$(curl -s "$HOST/testuser/$FILENAME/meta")

if echo "$META_RESPONSE" | grep -q "upload_time" && \
   echo "$META_RESPONSE" | grep -q "remote_address" && \
   echo "$META_RESPONSE" | grep -q "file_size"; then
    echo "✅ 元信息查询成功"
    echo "   包含: 上传时间、来源 IP、文件大小"
else
    echo "❌ 元信息查询失败或不完整"
    echo "   响应: $META_RESPONSE"
    exit 1
fi

# 测试 4: 上传文件（POST 方法）
echo ""
echo "4️⃣  测试文件上传（POST 方法）..."
POST_RESPONSE=$(curl -s -X POST -F "file=@$TEST_FILE" "$HOST/testuser2")
POST_DOWNLOAD_URL=$(echo "$POST_RESPONSE" | grep -o '"download_url":"[^"]*"' | cut -d'"' -f4)
POST_DOWNLOAD_PATH=$(echo "$POST_RESPONSE" | grep -o '"download_path":"[^"]*"' | cut -d'"' -f4)

if [ -n "$POST_DOWNLOAD_URL" ] && [ -n "$POST_DOWNLOAD_PATH" ]; then
    echo "✅ POST 上传成功"
    echo "   完整 URL: $POST_DOWNLOAD_URL"
    echo "   下载路径: $POST_DOWNLOAD_PATH"
else
    echo "❌ POST 上传失败"
    exit 1
fi

# 测试 5: 下载不存在的文件
echo ""
echo "5️⃣  测试下载不存在的文件..."
NOT_FOUND=$(curl -s -o /dev/null -w "%{http_code}" "$HOST/nonexistent/file.txt")

if [ "$NOT_FOUND" = "404" ]; then
    echo "✅ 正确返回 404"
else
    echo "❌ 应该返回 404，实际返回: $NOT_FOUND"
    exit 1
fi

# 清理
rm -f "$TEST_FILE"

echo ""
echo "================================"
echo "🎉 所有测试通过！"
echo ""
echo "快速使用示例:"
echo "  上传: curl --upload-file myfile.txt $HOST/username"
echo "  下载: wget $HOST/username/encoded_filename"
