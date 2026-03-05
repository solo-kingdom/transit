#!/bin/bash
#
# 新功能测试脚本
# 演示完整 URL 和元信息查询功能
#

set -e

HOST="${1:-http://localhost:8000}"
TEST_FILE="/tmp/transit_feature_test_$$"

echo "🧪 测试新功能: 完整 URL 和元信息管理"
echo "========================================"
echo "服务地址: $HOST"
echo ""

# 创建测试文件
echo "📝 创建测试文件..."
echo "Testing new features: complete URL and metadata management" > "$TEST_FILE"

# 测试 1: 上传文件并检查返回的完整 URL
echo ""
echo "1️⃣  测试上传文件（返回完整 URL）..."
RESPONSE=$(curl -s --upload-file "$TEST_FILE" "$HOST/testuser")
echo "响应: $RESPONSE"

# 提取 download_url
DOWNLOAD_URL=$(echo "$RESPONSE" | grep -o '"download_url":"[^"]*"' | cut -d'"' -f4)
echo ""
echo "✅ 完整下载 URL: $DOWNLOAD_URL"

# 检查 URL 格式
if [[ $DOWNLOAD_URL == http://* ]]; then
    echo "✅ URL 格式正确（包含协议）"
else
    echo "❌ URL 格式错误（应包含 http://）"
    exit 1
fi

# 测试 2: 查询元信息
echo ""
echo "2️⃣  测试查询文件元信息..."

# 从 DOWNLOAD_URL 中解析 encoded 和 original
REL_PATH="${DOWNLOAD_URL#*://*/}"
ENCODED="$(echo "$REL_PATH" | cut -d'/' -f1)"
ORIGINAL="$(echo "$REL_PATH" | cut -d'/' -f2-)"

META_RESPONSE=$(curl -s "$HOST/$ENCODED/$ORIGINAL/meta")
echo "元信息: $META_RESPONSE"

# 验证元信息字段
if echo "$META_RESPONSE" | grep -q "upload_time"; then
    echo "✅ 包含上传时间"
else
    echo "❌ 缺少上传时间"
    exit 1
fi

if echo "$META_RESPONSE" | grep -q "remote_address"; then
    echo "✅ 包含来源 IP"
else
    echo "❌ 缺少来源 IP"
    exit 1
fi

if echo "$META_RESPONSE" | grep -q "file_size"; then
    echo "✅ 包含文件大小"
else
    echo "❌ 缺少文件大小"
    exit 1
fi

# 测试 3: 使用完整 URL 下载
echo ""
echo "3️⃣  测试使用完整 URL 下载..."
DOWNLOADED=$(curl -s "$DOWNLOAD_URL")
EXPECTED="Testing new features: complete URL and metadata management"

if [ "$DOWNLOADED" = "$EXPECTED" ]; then
    echo "✅ 使用完整 URL 下载成功，内容正确"
else
    echo "❌ 下载内容不匹配"
    exit 1
fi

# 清理
rm -f "$TEST_FILE"

echo ""
echo "========================================"
echo "🎉 所有新功能测试通过！"
echo ""
echo "功能说明:"
echo "  - download_url: 包含完整主机地址的下载链接"
echo "  - meta 接口: 查询文件上传时间、来源 IP、大小等信息"
echo "  - 自动检测: 未配置 DOWNLOAD_HOST 时自动获取本机 IP"
