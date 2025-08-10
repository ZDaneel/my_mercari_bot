#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Mercari Bot 日志查看工具
用于分析生产环境中的日志文件，帮助定位通知问题
"""

import os
import sys
import re
from pathlib import Path
from datetime import datetime, timedelta
import argparse

def print_header():
    """打印工具头部信息"""
    print("="*70)
    print("📋 MERCARI BOT 日志查看工具")
    print("="*70)
    print(f"📅 当前时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("="*70)

def find_log_files():
    """查找日志文件"""
    log_files = []
    
    # 查找logs目录
    logs_dir = Path('logs')
    if logs_dir.exists():
        for log_file in logs_dir.glob('*.log*'):
            log_files.append(log_file)
    
    # 查找当前目录的日志文件
    for log_file in Path('.').glob('*.log*'):
        if log_file not in log_files:
            log_files.append(log_file)
    
    return log_files

def analyze_log_file(log_file_path, keyword=None, hours=24):
    """分析日志文件"""
    print(f"\n📄 分析日志文件: {log_file_path}")
    print("-" * 50)
    
    if not log_file_path.exists():
        print(f"❌ 文件不存在: {log_file_path}")
        return None
    
    # 获取文件信息
    stat = log_file_path.stat()
    file_size = stat.st_size
    modified_time = datetime.fromtimestamp(stat.st_mtime)
    
    print(f"📏 文件大小: {file_size:,} 字节")
    print(f"📅 修改时间: {modified_time.strftime('%Y-%m-%d %H:%M:%S')}")
    
    # 计算时间范围
    cutoff_time = datetime.now() - timedelta(hours=hours)
    
    # 读取和分析日志
    notification_entries = []
    error_entries = []
    warning_entries = []
    total_lines = 0
    recent_lines = 0
    
    try:
        with open(log_file_path, 'r', encoding='utf-8', errors='ignore') as f:
            for line_num, line in enumerate(f, 1):
                total_lines += 1
                
                # 解析时间戳
                time_match = re.search(r'(\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2})', line)
                if time_match:
                    try:
                        log_time = datetime.strptime(time_match.group(1), '%Y-%m-%d %H:%M:%S')
                        if log_time >= cutoff_time:
                            recent_lines += 1
                    except ValueError:
                        pass
                
                # 查找通知相关条目
                if any(keyword in line.lower() for keyword in ['通知', 'notification', 'toast', 'win11toast', 'notifier']):
                    notification_entries.append((line_num, line.strip()))
                
                # 查找错误条目
                if any(keyword in line.lower() for keyword in ['error', '错误', 'exception', 'traceback', '失败']):
                    error_entries.append((line_num, line.strip()))
                
                # 查找警告条目
                if any(keyword in line.lower() for keyword in ['warning', '警告', 'warn']):
                    warning_entries.append((line_num, line.strip()))
                
                # 如果指定了关键词，也查找该关键词
                if keyword and keyword.lower() in line.lower():
                    notification_entries.append((line_num, line.strip()))
        
        print(f"📊 总行数: {total_lines:,}")
        print(f"📊 最近{hours}小时行数: {recent_lines:,}")
        print(f"🔔 通知相关条目: {len(notification_entries)}")
        print(f"❌ 错误条目: {len(error_entries)}")
        print(f"⚠️ 警告条目: {len(warning_entries)}")
        
        # 显示通知相关条目
        if notification_entries:
            print(f"\n🔔 通知相关条目 (显示最近10条):")
            for line_num, line in notification_entries[-10:]:
                print(f"   [{line_num:6d}] {line}")
        
        # 显示错误条目
        if error_entries:
            print(f"\n❌ 错误条目 (显示最近10条):")
            for line_num, line in error_entries[-10:]:
                print(f"   [{line_num:6d}] {line}")
        
        # 显示警告条目
        if warning_entries:
            print(f"\n⚠️ 警告条目 (显示最近10条):")
            for line_num, line in warning_entries[-10:]:
                print(f"   [{line_num:6d}] {line}")
        
        return {
            'file_path': str(log_file_path),
            'file_size': file_size,
            'modified_time': modified_time,
            'total_lines': total_lines,
            'recent_lines': recent_lines,
            'notification_entries': len(notification_entries),
            'error_entries': len(error_entries),
            'warning_entries': len(warning_entries)
        }
        
    except Exception as e:
        print(f"❌ 读取文件失败: {e}")
        return None

def search_logs_for_pattern(pattern, hours=24):
    """在日志中搜索特定模式"""
    print(f"\n🔍 搜索模式: {pattern}")
    print(f"⏰ 时间范围: 最近{hours}小时")
    print("-" * 50)
    
    log_files = find_log_files()
    if not log_files:
        print("❌ 未找到日志文件")
        return
    
    cutoff_time = datetime.now() - timedelta(hours=hours)
    found_entries = []
    
    for log_file in log_files:
        try:
            with open(log_file, 'r', encoding='utf-8', errors='ignore') as f:
                for line_num, line in enumerate(f, 1):
                    # 检查时间戳
                    time_match = re.search(r'(\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2})', line)
                    if time_match:
                        try:
                            log_time = datetime.strptime(time_match.group(1), '%Y-%m-%d %H:%M:%S')
                            if log_time >= cutoff_time and re.search(pattern, line, re.IGNORECASE):
                                found_entries.append((log_file.name, line_num, line.strip()))
                        except ValueError:
                            pass
        except Exception as e:
            print(f"❌ 读取文件 {log_file} 失败: {e}")
    
    if found_entries:
        print(f"✅ 找到 {len(found_entries)} 个匹配项:")
        for file_name, line_num, line in found_entries[-20:]:  # 显示最近20条
            print(f"   [{file_name}:{line_num:6d}] {line}")
    else:
        print("❌ 未找到匹配项")

def show_notification_analysis():
    """显示通知分析"""
    print("\n🔔 通知功能分析")
    print("="*50)
    
    log_files = find_log_files()
    if not log_files:
        print("❌ 未找到日志文件")
        return
    
    notification_patterns = [
        r'win11toast',
        r'toast',
        r'通知',
        r'notification',
        r'notifier',
        r'Windows.*通知',
        r'发送.*通知',
        r'通知.*失败',
        r'通知.*成功'
    ]
    
    for pattern in notification_patterns:
        search_logs_for_pattern(pattern, hours=24)

def show_error_analysis():
    """显示错误分析"""
    print("\n❌ 错误分析")
    print("="*50)
    
    error_patterns = [
        r'error',
        r'错误',
        r'exception',
        r'traceback',
        r'失败',
        r'failed',
        r'import.*error',
        r'module.*not.*found'
    ]
    
    for pattern in error_patterns:
        search_logs_for_pattern(pattern, hours=24)

def main():
    """主函数"""
    parser = argparse.ArgumentParser(description='Mercari Bot 日志查看工具')
    parser.add_argument('--file', help='指定日志文件路径')
    parser.add_argument('--keyword', help='搜索关键词')
    parser.add_argument('--hours', type=int, default=24, help='时间范围（小时）')
    parser.add_argument('--pattern', help='搜索正则表达式模式')
    parser.add_argument('--notifications', action='store_true', help='分析通知相关日志')
    parser.add_argument('--errors', action='store_true', help='分析错误日志')
    parser.add_argument('--all', action='store_true', help='分析所有日志文件')
    
    args = parser.parse_args()
    
    print_header()
    
    if args.file:
        # 分析指定文件
        analyze_log_file(Path(args.file), args.keyword, args.hours)
    elif args.pattern:
        # 搜索特定模式
        search_logs_for_pattern(args.pattern, args.hours)
    elif args.notifications:
        # 分析通知日志
        show_notification_analysis()
    elif args.errors:
        # 分析错误日志
        show_error_analysis()
    elif args.all:
        # 分析所有日志文件
        log_files = find_log_files()
        if log_files:
            print(f"\n📁 找到 {len(log_files)} 个日志文件:")
            for log_file in log_files:
                analyze_log_file(log_file, args.keyword, args.hours)
        else:
            print("❌ 未找到日志文件")
    else:
        # 默认分析所有日志文件
        log_files = find_log_files()
        if log_files:
            print(f"\n📁 找到 {len(log_files)} 个日志文件:")
            for log_file in log_files:
                analyze_log_file(log_file, args.keyword, args.hours)
        else:
            print("❌ 未找到日志文件")
            print("\n💡 使用方法:")
            print("   python log_viewer.py --all                    # 分析所有日志")
            print("   python log_viewer.py --file logs/mercaribot.log  # 分析指定文件")
            print("   python log_viewer.py --notifications          # 分析通知日志")
            print("   python log_viewer.py --errors                 # 分析错误日志")
            print("   python log_viewer.py --pattern 'win11toast'   # 搜索特定模式")

if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n\n⏹️ 操作被用户中断")
    except Exception as e:
        print(f"\n❌ 操作过程中发生错误: {e}")
    
    input("\n按回车键退出...")
