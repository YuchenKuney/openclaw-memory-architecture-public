#!/usr/bin/env python3
"""
Task Monitor - 子 agent 任务进度监控器
与反黑箱四级分层深度整合

启动方式：作为 OpenClaw 子 agent 运行

四级分层（与 interceptor.py 完全一致）：
  LOG_ONLY (SAFE/LOW)     → 只记录日志，不推送飞书（轻量任务）
  WARN_AND_LOG (MEDIUM)    → 推送黄色警告卡片（进度正常但有疑问）
  BLOCK_AND_NOTIFY (HIGH)  → 推送红色拦截卡片，等坤哥审批（高危操作）
  KILL_AND_ISOLATE (CRITICAL) → 推送深红色紧急卡片，终止操作（核心文件删除）

调用方式：
  python3 task_monitor.py
  openclaw tasks spawn --runtime=subagent --task-file task_monitor.py
"""

import os
import sys
import json
import time
import hashlib
from pathlib import Path
from datetime import datetime
from enum import IntEnum
from typing import Optional, Dict

WORKSPACE = Path("/root/.openclaw/workspace")
PROGRESS_DIR = WORKSPACE / "tasks" / "progress"
PROGRESS_FILE = PROGRESS_DIR / "current_task.json"  # 备用兜底路径
NOTIFY_STATE_FILE = WORKSPACE / ".monitor_state.json"
FEISHU_WEBHOOK = os.environ.get(
    "FEISHU_WEBHOOK",
    "YOUR_FEISHU_WEBHOOK_URL"
)


# ============ 反黑箱四级分级（与 interceptor.py 一致）============

class AlertLevel(IntEnum):
    """与 interceptor.py 的 RiskLevel 对齐"""
    SAFE = 0       # 只记录，不推送
    LOW = 1        # 只记录，不推送
    MEDIUM = 2     # 警告卡片（黄色）
    HIGH = 3       # 拦截卡片（红色），等待审批
    CRITICAL = 4   # 紧急终止卡片（深红），强制处理


# ============ 飞书卡片推送（按风险等级）============

def send_card(level: int, title: str, body: str, footer: str = "") -> bool:
    """
    统一推送入口，按 AlertLevel 决定卡片样式
    """
    template_map = {
        AlertLevel.SAFE: "blue",
        AlertLevel.LOW: "blue",
        AlertLevel.MEDIUM: "yellow",
        AlertLevel.HIGH: "red",
        AlertLevel.CRITICAL: "red",
    }
    template = template_map.get(level, "blue")

    elements = [{"tag": "markdown", "content": body}]
    if footer:
        elements += [
            {"tag": "hr"},
            {"tag": "note", "elements": [{"tag": "plain_text", "content": footer}]},
        ]

    try:
        import urllib.request
        payload = json.dumps({
            "msg_type": "interactive",
            "card": {
                "header": {
                    "title": {"tag": "plain_text", "content": title},
                    "template": template,
                },
                "elements": elements
            }
        }).encode("utf-8")
        req = urllib.request.Request(
            FEISHU_WEBHOOK,
            data=payload,
            headers={"Content-Type": "application/json"},
            method="POST"
        )
        with urllib.request.urlopen(req, timeout=10):
            return True
    except Exception as e:
        print(f"[Monitor] 推送失败: {e}")
        return False


def progress_bar_emoji(pct: float, width: int = 10) -> str:
    filled = int(width * pct / 100)
    return "█" * filled + "░" * (width - filled)


# ============ 反黑箱分级判断（核心）============

def classify_task_event(task_name: str, progress: float, step: str, status: str, error: str = None) -> int:
    """
    判断任务事件的反黑箱风险等级
    与 detector.py 的 RULES 逻辑对齐
    """
    # CRITICAL：核心文件删除类任务
    critical_files = ["AGENTS.md", "SOUL.md", "MEMORY.md", "IDENTITY.md", "USER.md"]
    if any(f in task_name for f in critical_files):
        return AlertLevel.CRITICAL

    # HIGH：危险操作类任务
    high_risk_patterns = [
        "git push", "git force", "强制推送", "删除仓库",
        "authorized_keys", ".ssh/", "cron 修改",
        "jobs.json", "删除全部", "清空",
    ]
    if any(p in task_name for p in high_risk_patterns):
        return AlertLevel.HIGH

    # MEDIUM：有潜在风险的任务
    medium_risk_patterns = [
        "审计", "分析", "扫描", "检测",
        "修改配置", "更新", "重命名",
    ]
    if any(p in task_name for p in medium_risk_patterns):
        return AlertLevel.MEDIUM

    # 明确错误 → 升级到 HIGH（任务无法完成）
    if error and status == "error":
        return AlertLevel.HIGH

    # SAFE/LOW：常规开发任务
    safe_patterns = ["编写", "创建", "测试", "阅读", "查询", "检查"]
    if any(p in task_name for p in safe_patterns):
        return AlertLevel.LOW

    return AlertLevel.SAFE


