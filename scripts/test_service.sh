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

if [ -n "$DOWNLOAD_URL" ]; then
    echo "✅ 文件上传成功"
    echo "   完整 URL: $DOWNLOAD_URL"
else
    echo "❌ 文件上传失败"
    echo "   响应: $UPLOAD_RESPONSE"
    exit 1
fi

# 测试 3: 下载文件
echo ""
echo "3️⃣  测试文件下载..."
DOWNLOADED_CONTENT=$(curl -s "$DOWNLOAD_URL")
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

# 从 DOWNLOAD_URL 中解析 encoded 和 original
REL_PATH="${DOWNLOAD_URL#*://*/}"
ENCODED="$(echo "$REL_PATH" | cut -d'/' -f1)"
ORIGINAL="$(echo "$REL_PATH" | cut -d'/' -f2-)"

META_RESPONSE=$(curl -s "$HOST/$ENCODED/$ORIGINAL/meta")

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
POST_RESPONSE=$(curl -s -X POST -F "file=@$TEST_FILE" "$HOST")
POST_DOWNLOAD_URL=$(echo "$POST_RESPONSE" | grep -o '"download_url":"[^"]*"' | cut -d'"' -f4)

if [ -n "$POST_DOWNLOAD_URL" ]; then
    echo "✅ POST 上传成功"
    echo "   完整 URL: $POST_DOWNLOAD_URL"
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
echo "  上传: curl --upload-file myfile.txt $HOST"
echo "  下载: wget \$DOWNLOAD_URL"
