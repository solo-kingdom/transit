#!/usr/bin/env python3
"""
文件中转服务管理工具
提供文件统计、清理等管理功能
"""

import argparse
import json
import sys
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, List, Optional


def get_data_dir() -> Path:
    """获取数据目录路径"""
    # 从环境变量或配置中获取
    import os

    data_dir = os.getenv("DATA_DIR", "/app/transit/data")
    return Path(data_dir)


def get_meta_files(data_dir: Path, username: Optional[str] = None) -> List[Path]:
    """
    获取所有 meta 文件

    Args:
        data_dir: 数据目录
        username: 用户名（可选，如果指定则只返回该用户的 meta 文件）

    Returns:
        meta 文件路径列表
    """
    meta_files = []

    if username:
        user_dir = data_dir / username
        if user_dir.exists():
            meta_files = list(user_dir.glob(".meta.*.json"))
    else:
        for user_dir in data_dir.iterdir():
            if user_dir.is_dir():
                meta_files.extend(user_dir.glob(".meta.*.json"))

    return meta_files


def load_meta(meta_file: Path) -> Optional[Dict]:
    """
    加载 meta 文件

    Args:
        meta_file: meta 文件路径

    Returns:
        meta 数据字典，如果加载失败则返回 None
    """
    try:
        with open(meta_file, "r", encoding="utf-8") as f:
            return json.load(f)
    except (json.JSONDecodeError, IOError):
        return None


def get_file_path_from_meta(meta_file: Path) -> Path:
    """
    从 meta 文件路径获取对应的文件路径

    Args:
        meta_file: meta 文件路径

    Returns:
        对应的文件路径
    """
    # meta 文件名格式：.meta.{filename}.json
    filename = meta_file.name[6:-5]  # 去掉 .meta. 和 .json
    return meta_file.parent / filename


def cmd_stats(args):
    """
    统计文件信息

    Args:
        args: 命令行参数
    """
    data_dir = get_data_dir()

    if not data_dir.exists():
        print(f"❌ 数据目录不存在: {data_dir}")
        sys.exit(1)

    # 获取 meta 文件
    meta_files = get_meta_files(data_dir, args.username)

    # 统计信息
    total_files = 0
    total_size = 0
    user_stats: Dict[str, Dict] = {}

    for meta_file in meta_files:
        meta = load_meta(meta_file)
        if not meta:
            continue

        username = meta.get("username", "unknown")
        file_size = meta.get("file_size", 0)

        # 更新总统计
        total_files += 1
        total_size += file_size

        # 更新用户统计
        if username not in user_stats:
            user_stats[username] = {
                "file_count": 0,
                "total_size": 0,
            }

        user_stats[username]["file_count"] += 1
        user_stats[username]["total_size"] += file_size

    # 输出统计结果
    print("\n" + "=" * 60)
    print("📊 文件统计信息")
    print("=" * 60)

    if args.username:
        print(f"\n👤 用户: {args.username}")
        if args.username in user_stats:
            stats = user_stats[args.username]
            print(f"   文件数: {stats['file_count']}")
            print(f"   总大小: {format_size(stats['total_size'])}")
        else:
            print("   无文件")
    else:
        print(f"\n📈 总体统计:")
        print(f"   总文件数: {total_files}")
        print(f"   总大小: {format_size(total_size)}")
        print(f"   用户数: {len(user_stats)}")

        if args.detail and user_stats:
            print(f"\n👥 用户统计:")
            for username, stats in sorted(user_stats.items()):
                print(f"   {username}:")
                print(f"      文件数: {stats['file_count']}")
                print(f"      总大小: {format_size(stats['total_size'])}")

    print("=" * 60 + "\n")