def classify_step_event(step: str, status: str) -> int:
    """
    根据步骤类型和状态判断风险等级
    同一任务中不同步骤可能有不同风险
    """
    # 删除/修改核心文件步骤
    if any(k in step for k in ["删除", "修改核心", "清理"]):
        return AlertLevel.HIGH

    # 外部操作步骤（git push / curl / subprocess）
    if any(k in step for k in ["git push", "curl", "wget", "subprocess", "强制"]):
        return AlertLevel.MEDIUM

    # 纯内部操作（读写文件/分析）
    if any(k in step for k in ["读取", "写入", "分析", "检查", "生成"]):
        return AlertLevel.SAFE

    # 默认低危
    return AlertLevel.SAFE


# ============ 进度推送（按等级决定行为）============

def notify_event(task_name: str, progress: float, step: str, status: str,
                 event_type: str, error: str = None, how: str = "", eta_seconds: int = 0):
    """
    事件推送主函数（与 interceptor.py 的 intercept() 逻辑对齐）
    根据风险等级决定推送深度
    """
    task_level = classify_task_event(task_name, progress, step, status, error)
    step_level = classify_step_event(step, status)
    level = max(task_level, step_level)  # 取较高者

    ts = datetime.now().strftime("%H:%M:%S")
    bar = progress_bar_emoji(progress)

    # ========== SAFE/LOW：只记录，不推送飞书 ==========
    if level <= AlertLevel.LOW:
        print(f"[Monitor] 📝 [{status}] {task_name} [{progress:.0f}%] {step}")
        return

    # ========== MEDIUM：警告卡片 ==========
    # 反黑箱：计算剩余时间和步骤进度
    eta_str = f"\n\n⏱️  预计 {eta_seconds}秒 后完成" if eta_seconds > 0 else ""
    how_str = f"\n\n🔧 做法：{how}" if how else ""
    steps_str = f"\n📋 步骤进度：{progress:.0f}%" if progress > 0 else ""

    if level == AlertLevel.MEDIUM:
        send_card(
            AlertLevel.MEDIUM,
            title=f"⚠️  {task_name}",
            body=f"**任务进行中**{eta_str}{how_str}\n\n{bar} **{progress:.0f}%**{steps_str}\n📍 **{step}**\n\n🔍 检测到潜在风险操作，请确认",
            footer=f"⏰ {ts} · 子 agent 监控推送"
        )
        return

    # ========== HIGH：拦截卡片（高危操作） ==========
    if level == AlertLevel.HIGH:
        send_card(
            AlertLevel.HIGH,
            title=f"🚨  {task_name}",
            body=f"**⚠️ 高危操作进行中**{eta_str}{how_str}\n\n{bar} **{progress:.0f}%**{steps_str}\n📍 **{step}**\n\n🚨 请确认操作，坤哥可通过审批放行",
            footer=f"⏰ {ts} · 需要坤哥关注"
        )
        return

    # ========== CRITICAL：紧急终止卡片 ==========
    if level == AlertLevel.CRITICAL:
        send_card(
            AlertLevel.CRITICAL,
            title=f"🔴  {task_name}",
            body=f"**🚨 核心文件操作**{eta_str}{how_str}\n\n⚠️ 检测到极高危任务：{task_name}\n\n{bar} **{progress:.0f}%**{steps_str}\n📍 **{step}**\n\n🔒 系统已暂停，等待坤哥紧急审批",
            footer=f"🚨 {ts} · 反黑箱 CRITICAL 级 · 强制通知"
        )
        return


