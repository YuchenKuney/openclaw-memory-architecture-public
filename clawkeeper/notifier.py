#!/usr/bin/env python3
"""
Clawkeeper Notifier - 通知模块
将危险操作通知给用户（飞书）
"""

import os
import sys
import json
import urllib.request
import urllib.parse
import time
from datetime import datetime

# 添加当前目录到路径
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
try:
    from config_loader import get_webhook_url, get_user_id, get_group_id
except ImportError:
    # 如果 config_loader 不存在，使用默认值
    def get_webhook_url():
        return os.environ.get("FEISHU_WEBHOOK", "https://open.feishu.cn/open-apis/bot/v2/hook/375a8be1-9e3e-4758-a78b-e775fd4d32a1")
    def get_user_id():
        return os.environ.get("KUNGE_ID", "")
    def get_group_id():
        return os.environ.get("FEISHU_GROUP_ID", "")


class FeishuNotifier:
    """飞书通知器"""
    
    def __init__(self, webhook_url=None):
        # 从配置文件读取 webhook URL
        self.webhook = webhook_url or get_webhook_url()
        self.user_id = get_user_id()
        self.group_id = get_group_id()
        self.enabled = True
        
    def send(self, action):
        """
        发送通知
        action: Action 对象
        """
        if not self.enabled:
            return
            
        # 根据危险等级构建消息
        level = action.level.name
        
        if level == "CRITICAL":
            title = "🔴 极高风险拦截"
            color = "red"
        elif level == "HIGH":
            title = "🚨 高风险拦截"
            color = "orange"
        elif level == "MEDIUM":
            title = "⚠️ 中风险待审核"
            color = "yellow"
        elif level == "LOW":
            title = "📝 低风险记录"
            color = "blue"
        else:
            return
            
        # 构建卡片消息（兼容飞书卡片限制）
        elements = [
            {
                "tag": "markdown",
                "content": f"**文件**: `{action.details.get('path', 'unknown')}`"
            },
            {
                "tag": "markdown", 
                "content": f"**操作**: `{action.details.get('event', 'unknown')}`"
            },
            {
                "tag": "markdown",
                "content": f"**风险等级**: {level}"
            },
            {
                "tag": "markdown",
                "content": f"**时间**: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"
            },
            {"tag": "hr"},
            {
                "tag": "markdown",
                "content": f"**Clawkeeper 动作**: `{action.action_type}`  |  **AI 能否继续**: {'✅ 可以' if action.can_proceed else '❌ 不可以'}"
            },
            {"tag": "hr"},
        ]
        
        # 根据动作类型添加不同提示
        if action.action_type == "BLOCK":
            elements.append({
                "tag": "div",
                "text": {"tag": "plain_text", "content": "⚠️ 操作已被拦截！AI 已暂停执行，等待坤哥处理。\n\n回复「允许」放行 / 「拒绝」回退"}
            })
        elif action.action_type == "PAUSE":
            elements.append({
                "tag": "div", 
                "text": {"tag": "plain_text", "content": "⏸️ 操作已暂停，等待审核。\n\n回复「允许」继续 / 「拒绝」取消"}
            })
        else:
            elements.append({
                "tag": "div",
                "text": {"tag": "plain_text", "content": action.message}
            })
            
        card = {
            "msg_type": "interactive",
            "card": {
                "header": {
                    "title": {"tag": "plain_text", "content": f"🛡️ Clawkeeper {title}"},
                    "template": color,
                },
                "elements": elements
            }
        }
        
        self._send_card(card)
        
    def _send_card(self, card):
        """发送卡片消息"""
        try:
            data = json.dumps(card, ensure_ascii=False).encode("utf-8")
            req = urllib.request.Request(
                self.webhook,
                data=data,
                headers={"Content-Type": "application/json"}
            )
            with urllib.request.urlopen(req, timeout=10) as resp:
                result = json.loads(resp.read())
                if result.get("StatusCode") == 0:
                    print(f"[Notifier] 通知已发送")
                else:
                    print(f"[Notifier] 发送失败: {result}")
        except Exception as e:
            print(f"[Notifier] 发送异常: {e}")
            
    def send_simple(self, message, level="INFO"):
        """发送简单文本消息"""
        emoji = {"INFO": "ℹ️", "WARN": "⚠️", "ERROR": "❌", "SUCCESS": "✅"}
        
        msg = {
            "msg_type": "text",
            "content": {"text": f"{emoji.get(level, 'ℹ️')} {message}"}
        }
        
        try:
            data = json.dumps(msg).encode("utf-8")
            req = urllib.request.Request(
                self.webhook,
                data=data,
                headers={"Content-Type": "application/json"}
            )
            with urllib.request.urlopen(req, timeout=10):
                pass
        except Exception as e:
            print(f"[Notifier] 发送失败: {e}")

    def notify_cron_event(self, file_path, event_type):
        """
        发送 Cron 事件通知（解析 cron-events/ 目录下的 JSON 文件）
        """
        import urllib.request
        import urllib.parse
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                content = f.read().strip()

            # 尝试解析 JSON
            try:
                data = json.loads(content)
                job_name = data.get('job', '未知任务')
                status = data.get('status', event_type.lower())
                message = data.get('message', '')
                triggered_at = data.get('triggeredAt', '')
            except json.JSONDecodeError:
                job_name = content
                status = event_type.lower()
                message = ''
                triggered_at = ''

            # 根据状态决定颜色和 emoji
            status_config = {
                'fired': ('🟢 任务触发', 'green'),
                'running': ('🔵 进行中', 'blue'),
                'done': ('✅ 任务完成', 'green'),
                'error': ('🔴 任务异常', 'red'),
            }
            title, color = status_config.get(status, ('📋 任务事件', 'grey'))

            elements = [
                {"tag": "markdown", "content": f"**任务**: `{job_name}`"},
                {"tag": "markdown", "content": f"**状态**: `{status.upper()}`"},
            ]
            if triggered_at:
                elements.append({"tag": "markdown", "content": f"**触发时间**: `{triggered_at}`"})
            if message:
                elements.append({"tag": "markdown", "content": f"**详情**: {message}"}
            )
            elements.append({"tag": "hr"})
            elements.append({"tag": "markdown", "content": f"来源: `cron-events/` 监控"})

            card = {
                "msg_type": "interactive",
                "card": {
                    "header": {
                        "title": {"tag": "plain_text", "content": title},
                        "template": color,
                    },
                    "elements": elements
                }
            }
            self._send_card(card)
        except Exception as e:
            print(f"[Notifier] Cron事件通知失败: {e}")

    def notify_git_operation(self, operation, target, remote):
        """
        发送 Git 操作通知
        用于 git push / git commit / git merge 等操作前通知坤哥
        
        Args:
            operation: 操作类型 (push/commit/merge/...)
            target: 目标分支或仓库
            remote: 远程仓库 URL
        """
        # 简化仓库名
        repo_name = remote.split("/")[-1].replace(".git", "") if remote else "unknown"
        
        card = {
            "msg_type": "interactive",
            "card": {
                "header": {
                    "title": {"tag": "plain_text", "content": "🛡️ Git 操作通知"},
                    "template": "yellow",
                },
                "elements": [
                    {"tag": "markdown", "content": f"**Git 操作**: `{operation.upper()}`"},
                    {"tag": "markdown", "content": f"**目标**: `{target}`"},
                    {"tag": "markdown", "content": f"**仓库**: `{repo_name}`"},
                    {"tag": "markdown", "content": f"**时间**: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"},
                    {"tag": "hr"},
                    {"tag": "div", "text": {"tag": "plain_text", "content": "⚠️ AI 即将执行 Git 操作\n\n如需审核，请回复「允许」或「拒绝」"}},
                ]
            }
        }
        self._send_card(card)

    def log_git_operation(self, operation, target, remote, result="pending"):
        """
        记录 Git 操作到审计日志
        
        Args:
            operation: 操作类型
            target: 目标
            remote: 远程仓库
            result: 结果 (pending/success/failed/rejected)
        """
        entry = {
            "time": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "level": "GIT_OPERATION",
            "operation": operation,
            "target": target,
            "remote": remote,
            "result": result,
        }
        
        audit_log = "/root/.openclaw/workspace/clawkeeper/audit.log"
        try:
            os.makedirs(os.path.dirname(audit_log), exist_ok=True)
            with open(audit_log, "a") as f:
                f.write(json.dumps(entry, ensure_ascii=False) + "\n")
        except Exception as e:
            print(f"[Notifier] 审计日志写入失败: {e}")


class AuditLogger:
    """本地审计日志（备份）"""
    
    def __init__(self, log_path=None):
        self.log_path = log_path or os.environ.get(
            "CLAWKEEPER_AUDIT_LOG",
            "/root/.openclaw/workspace/clawkeeper/audit.log"
        )
        os.makedirs(os.path.dirname(self.log_path), exist_ok=True)
        
    def log(self, action, response=None):
        """记录动作和响应"""
        entry = {
            "timestamp": datetime.now().isoformat(),
            "action": action.to_dict(),
            "response": response,
        }
        
        with open(self.log_path, "a") as f:
            f.write(json.dumps(entry, ensure_ascii=False) + "\n")


if __name__ == "__main__":
    # 测试通知
    from detector import RiskDetector, Action, RiskLevel
    
    notifier = FeishuNotifier()
    
    # 测试危险操作通知
    action = Action(
        level=RiskLevel.HIGH,
        action_type="BLOCK",
        message="🚨 [HIGH] 尝试删除核心文件：AGENTS.md",
        details={"path": "/root/.openclaw/workspace/AGENTS.md", "event": "DELETE"}
    )
    
    notifier.send(action)
    print("通知已发送")
