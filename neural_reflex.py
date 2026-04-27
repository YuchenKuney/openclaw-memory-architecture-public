#!/usr/bin/env python3
"""
neural_reflex.py - 条件反射弧实现

条件反射：满足特定条件时自动触发预设动作，无需经过中枢

架构：
  中枢注册反射弧 → 节点保存 → 节点自主检测 → 触发动作

示例：
  - "CPU > 80%" → 自动发送告警到中枢
  - "磁盘 < 10%" → 自动清理临时文件
  - "收到特定信号" → 执行预设命令序列
"""

import os
import re
import sys
import json
import time
import subprocess
from pathlib import Path
from datetime import datetime
from typing import Dict, List, Optional, Callable

WORKSPACE = Path("/root/.openclaw/workspace")
REFLEX_FILE = WORKSPACE / "neural_reflexes.json"
REFLEX_LOG = WORKSPACE / "neural_reflex_log.jsonl"


class ReflexCondition:
    """反射条件"""

    def __init__(self, condition_type: str, threshold: float, comparison: str = ">"):
        self.condition_type = condition_type  # cpu/memory/disk/load/custom
        self.threshold = threshold
        self.comparison = comparison  # > / < / == / >= / <=

    def evaluate(self, metrics: dict) -> bool:
        """评估条件是否满足"""
        if self.condition_type == "cpu":
            value = metrics.get("cpu_load", 0)
        elif self.condition_type == "memory":
            value = metrics.get("memory_percent", 0)
        elif self.condition_type == "disk":
            value = metrics.get("disk_percent", 0)
        elif self.condition_type == "load":
            value = metrics.get("load_1min", 0)
        else:
            value = 0

        ops = {
            ">": lambda a, b: a > b,
            "<": lambda a, b: a < b,
            "==": lambda a, b: a == b,
            ">=": lambda a, b: a >= b,
            "<=": lambda a, b: a <= b,
        }
        op = ops.get(self.comparison, lambda a, b: False)
        return op(value, self.threshold)

    def describe(self) -> str:
        return f"{self.condition_type} {self.comparison} {self.threshold}"


class ReflexAction:
    """反射动作"""

    def __init__(self, action_type: str, params: dict):
        self.action_type = action_type  # exec / alert / sense / signal
        self.params = params

    def execute(self) -> dict:
        """执行动作"""
        if self.action_type == "exec":
            cmd = self.params.get("command", "")
            if cmd:
                result = subprocess.run(cmd, shell=True, capture_output=True, text=True, timeout=30)
                return {"status": "ok", "stdout": result.stdout[:500], "returncode": result.returncode}

        elif self.action_type == "alert":
            # 发送告警到中枢（通过信号）
            message = self.params.get("message", "节点告警")
            print(f"[ReflexAction] 🚨 告警: {message}")
            return {"status": "ok", "alert_sent": True, "message": message}

        elif self.action_type == "sense":
            # 采集更多数据
            sense_type = self.params.get("type", "system")
            print(f"[ReflexAction] 💾 感知: {sense_type}")
            return {"status": "ok", "sense_type": sense_type}

        return {"status": "ok", "action": self.action_type}


class ReflexArc:
    """条件反射弧"""

    def __init__(self, arc_id: str, condition: ReflexCondition, action: ReflexAction,
                 name: str = "", enabled: bool = True, description: str = ""):
        self.arc_id = arc_id
        self.name = name or arc_id
        self.condition = condition
        self.action = action
        self.enabled = enabled
        self.description = description
        self.trigger_count = 0
        self.last_triggered = None

    def to_dict(self):
        return {
            "arc_id": self.arc_id,
            "name": self.name,
            "condition_type": self.condition.condition_type,
            "condition_threshold": self.condition.threshold,
            "condition_comparison": self.condition.comparison,
            "action_type": self.action.action_type,
            "action_params": self.action.params,
            "enabled": self.enabled,
            "description": self.description,
            "trigger_count": self.trigger_count,
            "last_triggered": self.last_triggered,
        }

    @staticmethod
    def from_dict(d: dict):
        cond = ReflexCondition(
            d["condition_type"],
            d["condition_threshold"],
            d.get("condition_comparison", ">")
        )
        act = ReflexAction(d["action_type"], d.get("action_params", {}))
        arc = ReflexArc(d["arc_id"], cond, act, d.get("name", ""),
                       d.get("enabled", True), d.get("description", ""))
        arc.trigger_count = d.get("trigger_count", 0)
        arc.last_triggered = d.get("last_triggered")
        return arc

    def check_and_fire(self, metrics: dict) -> Optional[dict]:
        """检查条件并触发"""
        if not self.enabled:
            return None

        if self.condition.evaluate(metrics):
            self.trigger_count += 1
            self.last_triggered = datetime.now().isoformat()
            result = self.action.execute()
            return {
                "arc_id": self.arc_id,
                "name": self.name,
                "condition_met": self.condition.describe(),
                "action_result": result,
                "triggered_at": self.last_triggered,
            }
        return None