def notify_started(task_name: str, total_steps: int, level: int, how: str = "", eta_seconds: int = 0):
    """任务启动通知"""
    if level <= AlertLevel.LOW:
        print(f"[Monitor] 🚀 任务启动: {task_name} ({total_steps}步)")
        return

    level_map = {
        AlertLevel.MEDIUM: ("⚠️ 任务已启动（需关注）", "yellow"),
        AlertLevel.HIGH: ("🚨 任务已启动（高危）", "red"),
        AlertLevel.CRITICAL: ("🔴 任务已启动（极高危）", "red"),
    }

    title, template = level_map.get(level, ("📊 任务已启动", "blue"))
    eta_str = f"\n\n⏱️  预计 {eta_seconds}秒 后完成" if eta_seconds > 0 else ""
    how_str = f"\n\n🔧 做法：{how}" if how else ""
    steps_str = f"\n📋 共 {total_steps} 个步骤" if total_steps > 0 else ""

    send_card(
        level,
        title=f"{title} {task_name}",
        body=f"**{task_name}**{how_str}{steps_str}{eta_str}\n\n🔄 子 agent 监控中...\n\n⚠️ 操作有风险时请确认",
        footer=f"⏰ {datetime.now().strftime('%H:%M:%S')} · 子 agent 启动推送"
    )


def notify_completion(task_name: str, final_step: str, level: int, how: str = "", eta_seconds: int = 0):
    """任务完成通知"""
    if level <= AlertLevel.LOW:
        print(f"[Monitor] ✅ 完成: {task_name}")
        return

    level_map = {
        AlertLevel.MEDIUM: ("✅ 任务已完成（请确认）", "green"),
        AlertLevel.HIGH: ("✅ 任务已完成（高危操作）", "green"),
        AlertLevel.CRITICAL: ("✅ 极高危任务已完成", "green"),
    }
    title, template = level_map.get(level, ("✅ 任务已完成", "green"))

    how_str = f"\n\n🔧 做法：{how}" if how else ""
    send_card(
        level,
        title=f"{title} {task_name}",
        body=f"**✅ 任务已完成**{how_str}\n\n**{task_name}**\n\n📍 最终状态: **{final_step}**\n🎉 所有步骤执行完毕",
        footer=f"⏰ {datetime.now().strftime('%H:%M:%S')} · 子 agent 完成推送"
    )


def notify_error(task_name: str, step: str, error_msg: str, level: int, how: str = "", eta_seconds: int = 0):
    """任务异常通知"""
    level_map = {
        AlertLevel.MEDIUM: ("⚠️ 任务异常", "yellow"),
        AlertLevel.HIGH: ("🚨 任务异常", "red"),
        AlertLevel.CRITICAL: ("🔴 任务异常（极高危）", "red"),
    }
    title, template = level_map.get(level, ("⚠️ 任务异常", "yellow"))

    how_str = f"\n\n🔧 做法：{how}" if how else ""
    send_card(
        max(level, AlertLevel.HIGH),
        title=f"{title} {task_name}",
        body=f"**❌ 任务异常中断**{how_str}\n\n**{task_name}**\n\n📍 异常步骤: **{step}**\n\n⚠️ **{error_msg}**\n\n🔍 请检查任务状态",
        footer=f"🚨 {datetime.now().strftime('%H:%M:%S')} · 子 agent 异常告警"
    )


# ============ 状态管理 ============

def load_state() -> Dict:
    if Path(NOTIFY_STATE_FILE).exists():
        try:
            return json.loads(Path(NOTIFY_STATE_FILE).read_text())
        except Exception:
            pass
    return {
        "last_progress": -1,
        "last_step": "",
        "notified_start": False,
        "notified_done": False,
        "notified_error": False,
        "last_status": "",
        "last_level": AlertLevel.SAFE,
        "last_jobId": None,
    }


def save_state(state: Dict):
    try:
        Path(NOTIFY_STATE_FILE).write_text(json.dumps(state, indent=2))
    except Exception:
        pass


# ============ 核心监控循环 ============

