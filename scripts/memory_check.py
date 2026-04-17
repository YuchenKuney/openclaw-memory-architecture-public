#!/usr/bin/env python3
"""
记忆容量监控 - 参考 Hermes Agent 设计
自动检查 MEMORY.md 和 USER.md 的使用情况
"""

import os
import sys

MEMORY_PATH = "/root/.openclaw/workspace/MEMORY.md"
USER_PATH = "/root/.openclaw/workspace/USER.md"

MEMORY_LIMIT = 2200  # Hermes 标准
USER_LIMIT = 1375    # Hermes 标准
WARNING_PERCENT = 80  # 80% 以上应该合并

def check_file(name, path, limit):
    if not os.path.exists(path):
        print(f"❌ {name}: 文件不存在")
        return
    
    with open(path, 'r') as f:
        content = f.read()
    
    size = len(content)
    percent = (size / limit) * 100
    
    if percent >= 100:
        status = "🔴 满"
    elif percent >= WARNING_PERCENT:
        status = "🟡 警告"
    else:
        status = "🟢 正常"
    
    print(f"{status} {name}: {size}/{limit} 字符 ({percent:.1f}%)")
    
    if percent >= 100:
        print(f"   ⚠️ 已满！需要先精简再添加新内容")
        return False
    elif percent >= WARNING_PERCENT:
        print(f"   💡 建议：高于80%，考虑合并旧条目")
    
    return True

def main():
    print("=" * 40)
    print("📊 记忆容量检查")
    print("=" * 40)
    
    memory_ok = check_file("MEMORY.md", MEMORY_PATH, MEMORY_LIMIT)
    user_ok = check_file("USER.md", USER_PATH, USER_LIMIT)
    
    print("=" * 40)
    
    if memory_ok and user_ok:
        print("✅ 记忆容量正常")
        return 0
    else:
        print("⚠️ 需要清理记忆")
        return 1

if __name__ == '__main__':
    sys.exit(main())