class ReflexRegistry:
    """反射弧注册表（中枢端）"""

    def __init__(self):
        self.arcs: Dict[str, ReflexArc] = {}
        self.load()

    def load(self):
        if REFLEX_FILE.exists():
            try:
                data = json.loads(REFLEX_FILE.read_text())
                for d in data.get("arcs", []):
                    arc = ReflexArc.from_dict(d)
                    self.arcs[arc.arc_id] = arc
            except Exception as e:
                print(f"[ReflexRegistry] 加载失败: {e}")

    def save(self):
        data = {"arcs": [arc.to_dict() for arc in self.arcs.values()]}
        REFLEX_FILE.write_text(json.dumps(data, indent=2, ensure_ascii=False))

    def register(self, arc: ReflexArc):
        """注册反射弧"""
        self.arcs[arc.arc_id] = arc
        self.save()
        print(f"[ReflexRegistry] ✅ 注册反射弧: {arc.arc_id} - {arc.name}")
        print(f"    条件: {arc.condition.describe()}")
        print(f"    动作: {arc.action.action_type}")

    def register_reflex(self, target_node: str, condition: str, action: dict) -> dict:
        """
        注册条件反射弧（供signal调用）

        Args:
            target_node: 目标节点
            condition: 条件字符串（如 "cpu > 80"）
            action: 动作参数

        Returns:
            注册结果
        """
        # 解析条件字符串
        # 格式: "cpu > 80" / "disk < 10" / "memory >= 90"
        parts = condition.split()
        if len(parts) >= 3:
            cond_type = parts[0]
            comp = parts[1]
            threshold = float(parts[2])
        else:
            cond_type = "cpu"
            comp = ">"
            threshold = 80

        cond = ReflexCondition(cond_type, threshold, comp)
        act = ReflexAction(action.get("type", "exec"), action.get("params", action))

        arc_id = f"reflex_{target_node}_{int(time.time()*1000)}"
        arc = ReflexArc(arc_id, cond, act, f"{target_node}_{cond_type}_reflex")
        self.register(arc)

        return {"status": "ok", "arc_id": arc_id, "registered_to": target_node}

    def get_all_arcs(self) -> List[dict]:
        """获取所有反射弧"""
        return [arc.to_dict() for arc in self.arcs.values()]

    def remove(self, arc_id: str):
        """删除反射弧"""
        if arc_id in self.arcs:
            del self.arcs[arc_id]
            self.save()
            return {"status": "ok"}
        return {"status": "not_found"}


class ReflexRunner:
    """
    反射弧运行器（节点端）

    定期检查所有反射弧的条件，满足则触发
    """

    def __init__(self, registry_path: str = None):
        self.registry_path = Path(registry_path) if registry_path else REFLEX_FILE
        self.arcs: List[ReflexArc] = []
        self.last_check = None
        self.load()

    def load(self):
        """从注册表加载反射弧"""
        if self.registry_path.exists():
            try:
                data = json.loads(self.registry_path.read_text())
                for d in data.get("arcs", []):
                    self.arcs.append(ReflexArc.from_dict(d))
            except Exception:
                pass

    def get_metrics(self) -> dict:
        """获取当前系统指标"""
        metrics = {}
        try:
            # CPU load
            with open("/proc/loadavg") as f:
                load = f.read().split()
                metrics["load_1min"] = float(load[0])
                metrics["load_5min"] = float(load[1])
                metrics["load_15min"] = float(load[2])

            # Memory
            with open("/proc/meminfo") as f:
                mem = {}
                for line in f:
                    if ":" in line:
                        k, v = line.split(":")
                        mem[k.strip()] = int(v.strip().split()[0])

                total = mem.get("MemTotal", 1)
                avail = mem.get("MemAvailable", 0)
                used = total - avail
                metrics["memory_percent"] = round(used / total * 100, 1)
                metrics["memory_mb"] = used // 1024

            # Disk
            result = subprocess.run("df -h / | tail -1 | awk '{print $5,$4}'",
                                  shell=True, capture_output=True, text=True)
            parts = result.stdout.strip().split()
            if parts:
                metrics["disk_percent"] = int(parts[0].replace("%", ""))
                metrics["disk_free"] = parts[1] if len(parts) > 1 else "?"

        except Exception as e:
            print(f"[ReflexRunner] 获取指标失败: {e}")

        return metrics

    def check_and_fire(self, metrics: dict = None) -> List[dict]:
        """检查所有反射弧，触发满足条件的"""
        if metrics is None:
            metrics = self.get_metrics()

        triggered = []
        for arc in self.arcs:
            result = arc.check_and_fire(metrics)
            if result:
                triggered.append(result)
                # 记录到日志
                self._log_reflex(result)

        self.last_check = datetime.now().isoformat()
        return triggered

    def _log_reflex(self, result: dict):
        """记录反射弧触发日志"""
        try:
            entry = {**result, "logged_at": datetime.now().isoformat()}
            with open(REFLEX_LOG, "a") as f:
                f.write(json.dumps(entry, ensure_ascii=False) + "\n")
        except Exception:
            pass

    def run_daemon(self, interval: int = 30):
        """持续检查反射弧"""
        print(f"[ReflexRunner] 🧠 反射弧运行器启动（每{interval}秒检查）")
        print(f"[ReflexRunner] 加载 {len(self.arcs)} 个反射弧")

        while True:
            try:
                metrics = self.get_metrics()
                triggered = self.check_and_fire(metrics)

                if triggered:
                    print(f"[{datetime.now().strftime('%H:%M:%S')}] 🚨 触发 {len(triggered)} 个反射弧:")
                    for t in triggered:
                        print(f"  - {t['name']}: {t['condition_met']}")

                time.sleep(interval)
            except KeyboardInterrupt:
                print("\n[ReflexRunner] 停止")
                break
            except Exception as e:
                print(f"[ReflexRunner] 异常: {e}")
                time.sleep(interval)


