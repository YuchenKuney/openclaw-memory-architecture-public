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



    def notify_group_progress(self, job_name, progress, step, message=""):
        """
        发送群聊进度通知（实时进度条）
        """
        now = datetime.now().strftime("%H:%M:%S")
        filled = round(progress / 10)
        bar = "█" * filled + "░" * (10 - filled)

        if progress == 0:
            status_text, color = "🆕 开始执行", "blue"
        elif progress == 100:
            status_text, color = "✅ 任务完成", "green"
        else:
            status_text, color = "🔄 进行中", "orange"

        content_parts = [
            f"**任务**: `{job_name}`",
            f"**进度**: {bar} `{progress}%`",
            f"**步骤**: `{step}`",
        ]
        if message:
            content_parts.append(f"**详情**: {message}")
        content_parts.append(f"`⏰ {now}`")

        card = {
            "msg_type": "interactive",
            "card": {
                "header": {"title": {"tag": "plain_text", "content": f"{status_text} {job_name}"}, "template": color},
                "elements": [{"tag": "markdown", "content": "\n".join(content_parts)}]
            }
        }
        group_webhook = os.environ.get("FEISHU_GROUP_WEBHOOK", "https://open.feishu.cn/open-apis/bot/v2/hook/7a939580-e987-4571-a142-f58528cf71ec")
        try:
            data = json.dumps(card, ensure_ascii=False).encode("utf-8")
            req = urllib.request.Request(group_webhook, data=data, headers={"Content-Type": "application/json"})
            with urllib.request.urlopen(req, timeout=10) as resp:
                result = json.loads(resp.read())
                print(f"[Notifier] 群聊进度通知已发送: {progress}%") if result.get("StatusCode") == 0 or result.get("code") == 0 else print(f"[Notifier] 群聊通知失败: {result}")
        except Exception as e:
            print(f"[Notifier] 群聊通知异常: {e}")