def load_current_progress() -> Optional[Dict]:
    """
    扫描 tasks/progress/*.json 获取最新活跃任务
    策略：
    1. 先找 current_task.json（备用兜底）
    2. 再扫所有 {job_id}.json，找最新修改的
    3. 跳过已完成/错误超过10分钟的任务
    """
    if PROGRESS_DIR.exists():
        candidates = []
        for pf in PROGRESS_DIR.glob("*.json"):
            try:
                data = json.loads(pf.read_text())
                if not data.get("jobId"):
                    continue
                # 跳过已完成/错误超过10分钟的任务
                status = data.get("status", "")
                if status in ("done", "error"):
                    updated = data.get("updatedAt", 0)
                    if isinstance(updated, str):
                        try:
                            updated = datetime.fromisoformat(updated).timestamp()
                        except Exception:
                            updated = 0
                    if time.time() - updated > 600:
                        continue
                candidates.append((pf.stat().st_mtime, data))
            except Exception:
                continue

        if candidates:
            # 按最后修改时间排序，取最新
            candidates.sort(key=lambda x: x[0], reverse=True)
            latest_data = candidates[0][1]
            # 重命名为统一字段方便后续使用
            return {
                "name": latest_data.get("name", latest_data.get("jobId", "任务")),
                "progress": latest_data.get("progress", 0),
                "status": latest_data.get("status", "running"),
                "step": latest_data.get("step", latest_data.get("currentStep", "")),
                "error": latest_data.get("error"),
                "jobId": latest_data.get("jobId"),
                "how": latest_data.get("how", ""),       # 怎么做
                "eta_seconds": latest_data.get("eta_seconds", 0),  # ETA
                "steps": latest_data.get("steps", []),   # 步骤历史
                "totalSteps": latest_data.get("totalSteps", 0),   # 总步骤数
            }


    # 兜底：current_task.json
    if PROGRESS_FILE.exists():
        try:
            data = json.loads(PROGRESS_FILE.read_text())
            return {
                "name": data.get("name", data.get("jobId", "任务")),
                "progress": data.get("progress", 0),
                "status": data.get("status", "running"),
                "step": data.get("step", data.get("currentStep", "")),
                "error": data.get("error"),
                "jobId": data.get("jobId"),
                "how": data.get("how", ""),
                "eta_seconds": data.get("eta_seconds", 0),
                "steps": data.get("steps", []),
                "totalSteps": data.get("totalSteps", 0),
            }
        except Exception:
            pass

    return None


def main():
    print(f"[TaskMonitor] 🚀 子 agent 监控启动 PID={os.getpid()}")
    print(f"[TaskMonitor] 反黑箱四级分级联动")

    os.makedirs(PROGRESS_DIR, exist_ok=True)
    state = load_state()

    while True:
        try:
            progress_data = load_current_progress()
            if progress_data is None:
                time.sleep(3)
                continue

            task_name = progress_data.get("name", "未知任务")
            progress = progress_data.get("progress", 0)
            status = progress_data.get("status", "running")
            step = progress_data.get("step", "初始化")
            error = progress_data.get("error")
            how = progress_data.get("how", "") or ""
            eta_seconds = progress_data.get("eta_seconds", 0)
            total_steps = progress_data.get("totalSteps", 0)

            # 动态计算风险等级
            level = classify_task_event(task_name, progress, step, status, error)

            # 启动通知
            if not state["notified_start"]:
                notify_started(task_name, total_steps, level, how, eta_seconds)
                state["notified_start"] = True
                state["last_level"] = level
                state["last_jobId"] = progress_data.get("jobId")
                save_state(state)

            # 进度变化推送（按风险等级）
            changed = (
                state["last_progress"] != progress or
                state["last_step"] != step or
                state["last_status"] != status
            )
            if changed and progress > 0:
                notify_event(task_name, progress, step, status, "progress", error, how, eta_seconds)
                state["last_progress"] = progress
                state["last_step"] = step
                state["last_status"] = status
                state["last_level"] = level
                save_state(state)

            # 检测任务完成（基于 jobId 判断是否是同一个任务）
            job_id = progress_data.get("jobId")
            last_job_id = state.get("last_jobId")
            if status == "done" and not state["notified_done"] and (job_id == last_job_id or not last_job_id):
                notify_completion(task_name, step, state.get("last_level", level), how, eta_seconds)
                state["notified_done"] = True
                save_state(state)
                print(f"[Monitor] ✅ 任务完成通知已推送，退出")
                break

            # 检测新任务开始（jobId 变化了，重置通知状态）
            if job_id and last_job_id and job_id != last_job_id:
                state["notified_done"] = False
                state["notified_error"] = False
                state["notified_start"] = False
                print(f"[Monitor] 🔄 检测到新任务 {job_id}，重置通知状态")

            state["last_jobId"] = job_id

            # 错误通知
            if error and not state["notified_error"]:
                notify_error(task_name, step, str(error), level, how, eta_seconds)
                state["notified_error"] = True
                save_state(state)
                break

            time.sleep(3)

        except KeyboardInterrupt:
            print("[TaskMonitor] ⏹️ 退出")
            break
        except Exception as e:
            print(f"[Monitor] ⚠️ 异常: {e}")
            time.sleep(5)


if __name__ == "__main__":
    main()