def setup_default_reflexes():
    """设置默认反射弧"""
    registry = ReflexRegistry()

    # 反射1: CPU > 80% 时发送告警
    arc1 = ReflexArc(
        "cpu_high_alert",
        ReflexCondition("cpu", 80, ">="),
        ReflexAction("alert", {"message": "CPU使用率超过80%"}),
        name="CPU过载告警",
        description="CPU超过80%时自动告警"
    )
    registry.register(arc1)

    # 反射2: 磁盘 < 10% 时自动清理
    arc2 = ReflexArc(
        "disk_low_cleanup",
        ReflexCondition("disk", 10, "<="),
        ReflexAction("exec", {"command": "rm -rf /tmp/*.log /root/.openclaw/workspace/logs/*.log 2>/dev/null; echo cleaned"}),
        name="磁盘不足自动清理",
        description="磁盘空间低于10%时自动清理临时文件"
    )
    registry.register(arc2)

    return registry


def main():
    if "--setup" in sys.argv:
        # 设置默认反射弧
        registry = setup_default_reflexes()
        print(f"✅ 已设置 {len(registry.arcs)} 个默认反射弧")
        for arc in registry.arcs.values():
            print(f"  - {arc.name}: {arc.condition.describe()}")
        return

    if "--run" in sys.argv:
        # 运行反射弧检查器（节点端）
        runner = ReflexRunner()
        interval = int(sys.argv[2]) if len(sys.argv) > 2 else 30
        runner.run_daemon(interval)
        return

    if "--check" in sys.argv:
        # 单次检查
        runner = ReflexRunner()
        metrics = runner.get_metrics()
        print("当前指标:", metrics)
        triggered = runner.check_and_fire(metrics)
        if triggered:
            print(f"触发: {triggered}")
        else:
            print("无反射弧触发")
        return

    # 中枢端：注册反射弧
    registry = ReflexRegistry()

    if len(sys.argv) > 1 and sys.argv[1] == "--register":
        # --register <target> <condition> <action_type> <action_params_json>
        target = sys.argv[2] if len(sys.argv) > 2 else "singapore"
        condition = sys.argv[3] if len(sys.argv) > 3 else "cpu > 80"
        action_type = sys.argv[4] if len(sys.argv) > 4 else "alert"
        action_params = json.loads(sys.argv[5]) if len(sys.argv) > 5 else {"message": "test"}
        result = registry.register_reflex(target, condition, {"type": action_type, "params": action_params})
        print(json.dumps(result, indent=2))
        return

    # 列出所有反射弧
    print("🧠 反射弧注册表")
    print(f"共 {len(registry.arcs)} 个反射弧:")
    for arc in registry.arcs.values():
        print(f"  [{arc.arc_id}] {arc.name}")
        print(f"    条件: {arc.condition.describe()}")
        print(f"    动作: {arc.action.action_type} - {arc.action.params}")


if __name__ == "__main__":
    main()