def cmd_clean(args):
    """
    清理文件

    Args:
        args: 命令行参数
    """
    data_dir = get_data_dir()

    if not data_dir.exists():
        print(f"❌ 数据目录不存在: {data_dir}")
        sys.exit(1)

    # 计算截止时间
    cutoff_time = None
    if args.days:
        cutoff_time = datetime.now() - timedelta(days=args.days)

    # 获取 meta 文件
    meta_files = get_meta_files(data_dir, args.username)

    deleted_files = 0
    deleted_size = 0
    errors = 0

    print("\n" + "=" * 60)
    print("🗑️  文件清理")
    print("=" * 60)

    if args.username:
        print(f"\n👤 目标用户: {args.username}")
    else:
        print(f"\n👥 目标: 所有用户")

    if cutoff_time:
        print(f"📅 时间范围: {cutoff_time.strftime('%Y-%m-%d %H:%M:%S')} 之前")
    else:
        print(f"📅 时间范围: 所有文件")

    if not args.force:
        print(f"\n⚠️  警告: 将要删除 {len(meta_files)} 个文件")
        confirm = input("确认删除? (yes/no): ")
        if confirm.lower() != "yes":
            print("❌ 取消删除")
            return

    for meta_file in meta_files:
        meta = load_meta(meta_file)
        if not meta:
            continue

        # 检查时间条件
        if cutoff_time:
            upload_time_str = meta.get("upload_time")
            if upload_time_str:
                try:
                    upload_time = datetime.fromisoformat(upload_time_str)
                    if upload_time > cutoff_time:
                        continue  # 跳过未过期的文件
                except ValueError:
                    pass

        # 删除文件和 meta 文件
        try:
            file_path = get_file_path_from_meta(meta_file)

            if file_path.exists():
                file_size = file_path.stat().st_size
                file_path.unlink()
                deleted_size += file_size
                deleted_files += 1

            if meta_file.exists():
                meta_file.unlink()
        except Exception as e:
            print(f"❌ 删除失败: {meta_file.name} - {e}")
            errors += 1

    print(f"\n✅ 清理完成:")
    print(f"   删除文件数: {deleted_files}")
    print(f"   释放空间: {format_size(deleted_size)}")

    if errors > 0:
        print(f"   错误数: {errors}")

    print("=" * 60 + "\n")


def cmd_list(args):
    """
    列出文件

    Args:
        args: 命令行参数
    """
    data_dir = get_data_dir()

    if not data_dir.exists():
        print(f"❌ 数据目录不存在: {data_dir}")
        sys.exit(1)

    # 获取 meta 文件
    meta_files = get_meta_files(data_dir, args.username)

    print("\n" + "=" * 60)
    print("📁 文件列表")
    print("=" * 60)

    if args.username:
        print(f"\n👤 用户: {args.username}")

    if not meta_files:
        print("\n   无文件")
    else:
        print()
        for meta_file in sorted(meta_files):
            meta = load_meta(meta_file)
            if not meta:
                continue

            print(f"   📄 {meta.get('encoded_filename', 'unknown')}")
            print(f"      原始文件名: {meta.get('original_filename', 'unknown')}")
            print(f"      大小: {format_size(meta.get('file_size', 0))}")
            print(f"      上传时间: {meta.get('upload_time', 'unknown')}")
            print(f"      来源 IP: {meta.get('remote_address', 'unknown')}")
            print()

    print("=" * 60 + "\n")


def format_size(size_bytes: int) -> str:
    """
    格式化文件大小

    Args:
        size_bytes: 字节数

    Returns:
        格式化后的大小字符串
    """
    for unit in ["B", "KB", "MB", "GB", "TB"]:
        if size_bytes < 1024.0:
            return f"{size_bytes:.2f} {unit}"
        size_bytes /= 1024.0
    return f"{size_bytes:.2f} PB"


def main():
    """主函数"""
    parser = argparse.ArgumentParser(
        description="文件中转服务管理工具",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
示例:
  # 统计所有文件信息
  python manage.py stats
  
  # 统计指定用户的文件信息
  python manage.py stats -u username
  
  # 统计所有用户的详细信息
  python manage.py stats --detail
  
  # 列出所有文件
  python manage.py list
  
  # 列出指定用户的文件
  python manage.py list -u username
  
  # 清理所有文件（需要确认）
  python manage.py clean
  
  # 清理指定用户的文件
  python manage.py clean -u username
  
  # 清理 7 天前的所有文件
  python manage.py clean --days 7
  
  # 清理指定用户 30 天前的文件
  python manage.py clean -u username --days 30
  
  # 强制清理（不需要确认）
  python manage.py clean --force
        """,
    )

    subparsers = parser.add_subparsers(dest="command", help="可用命令")

    # stats 命令
    stats_parser = subparsers.add_parser("stats", help="统计文件信息")
    stats_parser.add_argument("-u", "--username", help="指定用户名")
    stats_parser.add_argument("--detail", action="store_true", help="显示详细统计")
    stats_parser.set_defaults(func=cmd_stats)

    # clean 命令
    clean_parser = subparsers.add_parser("clean", help="清理文件")
    clean_parser.add_argument("-u", "--username", help="指定用户名")
    clean_parser.add_argument("--days", type=int, help="清理指定天数前的文件")
    clean_parser.add_argument("--force", action="store_true", help="强制删除，不需要确认")
    clean_parser.set_defaults(func=cmd_clean)

    # list 命令
    list_parser = subparsers.add_parser("list", help="列出文件")
    list_parser.add_argument("-u", "--username", help="指定用户名")
    list_parser.set_defaults(func=cmd_list)

    args = parser.parse_args()

    if not args.command:
        parser.print_help()
        sys.exit(1)

    # 执行命令
    args.func(args)


if __name__ == "__main__":
    main()
