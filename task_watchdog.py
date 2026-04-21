#!/usr/bin/env python3
"""
Task Watchdog - 守护子 agent 不挂

功能：
  1. 监控 task_monitor.py 子 agent 进程是否存活
  2. 进程挂了自动拉起（不死）
  3. 每 30 秒发送心跳到飞书群
  4. 检测 memory/ 完整性（在子 agent 监控的基础上）
  5. 进程监控 + 文件监控 + 心跳 三合一

调用方式：
  python3 task_watchdog.py              # 正常启动（前台打印）
  python3 task_watchdog.py --daemon     # 后台运行
  python3 task_watchdog.py --once      # 单次检测后退出（用于调试）
"""

import os
import sys
import json
import time
import signal
import subprocess
import hashlib
from pathlib import Path
from datetime import datetime
from typing import Optional, Dict, List

WORKSPACE = Path("/root/.openclaw/workspace")
# 要监控的脚本列表（看门狗都会自动拉起）
MONITOR_SCRIPTS = {
    "task_monitor": WORKSPACE / "task_monitor.py",
    "task_agent": WORKSPACE / "scripts" / "task_monitor_agent.py",
}
STATE_FILE = WORKSPACE / ".watchdog_state.json"
HEARTBEAT_FILE = WORKSPACE / ".watchdog_heartbeat.json"
FEISHU_WEBHOOK = os.environ.get(
    "FEISHU_WEBHOOK",
    "https://open.feishu.cn/open-apis/bot/v2/hook/7a939580-e987-4571-a142-f58528cf71ec"
)
FEISHU_GROUP = os.environ.get(
    "FEISHU_GROUP_ID",
    "oc_0533b03e077fedca255c4d2c6717deea"
)


# ============ 反黑箱四级分级（与 interceptor.py 一致）============

class AlertLevel:
    SAFE = 0
    LOW = 1
    MEDIUM = 2
    HIGH = 3
    CRITICAL = 4


# ============ 飞书推送 ============

def send_simple_msg(msg: str, level: str = "INFO"):
    """发送飞书文本消息"""
    try:
        import urllib.request
        emoji_map = {
            "INFO": "ℹ️", "WARN": "⚠️", "ERROR": "❌",
            "SUCCESS": "✅", "HEARTBEAT": "💓",
            "SAFE": "✅", "LOW": "📝", "MEDIUM": "⚠️",
            "HIGH": "🚨", "CRITICAL": "🔴",
        }
        payload = json.dumps({
            "msg_type": "text",
            "content": {"text": f"{emoji_map.get(level, 'ℹ️')} [{level}] {msg}"}
        }).encode("utf-8")
        req = urllib.request.Request(FEISHU_WEBHOOK, data=payload,
            headers={"Content-Type": "application/json"}, method="POST")
        with urllib.request.urlopen(req, timeout=5):
            pass
    except Exception:
        pass


ALERT_TEMPLATE = {
    0: ("blue", "✅"),
    1: ("blue", "📝"),
    2: ("yellow", "⚠️"),
    3: ("red", "🚨"),
    4: ("red", "🔴"),
}


def send_watchdog_card(title: str, body: str, alert_level: int = 0):
    """发送看门狗卡片（按反黑箱等级决定颜色）"""
    template, _ = ALERT_TEMPLATE.get(alert_level, ("blue", "ℹ️"))
    try:
        import urllib.request
        payload = json.dumps({
            "msg_type": "interactive",
            "card": {
                "header": {
                    "title": {"tag": "plain_text", "content": title},
                    "template": template,
                },
                "elements": [
                    {"tag": "markdown", "content": body},
                    {"tag": "hr"},
                    {"tag": "note", "elements": [
                        {"tag": "plain_text", "content": f"🐕 看门狗 · {datetime.now().strftime('%H:%M:%S')}"}
                    ]}
                ]
            }
        }).encode("utf-8")
        req = urllib.request.Request(FEISHU_WEBHOOK, data=payload,
            headers={"Content-Type": "application/json"}, method="POST")
        with urllib.request.urlopen(req, timeout=5):
            pass
    except Exception:
        pass


def get_current_task_info() -> tuple:
    """获取当前任务信息（用于心跳报告）"""
    try:
        state_file = Path(WORKSPACE) / ".monitor_state.json"
        if state_file.exists():
            state = json.loads(state_file.read_text())
            return state.get("last_step", "无"), state.get("last_level", 0)
    except Exception:
        pass
    return "无", 0


