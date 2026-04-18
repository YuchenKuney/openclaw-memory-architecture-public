#!/usr/bin/env python3
"""
Clawkeeper Interceptor - 操作拦截器
当检测到危险操作时，阻止 AI 继续执行
"""

import os
import sys
import time
import signal
from pathlib import Path


class Interceptor:
    """拦截器"""
    
    def __init__(self, detector, notifier):
        self.detector = detector
        self.notifier = notifier
        self.pending_actions = {}  # 待审核的操作
        self.blocked_paths = set()  # 被拦截的路径
        
    def block(self, action):
        """
        拦截操作
        1. 记录到 blocked_paths
        2. 发送通知给用户
        3. 触发暂停信号
        """
        if not action or action.can_proceed:
            return False
            
        path = action.details.get("path", "")
        self.blocked_paths.add(path)
        
        # 发送通知
        self.notifier.send(action)
        
        # 记录待审核
        self.pending_actions[path] = {
            "action": action,
            "time": time.time(),
        }
        
        return True
        
    def pause_ai(self):
        """
        发送暂停信号给 AI
        通过设置环境变量或发送特定信号
        """
        os.environ["CLAWKEEPER_PAUSED"] = "1"
        print("[Interceptor] AI 已暂停，等待用户审核")
        
    def is_blocked(self, path):
        """检查路径是否被拦截"""
        return path in self.blocked_paths
        
    def approve(self, path):
        """
        用户批准操作
        返回: (success, message)
        """
        if path not in self.blocked_paths:
            return False, "路径未被拦截"
            
        self.blocked_paths.discard(path)
        
        # 清除待审核记录
        if path in self.pending_actions:
            del self.pending_actions[path]
            
        os.environ.pop("CLAWKEEPER_PAUSED", None)
        
        self.notifier.send_simple(f"✅ 坤哥已批准: {path}", "SUCCESS")
        return True, "操作已批准"
        
    def reject(self, path, rollback=True):
        """
        用户拒绝操作
        rollback: 是否尝试回退操作
        """
        if path not in self.blocked_paths and path not in self.pending_actions:
            return False, "路径未被拦截"
            
        self.blocked_paths.discard(path)
        
        if path in self.pending_actions:
            del self.pending_actions[path]
            
        os.environ.pop("CLAWKEEPER_PAUSED", None)
        
        # 尝试回退
        if rollback:
            self._rollback_path(path)
            
        self.notifier.send_simple(f"❌ 坤哥已拒绝: {path}", "WARN")
        return True, "操作已拒绝"
        
    def _rollback_path(self, path):
        """尝试回退文件操作"""
        path_obj = Path(path)
        
        try:
            # 如果文件被删除，尝试从 git 恢复
            if not path_obj.exists():
                workspace = os.environ.get("WORKSPACE", "/root/.openclaw/workspace")
                rel_path = Path(path).relative_to(workspace)
                cmd = f"cd {workspace} && git checkout -- {rel_path}"
                result = os.system(cmd)
                if result == 0:
                    print(f"[Interceptor] 已回退: {path}")
                else:
                    print(f"[Interceptor] 回退失败: {path}")
        except Exception as e:
            print(f"[Interceptor] 回退异常: {e}")
            
    def get_pending(self):
        """获取待审核操作列表"""
        return list(self.pending_actions.items())
        
    def is_paused(self):
        """检查是否暂停"""
        return os.environ.get("CLAWKEEPER_PAUSED") == "1"


class GitInterceptor:
    """Git 操作拦截器（通过 git hooks）"""
    
    HOOK_TEMPLATE = '''#!/bin/bash
# Clawkeeper Git Hook - 自动安装到 .git/hooks/
# 此脚本在 git 操作前运行

WORKSPACE="{workspace}"
AUDIT_LOG="{audit_log}"

log_event() {{
    echo "$(date '+%Y-%m-%d %H:%M:%S') $1" >> "$AUDIT_LOG"
}}

# 检查是否推送到公共仓库
if [[ "$*" == *"push"* ]] || [[ "$1" == "push" ]]; then
    # 检查目标仓库
    remote=$(git remote get-url --push origin 2>/dev/null || echo "")
    
    if [[ "$remote" == *"openclaw-memory-architecture-public"* ]]; then
        log_event "WARN: 尝试推送到公共仓库: $remote"
        
        # 调用 Python 拦截器
        python3 "{interceptor_script}" --check-push --remote "$remote"
        
        if [ $? -ne 0 ]; then
            echo "❌ Clawkeeper: 推送到公共仓库已暂停，等待坤哥审核"
            exit 1
        fi
    fi
fi

exit 0
'''
    
    def __init__(self, workspace, config_path=None):
        self.workspace = Path(workspace).resolve()
        self.git_hooks_dir = self.workspace / ".git" / "hooks"
        self.audit_log = (self.workspace / "clawkeeper" / "audit.log").resolve()
        self.interceptor_script = (self.workspace / "clawkeeper" / "interceptor.py").resolve()
        
    def install_hooks(self):
        """安装 git hooks"""
        os.makedirs(self.git_hooks_dir, exist_ok=True)
        
        hook_content = self.HOOK_TEMPLATE.format(
            workspace=self.workspace,
            audit_log=self.audit_log,
            interceptor_script=self.interceptor_script,
        )
        
        hook_path = self.git_hooks_dir / "pre-push"
        with open(hook_path, "w") as f:
            f.write(hook_content)
            
        os.chmod(hook_path, 0o755)
        print(f"[GitInterceptor] Hook 已安装到: {hook_path}")
        
    def uninstall_hooks(self):
        """卸载 git hooks"""
        hook_path = self.git_hooks_dir / "pre-push"
        if hook_path.exists():
            hook_path.unlink()
            print(f"[GitInterceptor] Hook 已卸载")


if __name__ == "__main__":
    workspace = os.environ.get("WORKSPACE", "/root/.openclaw/workspace")
    
    from detector import RiskDetector
    from notifier import FeishuNotifier
    
    detector = RiskDetector()
    notifier = FeishuNotifier()
    interceptor = Interceptor(detector, notifier)
    
    # 测试拦截
    from detector import Action, RiskLevel
    
    action = Action(
        level=RiskLevel.HIGH,
        action_type="BLOCK",
        message="🚨 尝试删除 AGENTS.md",
        details={"path": f"{workspace}/AGENTS.md", "event": "DELETE"}
    )
    
    if interceptor.block(action):
        print("操作已拦截，等待审核")
        print(f"待审核列表: {interceptor.get_pending()}")
