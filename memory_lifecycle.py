#!/usr/bin/env python3
"""
Memory Lifecycle Manager - 记忆生命周期管理
功能：
1. 自动归档过期日志（7天后）
2. 删除超期归档（90天后）
3. 检测重复条目
4. 更新已有条目而非追加
"""

import os
import json
import hashlib
import re
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional

# 配置
MEMORY_DIR = "/root/.openclaw/workspace/memory"
ARCHIVE_DIR = "/root/.openclaw/workspace/memory/archive"
CONFIG_FILE = "/root/.openclaw/workspace/memory/.lifecycle.json"

ACTIVE_DAYS = 7      # 活跃期：7天
ARCHIVE_DAYS = 90    # 归档保留期：90天
HASH_WINDOW = 200   # 计算哈希的字符窗口

class LifecycleManager:
    def __init__(self):
        self.memory_dir = Path(MEMORY_DIR)
        self.archive_dir = Path(ARCHIVE_DIR)
        self.config = self.load_config()
        
    def load_config(self) -> dict:
        """加载生命周期配置"""
        if os.path.exists(CONFIG_FILE):
            with open(CONFIG_FILE, 'r') as f:
                return json.load(f)
        return {
            "last_cleanup": None,
            "dedup_hashes": {},  # hash -> first_seen_date
            "entry_updates": {}, # topic -> last_updated_date
            "archived_files": []
        }
    
    def save_config(self):
        """保存配置"""
        with open(CONFIG_FILE, 'w') as f:
            json.dump(self.config, f, indent=2)
    
    def compute_hash(self, content: str) -> str:
        """计算内容哈希（使用前HASH_WINDOW个字符）"""
        return hashlib.md5(content[:HASH_WINDOW].encode()).hexdigest()[:12]
    
    def extract_topics(self, content: str) -> list:
        """提取主题关键词"""
        topics = []
        # 提取 ## 标题
        headers = re.findall(r'^##\s+(.+)$', content, re.MULTILINE)
        topics.extend(headers)
        # 提取日期格式
        dates = re.findall(r'\d{4}-\d{2}-\d{2}', content)
        topics.extend(dates)
        return topics
    
    def check_dedup(self, content: str) -> Optional[str]:
        """检查是否重复，返回已存在的日期或None"""
        h = self.compute_hash(content)
        if h in self.config["dedup_hashes"]:
            return self.config["dedup_hashes"][h]
        return None
    
    def add_hash(self, content: str, date: str):
        """添加内容哈希"""
        h = self.compute_hash(content)
        self.config["dedup_hashes"][h] = date
    
    def needs_update(self, topic: str, new_date: str) -> bool:
        """检查是否需要更新已有条目"""
        if topic in self.config["entry_updates"]:
            old_date = self.config["entry_updates"][topic]
            if old_date < new_date:
                return True
        return False
    
    def mark_updated(self, topic: str, date: str):
        """标记条目已更新"""
        self.config["entry_updates"][topic] = date
    
    def get_files_to_archive(self) -> list:
        """获取需要归档的文件"""
        cutoff = datetime.now() - timedelta(days=ACTIVE_DAYS)
        to_archive = []
        
        for f in self.memory_dir.glob("*.md"):
            if f.name.startswith('.'):
                continue
            # 跳过索引文件
            if f.name == "index.md":
                continue
            # 检查日期
            try:
                date_str = f.stem  # 文件名去掉.md
                file_date = datetime.strptime(date_str, "%Y-%m-%d")
                if file_date < cutoff:
                    to_archive.append(f)
            except ValueError:
                continue
        
        return to_archive
    
    def get_files_to_delete(self) -> list:
        """获取需要删除的归档文件"""
        cutoff = datetime.now() - timedelta(days=ARCHIVE_DAYS)
        to_delete = []
        
        if not self.archive_dir.exists():
            return []
        
        for f in self.archive_dir.rglob("*.md"):
            try:
                # 从路径提取日期
                date_str = f.stem
                file_date = datetime.strptime(date_str, "%Y-%m-%d")
                if file_date < cutoff:
                    to_delete.append(f)
            except ValueError:
                continue
        
        return to_delete
    
    def archive_file(self, filepath: Path) -> bool:
        """归档文件"""
        try:
            # 创建归档目录
            year_month = filepath.stem[:7]  # YYYY-MM
            archive_subdir = self.archive_dir / year_month
            archive_subdir.mkdir(parents=True, exist_ok=True)
            
            # 移动文件
            dest = archive_subdir / filepath.name
            filepath.rename(dest)
            
            self.config["archived_files"].append({
                "original": str(filepath),
                "archived": str(dest),
                "date": datetime.now().isoformat()
            })
            return True
        except Exception as e:
            print(f"  ❌ 归档失败 {filepath}: {e}")
            return False
    
    def delete_file(self, filepath: Path) -> bool:
        """删除超期文件"""
        try:
            filepath.unlink()
            return True
        except Exception as e:
            print(f"  ❌ 删除失败 {filepath}: {e}")
            return False
    
    def run_cleanup(self) -> dict:
        """执行清理"""
        stats = {
            "archived": 0,
            "deleted": 0,
            "errors": 0
        }
        
        # 归档活跃期已过的文件
        for f in self.get_files_to_archive():
            if self.archive_file(f):
                stats["archived"] += 1
                print(f"  📦 归档: {f.name}")
            else:
                stats["errors"] += 1
        
        # 删除超期归档
        for f in self.get_files_to_delete():
            if self.delete_file(f):
                stats["deleted"] += 1
                print(f"  🗑️  删除: {f}")
            else:
                stats["errors"] += 1
        
        # 更新配置
        self.config["last_cleanup"] = datetime.now().isoformat()
        self.save_config()
        
        return stats
    
    def check(self) -> dict:
        """检查状态"""
        archive_count = len(self.get_files_to_archive())
        delete_count = len(self.get_files_to_delete())
        
        stats = {
            "active_files": len(list(self.memory_dir.glob("*.md"))) - 1,  # -1 for index
            "to_archive": archive_count,
            "to_delete": delete_count,
            "dedup_entries": len(self.config["dedup_hashes"]),
            "update_entries": len(self.config["entry_updates"]),
            "last_cleanup": self.config["last_cleanup"]
        }
        
        return stats
    
    def print_stats(self):
        """打印统计"""
        stats = self.check()
        print("=" * 50)
        print("📊 Memory Lifecycle 状态")
        print("=" * 50)
        print(f"  活跃日志文件: {stats['active_files']}")
        print(f"  待归档: {stats['to_archive']}")
        print(f"  待删除: {stats['to_delete']}")
        print(f"  去重哈希: {stats['dedup_entries']}")
        print(f"  更新追踪: {stats['update_entries']}")
        print(f"  上次清理: {stats['last_cleanup'] or '从未清理'}")
        print("=" * 50)
        
        if stats['to_archive'] > 0 or stats['to_delete'] > 0:
            print(f"  ⚠️  需要清理！运行 --cleanup")
        else:
            print(f"  ✅ 无需清理")
        print()

def main():
    import argparse
    parser = argparse.ArgumentParser(description='Memory Lifecycle Manager')
    parser.add_argument('--check', action='store_true', help='检查状态')
    parser.add_argument('--cleanup', action='store_true', help='执行清理')
    parser.add_argument('--stats', action='store_true', help='显示统计')
    args = parser.parse_args()
    
    manager = LifecycleManager()
    
    if args.check or args.stats or (not args.cleanup):
        manager.print_stats()
    
    if args.cleanup:
        print("\n🧹 开始清理...")
        stats = manager.run_cleanup()
        print(f"\n✅ 清理完成！")
        print(f"   归档: {stats['archived']} | 删除: {stats['deleted']} | 错误: {stats['errors']}")
        manager.print_stats()

if __name__ == '__main__':
    main()
