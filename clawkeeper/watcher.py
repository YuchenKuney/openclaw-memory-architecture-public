#!/usr/bin/env python3
"""
Clawkeeper Watcher - inotify 文件系统监控
监控 AI Agent 对关键文件的操作（删除、修改、移动）
"""

import os
import sys
import time
import threading
import subprocess
from pathlib import Path

# 尝试导入 inotify，不存在则使用 fallback
try:
    import inotify.adapters
    INOTIFY_AVAILABLE = True
except ImportError:
    INOTIFY_AVAILABLE = False

# 核心保护文件列表（铁律）
PROTECTED_FILES = [
    "AGENTS.md",
    "SOUL.md", 
    "MEMORY.md",
    "IDENTITY.md",
    "USER.md",
    "HEARTBEAT.md",
    "TOOLS.md",
]

# 核心目录
PROTECTED_DIRS = [
    "tasks/",
    "memory/",
    "shared/",
]

# 危险操作类型
INOTIFY_EVENTS = {
    "IN_DELETE": "DELETE",      # 文件被删除
    "IN_MODIFY": "MODIFY",     # 文件被修改
    "IN_MOVED_FROM": "MOVED_FROM",  # 文件被移走
    "IN_MOVED_TO": "MOVED_TO",      # 文件被移入
    "IN_CREATE": "CREATE",     # 文件被创建
}


class ClawWatcher:
    """文件监控器"""
    
    def __init__(self, workspace_path, detector, notifier):
        self.workspace = Path(workspace_path).resolve()
        self.detector = detector
        self.notifier = notifier
        self.running = False
        self._thread = None
        
    def is_protected_path(self, path):
        """检查路径是否受保护"""
        path = Path(path).resolve()
        rel_path = path.relative_to(self.workspace) if path.is_relative_to(self.workspace) else path
        
        # 检查文件名
        if rel_path.name in PROTECTED_FILES:
            return True, "CORE_FILE"
            
        # 检查路径前缀
        for protected in PROTECTED_DIRS:
            if str(rel_path).startswith(protected):
                return True, "CORE_DIR"
                
        return False, None
        
    def handle_event(self, path, event_type):
        """处理监控事件"""
        is_protected, category = self.is_protected_path(path)
        
        if not is_protected:
            return None
            
        # 构建事件信息
        event_info = {
            "path": str(path),
            "event": event_type,
            "category": category,
            "timestamp": time.time(),
        }
        
        # 交给检测器判断
        action = self.detector.evaluate(event_info)
        
        if action:
            self.notifier.send(action)
            
        return action
        
    def watch_inotify(self):
        """使用 inotify 监控"""
        if not INOTIFY_AVAILABLE:
            print("ERROR: inotify not available. Using fallback polling.")
            return self.watch_fallback()
            
        i = inotify.adapters.Inotify()
        
        # 添加工作区监控
        i.add_watch(str(self.workspace), 
            inotify.adapters.InotifyTree.WATCH_EVENTS)
            
        self.running = True
        print(f"[ClawWatcher] 监控中: {self.workspace}")
        
        try:
            for event in i.event_gen():
                if not self.running:
                    break
                    
                if event is None:
                    continue
                    
                (header, type_names, path, filename) = event
                full_path = os.path.join(path, filename) if filename else path
                
                for event_name in type_names:
                    if event_name in INOTIFY_EVENTS:
                        self.handle_event(full_path, INOTIFY_EVENTS[event_name])
                        
        except Exception as e:
            print(f"[ClawWatcher] 监控异常: {e}")
        finally:
            self.running = False
            
    def watch_fallback(self):
        """Fallback：使用 stat 轮询（不支持 inotify 的系统）"""
        import hashlib
        
        file_states = {}
        
        # 初始化状态
        for root, dirs, files in os.walk(self.workspace):
            for f in files:
                path = os.path.join(root, f)
                try:
                    stat = os.stat(path)
                    file_states[path] = {
                        "mtime": stat.st_mtime,
                        "size": stat.st_size,
                        "exists": True,
                    }
                except:
                    pass
                    
        self.running = True
        print(f"[ClawWatcher Fallback] 监控中: {self.workspace}")
        
        while self.running:
            for path, state in list(file_states.items()):
                try:
                    stat = os.stat(path)
                    
                    if not state["exists"]:
                        # 文件恢复了
                        self.handle_event(path, "RESTORE")
                        file_states[path]["exists"] = True
                        
                    elif stat.st_mtime != state["mtime"]:
                        # 文件被修改
                        self.handle_event(path, "MODIFY")
                        file_states[path]["mtime"] = stat.st_mtime
                        
                except FileNotFoundError:
                    if state["exists"]:
                        # 文件被删除
                        self.handle_event(path, "DELETE")
                        file_states[path]["exists"] = False
                        
                except Exception:
                    pass
                    
            time.sleep(2)  # 每2秒检查一次
            
    def start(self):
        """启动监控线程"""
        if self._thread and self._thread.is_alive():
            return
            
        self._thread = threading.Thread(target=self.watch_inotify, daemon=True)
        self._thread.start()
        print(f"[ClawWatcher] 启动完成 (thread: {self._thread.name})")
        
    def stop(self):
        """停止监控"""
        self.running = False
        if self._thread:
            self._thread.join(timeout=3)
        print("[ClawWatcher] 已停止")


if __name__ == "__main__":
    # 测试用
    workspace = os.environ.get("WORKSPACE", "/root/.openclaw/workspace")
    
    from detector import RiskDetector
    from notifier import FeishuNotifier
    
    detector = RiskDetector()
    notifier = FeishuNotifier()
    
    watcher = ClawWatcher(workspace, detector, notifier)
    
    print(f"工作区: {workspace}")
    print("按 Ctrl+C 停止")
    
    try:
        watcher.start()
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        print("\n停止中...")
        watcher.stop()
