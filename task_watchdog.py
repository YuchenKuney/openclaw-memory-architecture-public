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
MONITOR_SCRIPT = WORKSPACE / "task_monitor.py"
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


# ============ 飞书推送 ============

def send_simple_msg(msg: str, level: str = "INFO"):
    """发送飞书文本消息"""
    try:
        import urllib.request
        emoji_map = {"INFO": "ℹ️", "WARN": "⚠️", "ERROR": "❌", "SUCCESS": "✅", "HEARTBEAT": "💓"}
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


def send_card(title: str, content: str, template: str = "blue"):
    """发送飞书卡片"""
    try:
        import urllib.request
        payload = json.dumps({
            "msg_type": "interactive",
            "card": {
                "header": {"title": {"tag": "plain_text", "content": title}, "template": template},
                "elements": [{"tag": "markdown", "content": content}, {"tag": "hr"},
                    {"tag": "note", "elements": [{"tag": "plain_text", "content": f"🐕 看门狗 · {datetime.now().strftime('%H:%M:%S')}"}]}]
            }
        }).encode("utf-8")
        req = urllib.request.Request(FEISHU_WEBHOOK, data=payload,
            headers={"Content-Type": "application/json"}, method="POST")
        with urllib.request.urlopen(req, timeout=5):
            pass
    except Exception:
        pass


# ============ 进程管理 ============

def is_process_alive(pid: int) -> bool:
    """检查进程是否存活"""
    try:
        os.kill(pid, 0)
        return True
    except OSError:
        return False


def get_monitor_pid() -> Optional[int]:
    """获取 task_monitor.py 的 PID"""
    try:
        result = subprocess.run(
            ["pgrep", "-f", "task_monitor.py"],
            capture_output=True, text=True
        )
        if result.returncode == 0 and result.stdout.strip():
            return int(result.stdout.strip().split()[0])
    except Exception:
        pass
    return None


def start_monitor_process() -> Optional[int]:
    """启动 task_monitor.py，返回 PID"""
    try:
        proc = subprocess.Popen(
            [sys.executable, str(MONITOR_SCRIPT)],
            cwd=str(WORKSPACE),
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            start_new_session=True
        )
        return proc.pid
    except Exception as e:
        print(f"[Watchdog] 启动失败: {e}")
        return None


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
    return {"monitor_pid": None, "last_restart": None, "restart_count": 0, "last_heartbeat": None}


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
            "pid": state.get("monitor_pid"),
            "updated": now,
            "restarts": state.get("restart_count", 0),
        }, indent=2))
    except Exception:
        pass
    save_state(state)


def send_heartbeat(state: Dict):
    """发送心跳到飞书"""
    now = datetime.now().strftime("%H:%M:%S")
    pid = state.get("monitor_pid")
    restarts = state.get("restart_count", 0)
    alive = state.get("monitor_alive", False)
    status = "🟢 存活" if alive else "🔴 已停止"
    send_simple_msg(f"🐕 看门狗心跳 {now} | 监控进程: {status} | PID: {pid} | 重启: {restarts}次", "HEARTBEAT")


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

    state = load_state()
    last_heartbeat = time.time()
    last_integrity_check = time.time()

    while True:
        try:
            current_pid = state.get("monitor_pid")
            alive = current_pid and is_process_alive(current_pid)

            if not alive:
                # 进程挂了，需要重启
                state["restart_count"] = state.get("restart_count", 0) + 1
                state["last_restart"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                print(f"[Watchdog] ⚠️ 监控进程已停止（PID={current_pid}），尝试重启 #{state['restart_count']}")

                send_card(
                    "🐕 看门狗重启监控进程",
                    f"⚠️ task_monitor 进程已停止（挂了第{state['restart_count']}次）\n\n自动拉起中...",
                    "yellow"
                )

                new_pid = start_monitor_process()
                if new_pid:
                    state["monitor_pid"] = new_pid
                    print(f"[Watchdog] ✅ 监控进程已重启，新 PID={new_pid}")
                    send_simple_msg(f"✅ 监控进程已拉起 PID={new_pid}", "SUCCESS")
                else:
                    print(f"[Watchdog] ❌ 重启失败")
                    send_simple_msg("❌ 监控进程重启失败，10秒后重试", "ERROR")

            # 更新心跳
            update_heartbeat(state, alive)

            # 每 30 秒发送一次心跳
            if time.time() - last_heartbeat >= 30:
                send_heartbeat(state)
                last_heartbeat = time.time()

            # 每 5 分钟检查 memory 完整性
            if time.time() - last_integrity_check >= 300:
                result = check_memory_integrity()
                if result.get("status") == "compromised":
                    send_card(
                        "🐕 看门狗完整性告警",
                        f"⚠️ memory/ 目录发生变化！\n\n新增: {len(result.get('added', []))}\n篡改: {len(result.get('changed', []))}",
                        "red"
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
        if state.get("monitor_pid"):
            stop_monitor_process(state["monitor_pid"])


def main():
    import argparse
    parser = argparse.ArgumentParser(description="Task Watchdog - 看门狗守护进程")
    parser.add_argument("--daemon", action="store_true", help="后台运行")
    parser.add_argument("--once", action="store_true", help="单次检测后退出")
    args = parser.parse_args()

    if args.daemon:
        pid = os.fork()
        if pid > 0:
            print(f"[Watchdog] 🚀 已后台化，PID={pid}")
            return
        os.chdir("/")
        os.setsid()

    watchdog_loop(daemon=args.daemon, once=args.once)


if __name__ == "__main__":
    main()