# ============ 进程管理 ============

def is_process_alive(pid: int) -> bool:
    """检查进程是否存活"""
    try:
        os.kill(pid, 0)
        return True
    except OSError:
        return False


def get_monitor_pids() -> dict:
    """获取所有被监控脚本的 PID，返回 {脚本名: pid}"""
    pids = {}
    for name, script_path in MONITOR_SCRIPTS.items():
        try:
            result = subprocess.run(
                ["pgrep", "-f", script_path.name],
                capture_output=True, text=True
            )
            if result.returncode == 0 and result.stdout.strip():
                pid_str = result.stdout.strip().split()[0]
                pids[name] = int(pid_str)
        except Exception:
            pass
    return pids


def start_all_monitors() -> dict:
    """启动所有被监控脚本，返回 {脚本名: pid}"""
    started = {}
    for name, script_path in MONITOR_SCRIPTS.items():
        try:
            # 检查是否已经在运行
            existing = subprocess.run(
                ["pgrep", "-f", script_path.name],
                capture_output=True, text=True
            )
            if existing.returncode == 0 and existing.stdout.strip():
                # 已经在运行
                pid = int(existing.stdout.strip().split()[0])
                started[name] = pid
                print(f"[Watchdog] {name} 已在运行 PID={pid}")
                continue

            # 启动新进程
            proc = subprocess.Popen(
                [sys.executable, str(script_path)],
                cwd=str(WORKSPACE),
                stdin=subprocess.DEVNULL,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                start_new_session=True
            )
            started[name] = proc.pid
            print(f"[Watchdog] ✅ {name} 已启动 PID={proc.pid}")
        except Exception as e:
            print(f"[Watchdog] ❌ {name} 启动失败: {e}")
    return started


def stop_monitor_process(pid: int):
    """停止监控进程"""
    try:
        os.kill(pid, signal.SIGTERM)
        time.sleep(1)
        try:
            os.kill(pid, signal.SIGKILL)
        except OSError:
            pass
    except OSError:
        pass


# ============ 状态管理 ============

def load_state() -> Dict:
    if Path(STATE_FILE).exists():
        try:
            return json.loads(Path(STATE_FILE).read_text())
        except Exception:
            pass
    return {"monitor_pids": {}, "last_restart": None, "restart_count": 0, "last_heartbeat": None, "monitored": list(MONITOR_SCRIPTS.keys())}


def save_state(state: Dict):
    try:
        Path(STATE_FILE).write_text(json.dumps(state, indent=2))
    except Exception:
        pass


# ============ 看门狗心跳 ============

def update_heartbeat(state: Dict, monitor_alive: bool):
    """更新心跳"""
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    state["last_heartbeat"] = now
    state["monitor_alive"] = monitor_alive
    try:
        Path(HEARTBEAT_FILE).write_text(json.dumps({
            "alive": monitor_alive,
            "monitored": list(MONITOR_SCRIPTS.keys()),
            "pids": state.get("monitor_pids", {}),
            "updated": now,
            "restarts": state.get("restart_count", 0),
        }, indent=2))
    except Exception:
        pass
    save_state(state)


def send_heartbeat(state: Dict):
    """发送心跳到飞书（带当前任务风险等级）"""
    step, level = get_current_task_info()
    level_names = ["SAFE", "LOW", "MEDIUM", "HIGH", "CRITICAL"]
    level_name = level_names[level] if level < len(level_names) else "UNKNOWN"
    now = datetime.now().strftime("%H:%M:%S")
    pids = state.get("monitor_pids", {})
    restarts = state.get("restart_count", 0)
    # 显示所有监控进程状态
    proc_status = []
    for name, pid in pids.items():
        alive = is_process_alive(pid) if pid else False
        s = f"{name}={'🟢' if alive else '🔴'}(PID={pid})"
        proc_status.append(s)
    proc_info = " | ".join(proc_status) if proc_status else "无"
    send_simple_msg(
        f"🐕 看门狗心跳 {now} | 监控: {proc_info} | 重启:{restarts}次 | 当前:{level_name} | {step}",
        level_name,
    )


# ============ memory 完整性检查（额外功能）============