class StepReporter:
    """
    全链路透明化步骤汇报器（反黑箱核心）

    坤哥铁律：AI 每个操作步骤都对坤哥可见

    用法：
        reporter = StepReporter()
        reporter.start_task("编写 Demo 脚本", total_steps=4)
        # 飞书群收到：🆕 开始执行 | 任务计划（4步）
        #
        reporter.step_done(1, "分析 demo 需求", next_step="编写 demo1 代码")
        # 飞书群收到：✅ Step 1/4 完成 | 下一步：编写 demo1 代码
        #
        reporter.step_done(2, "编写 demo1_longpoll.py", next_step="编写 demo2_callback.py")
        # ...
        #
        reporter.task_done("全部完成！")
        # 飞书群收到：✅ 任务完成 | 总结

    与 notifier.notify_group_progress() 的区别：
        - notify_group_progress: 单次进度条（0-100%）
        - StepReporter: 任务级别的步骤计划 + 每步完成时主动汇报
    """

    def __init__(self, group_webhook: str = None):
        self.group_webhook = group_webhook or os.environ.get(
            "FEISHU_GROUP_WEBHOOK",
            "https://open.feishu.cn/open-apis/bot/v2/hook/7a939580-e987-4571-a142-f58528cf71ec"
        )
        self._current_task = None  # 当前任务

    def _send_card(self, card: dict):
        """发送卡片到飞书群"""
        try:
            data = json.dumps(card, ensure_ascii=False).encode("utf-8")
            req = urllib.request.Request(
                self.group_webhook,
                data=data,
                headers={"Content-Type": "application/json"}
            )
            with urllib.request.urlopen(req, timeout=10) as resp:
                result = json.loads(resp.read())
                status = result.get("StatusCode") or result.get("code")
                if status == 0:
                    print(f"[StepReporter] 步骤通知已发送")
                else:
                    print(f"[StepReporter] 发送失败: {result}")
        except Exception as e:
            print(f"[StepReporter] 发送异常: {e}")

    def _build_progress_bar(self, current: int, total: int) -> str:
        """构建进度条：███░░░░░░░"""
        filled = round(current / total * 10)
        return "█" * filled + "░" * (10 - filled)

    def start_task(self, task_name: str, total_steps: int = 1, task_desc: str = ""):
        """
        开始任务：发送任务计划到飞书群（告诉坤哥要做什么）

        Args:
            task_name: 任务名称（如"编写 Demo 脚本"）
            total_steps: 总步骤数（如 4）
            task_desc: 可选，任务详细描述
        """
        self._current_task = {
            "name": task_name,
            "total_steps": total_steps,
            "current_step": 0,
            "started_at": datetime.now().strftime("%H:%M:%S"),
        }

        # 构建步骤计划文字
        steps_text = ""
        if total_steps <= 10:
            steps_text = "\n".join([
                f"  Step {i}/{total_steps}: ..." for i in range(1, total_steps + 1)
            ])

        content_parts = [
            f"**🤖 任务开始**: `{task_name}`",
            f"**📋 任务计划**: 共 **{total_steps}** 步",
        ]
        if task_desc:
            content_parts.append(f"**📝 描述**: {task_desc}")
        if steps_text:
            content_parts.append(f"**📌 步骤计划**:\n{steps_text}")
        content_parts.append(f"**⏰ 开始时间**: `{self._current_task['started_at']}`")
        content_parts.append("")
        content_parts.append("🔔 坤哥将实时收到每步完成通知...")

        card = {
            "msg_type": "interactive",
            "card": {
                "header": {
                    "title": {"tag": "plain_text", "content": f"🆕 任务开始 | {task_name}"},
                    "template": "blue",
                },
                "elements": [
                    {"tag": "markdown", "content": "\n".join(content_parts)},
                    {"tag": "hr"},
                    {"tag": "markdown", "content": "_AI 将实时汇报每步完成情况，请留意群消息_"},
                ]
            }
        }
        self._send_card(card)
        print(f"[StepReporter] 🆕 任务开始: {task_name} ({total_steps} 步)")

        # 同时写入状态文件（供 Cron 任务进度汇报使用）
        import subprocess
        try:
            subprocess.run([
                "python3",
                "/root/.openclaw/workspace/scripts/task_state_writer.py",
                "start", task_name, str(total_steps)
            ], timeout=5, capture_output=True)
        except Exception as e:
            print(f"[StepReporter] 状态写入失败: {e}")

    def step_done(self, step_num: int, step_name: str, next_step: str = "", eta_seconds: int = 0):
        """
        步骤完成：发送进度更新到飞书群

        Args:
            step_num: 当前步骤（从 1 开始）
            step_name: 当前步骤名称（如"分析 demo 需求"）
            next_step: 下一步要做什么（如"编写 demo1 代码"）
            eta_seconds: 预计剩余时间（秒）
        """
        if not self._current_task:
            print(f"[StepReporter] ⚠️ 没有活跃任务，请先调用 start_task()")
            return

        total = self._current_task["total_steps"]
        progress = round(step_num / total * 100)
        bar = self._build_progress_bar(step_num, total)
        elapsed = datetime.now().strftime("%H:%M:%S")

        # 判断状态
        if step_num == total:
            status_text, color, template = "✅ 即将完成", "green", "green"
        else:
            status_text, color, template = "🔄 进行中", "orange", "orange"

        content_parts = [
            f"**📍 当前**: Step {step_num}/{total} — `{step_name}`",
            f"**{status_text}**: {bar} **{progress}%**",
        ]
        if next_step:
            content_parts.append(f"**➡️  下一步**: `{next_step}`")
        if eta_seconds > 0:
            eta_text = f"约 {eta_seconds} 秒" if eta_seconds < 60 else f"约 {eta_seconds // 60} 分钟"
            content_parts.append(f"**⏱️  预计**: {eta_text} 后完成")
        content_parts.append(f"**⏰ 已用时间**: `{elapsed}`")

        card = {
            "msg_type": "interactive",
            "card": {
                "header": {
                    "title": {"tag": "plain_text", "content": f"{status_text} {self._current_task['name']}"},
                    "template": template,
                },
                "elements": [
                    {"tag": "markdown", "content": "\n".join(content_parts)},
                ]
            }
        }
        self._send_card(card)
        self._current_task["current_step"] = step_num
        print(f"[StepReporter] 📍 Step {step_num}/{total}: {step_name}")

        # 同时写入状态文件
        import subprocess
        try:
            next_arg = [str(step_num), step_name, next_step or "", str(eta_seconds or 0)]
            subprocess.run([
                "python3",
                "/root/.openclaw/workspace/scripts/task_state_writer.py",
                "step", *next_arg
            ], timeout=5, capture_output=True)
        except Exception as e:
            print(f"[StepReporter] 状态写入失败: {e}")

    def task_done(self, message: str = ""):
        """
        任务完成：发送完成总结到飞书群

        Args:
            message: 可选，完成总结（如"全部完成！用时 2 分钟"）
        """
        if not self._current_task:
            print(f"[StepReporter] ⚠️ 没有活跃任务")
            return

        total = self._current_task["total_steps"]
        started = self._current_task["started_at"]
        elapsed = datetime.now().strftime("%H:%M:%S")

        content_parts = [
            f"**✅ 任务完成**: `{self._current_task['name']}`",
            f"**📊 完成时间**: {started} → {elapsed}",
            f"**📋 共完成**: {total}/{total} 步",
        ]
        if message:
            content_parts.append(f"**📝 总结**: {message}")

        card = {
            "msg_type": "interactive",
            "card": {
                "header": {
                    "title": {"tag": "plain_text", "content": f"✅ 任务完成 | {self._current_task['name']}"},
                    "template": "green",
                },
                "elements": [
                    {"tag": "markdown", "content": "\n".join(content_parts)},
                    {"tag": "hr"},
                    {"tag": "markdown", "content": "_感谢坤哥的耐心等待 🎉_"},
                ]
            }
        }
        self._send_card(card)
        task_name = self._current_task["name"] if self._current_task else "?"
        self._current_task = None
        print(f"[StepReporter] ✅ 任务完成: {task_name}")

        # 写入完成状态 + 清除（让 Cron 不再汇报）
        import subprocess
        try:
            subprocess.run([
                "python3",
                "/root/.openclaw/workspace/scripts/task_state_writer.py",
                "done", message or ""
            ], timeout=5, capture_output=True)
        except Exception as e:
            print(f"[StepReporter] 状态写入失败: {e}")

    def task_error(self, step_num: int, step_name: str, error_message: str = ""):
        """
        任务出错：发送错误通知到飞书群

        Args:
            step_num: 当前步骤
            step_name: 当前步骤名称
            error_message: 错误信息
        """
        if not self._current_task:
            print(f"[StepReporter] ⚠️ 没有活跃任务")
            return

        content_parts = [
            f"**🔴 任务出错**: `{self._current_task['name']}`",
            f"**📍 错误位置**: Step {step_num}/{self._current_task['total_steps']} — `{step_name}`",
        ]
        if error_message:
            content_parts.append(f"**❌ 错误信息**: `{error_message}`")

        card = {
            "msg_type": "interactive",
            "card": {
                "header": {
                    "title": {"tag": "plain_text", "content": f"🔴 任务出错 | {self._current_task['name']}"},
                    "template": "red",
                },
                "elements": [
                    {"tag": "markdown", "content": "\n".join(content_parts)},
                    {"tag": "hr"},
                    {"tag": "markdown", "content": "_AI 已停止，等待坤哥处理_"},
                ]
            }
        }
        self._send_card(card)
        print(f"[StepReporter] 🔴 任务出错: Step {step_num} - {error_message}")




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

