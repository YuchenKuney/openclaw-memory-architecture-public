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
    "cron-events/",
]

# 危险操作类型
INOTIFY_EVENTS = {
    "IN_DELETE": "DELETE",
    "IN_MODIFY": "MODIFY",
    "IN_CLOSE_WRITE": "MODIFY",
    "IN_MOVED_FROM": "MOVED_FROM",
    "IN_MOVED_TO": "MOVED_TO",
    "IN_CREATE": "CREATE",
}


class ClawWatcher:
    """文件监控器"""
    
    def __init__(self, workspace_path, detector, notifier):
        self.workspace = Path(workspace_path).resolve()
        self.detector = detector
        self.notifier = notifier
        self.running = False
        self._thread = None
        
    def _handle_progress_event(self, path, event_type):
        """
        处理 tasks/progress/ 目录下的进度文件变化
        解析 JSON → 推送群聊进度卡片

        字段映射（progress_tracker.py 实际写入格式）：
          name       → 任务名称
          jobId      → 任务ID
          progress   → 进度 0-100
          step       → 当前步骤描述
          status     → running/done/error
          message    → 额外消息
          updatedAt  → 更新时间
          steps      → 历史步骤列表
        """
        import json as _json
        try:
            with open(path, 'r', encoding='utf-8') as f:
                data = _json.load(f)

            # 兼容 progress_tracker.py 的字段格式
            job_name = data.get('name', data.get('jobName', '未知任务'))
            progress = data.get('progress', 0)
            step = data.get('step', data.get('currentStep', ''))
            message = data.get('message', '')
            status = data.get('status', 'running')
            job_id = data.get('jobId', Path(path).stem)

            # 任务开始时（progress=0）推送"开始"通知
            if status == 'running' and progress == 0:
                self.notifier.notify_group_progress(job_name, 1, '🚀 任务开始', f'开始执行，共 {data.get("totalSteps", "?")} 步')
                return

            # running 状态推送当前进度
            if status == 'running':
                self.notifier.notify_group_progress(job_name, progress, step, message)
            elif status == 'done':
                self.notifier.notify_group_progress(job_name, 100, '✅ 已完成', message)
            elif status == 'error':
                err_msg = data.get('error', message or '任务异常')
                self.notifier.notify_group_progress(job_name, progress, '🔴 任务异常', err_msg)

        except Exception as e:
            print(f"[Watcher] 进度事件处理异常: {e}")

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
        
        # cron-events/ 目录的事件走专门的解析通知
        if category == "CORE_DIR" and str(path).startswith("cron-events"):
            self.notifier.notify_cron_event(str(path), event_type)
            return None

        # tasks/progress/ 目录的事件 → 解析进度 JSON → 推送群聊卡片
        if category == "CORE_DIR" and "tasks/progress" in str(path):
            self._handle_progress_event(str(path), event_type)
            return None

        # 交给检测器判断
        action = self.detector.evaluate(event_info)

        if action:
            self.notifier.send(action)

        return action
        
    def watch_inotify(self):
        """
        使用 inotify 监控
        使用 Inotify() + 手动管理目录监控，
        解决 InotifyTree 无法自动监控新建子目录的问题
        """
        if not INOTIFY_AVAILABLE:
            print("ERROR: inotify not available. Using fallback polling.")
            return self.watch_fallback()

        import inotify.constants as constants

        # 使用 Inotify() 而非 InotifyTree，手动管理每个目录的监控
        i = inotify.adapters.Inotify()

        # 递归添加监控（深度3层）
        def add_tree_watches(base_path, depth=0, max_depth=3):
            try:
                i.add_watch(base_path,
                    constants.IN_CREATE | constants.IN_DELETE |
                    constants.IN_MODIFY | constants.IN_CLOSE_WRITE |
                    constants.IN_OPEN | constants.IN_ACCESS |
                    constants.IN_MOVED_FROM | constants.IN_MOVED_TO)
                print(f"[ClawWatcher] +监控: {base_path}")
            except Exception as e:
                print(f"[ClawWatcher] 添加监控失败: {base_path}: {e}")
                return
            if depth < max_depth:
                try:
                    for entry in os.scandir(base_path):
                        if entry.is_dir() and not entry.name.startswith('.'):
                            add_tree_watches(entry.path, depth + 1, max_depth)
                except PermissionError:
                    pass

        add_tree_watches(str(self.workspace))

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

                # 如果新建了子目录，立即添加监控
                for event_name in type_names:
                    if event_name == 'IN_ISDIR' and 'IN_CREATE' in type_names:
                        try:
                            i.add_watch(full_path,
                                constants.IN_CREATE | constants.IN_DELETE |
                                constants.IN_MODIFY | constants.IN_CLOSE_WRITE |
                                constants.IN_OPEN | constants.IN_ACCESS |
                                constants.IN_MOVED_FROM | constants.IN_MOVED_TO)
                            print(f"[ClawWatcher] +新目录监控: {full_path}")
                        except Exception as e:
                            pass

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