def check_memory_integrity() -> dict:
    """检查 memory/ 完整性"""
    try:
        sys.path.insert(0, str(WORKSPACE))
        from clawkeeper.detector import RiskDetector
        detector = RiskDetector()
        detector.save_integrity_manifest()

        from clawkeeper.auditor import Auditor
        auditor = Auditor()
        result = auditor._check_file_integrity()
        return result
    except Exception as e:
        return {"status": "error", "error": str(e)}


# ============ 主循环 ============

def watchdog_loop(daemon: bool = False, once: bool = False):
    """看门狗主循环"""
    print(f"[Watchdog] 🚀 看门狗启动 PID={os.getpid()} {'(daemon)' if daemon else ''}")
    send_simple_msg("🐕 看门狗已启动", "INFO")

    # 启动时确保所有被监控脚本都在运行
    state = load_state()
    initial_pids = start_all_monitors()
    if initial_pids:
        state["monitor_pids"] = initial_pids
        save_state(state)
        pids_str = " | ".join(f"{k}={v}" for k, v in initial_pids.items())
        print(f"[Watchdog] ✅ 启动时拉起监控进程: {pids_str}")
    last_heartbeat = time.time()
    last_integrity_check = time.time()

    while True:
        try:
            current_pids = get_monitor_pids()
            for name, script_path in MONITOR_SCRIPTS.items():
                pid = current_pids.get(name)
                alive = pid and is_process_alive(pid)
                if not alive:
                    state["restart_count"] = state.get("restart_count", 0) + 1
                    state["last_restart"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                    restart_count = state["restart_count"]
                    print(f"[Watchdog] ⚠️ {name} 进程已停止，尝试重启 #{restart_count}")
                    # 只在重启次数过多时告警（避免刷屏）
                    if restart_count >= 5:
                        msg = f"⚠️ {name} 进程挂了 {restart_count} 次（频繁重启）\n🔄 自动拉起中..."
                        send_simple_msg(msg, "WARN")
                    else:
                        # 重启次数少，不打扰坤哥，静默拉起
                        print(f"[Watchdog] ⚠️ 重启次数少（{restart_count}次），静默拉起")
                    new_pids = start_all_monitors()
                    current_pids.update(new_pids)
            update_heartbeat(state, alive)

            # 每 30 秒更新一次心跳文件（不通知）
            if time.time() - last_heartbeat >= 30:
                last_heartbeat = time.time()

            # 每 5 分钟检查 memory 完整性
            if time.time() - last_integrity_check >= 300:
                result = check_memory_integrity()
                if result.get("status") == "compromised":
                    send_watchdog_card(
                        "🐕 看门狗完整性告警",
                        f"⚠️ memory/ 目录发生变化！\n\n新增: {len(result.get('added', []))}\n篡改: {len(result.get('changed', []))}",
                        alert_level=3,
                    )
                last_integrity_check = time.time()

            if once:
                print("[Watchdog] ✅ 单次检测完成，退出")
                break

            time.sleep(5)  # 每 5 秒检查一次

        except KeyboardInterrupt:
            if daemon:
                print("[Watchdog] ⏹️ 收到终止信号，继续运行...")
                continue
            print("[Watchdog] ⏹️ 收到终止信号，退出")
            send_simple_msg("🐕 看门狗已停止", "WARN")
            break
        except Exception as e:
            print(f"[Watchdog] ⚠️ 主循环异常: {e}")
            time.sleep(5)

    # 清理（daemon 不清理）
    if not daemon:
        for pid in state.get("monitor_pids", {}).values():
            stop_monitor_process(pid)


def main():
    import argparse
    parser = argparse.ArgumentParser(description="Task Watchdog - 看门狗守护进程")
    parser.add_argument("--daemon", action="store_true", help="后台运行")
    parser.add_argument("--once", action="store_true", help="单次检测后退出")
    parser.add_argument("--systemd", action="store_true", help="前台运行（systemd 使用，不 fork）")
    args = parser.parse_args()

    # 前台运行（systemd 环境或调试用）
    is_daemon = args.daemon and not getattr(args, 'systemd', False)

    if is_daemon:
        pid = os.fork()
        if pid > 0:
            pid_file = WORKSPACE / ".watchdog.pid"
            pid_file.write_text(str(pid))
            print(f"[Watchdog] 🚀 已后台化，PID={pid}")
            import time; time.sleep(2)
            return
        os.chdir("/")
        os.setsid()
        os.umask(0o022)

    watchdog_loop(daemon=is_daemon, once=args.once)
if __name__ == "__main__":
    main()
