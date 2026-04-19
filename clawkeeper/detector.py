#!/usr/bin/env python3
"""
Clawkeeper Detector - 行为风险检测引擎
根据事件类型和文件类型判断危险等级，决定拦截/审核/放行
"""

import os
import json
import time
from enum import IntEnum
from pathlib import Path


class RiskLevel(IntEnum):
    """风险等级"""
    SAFE = 0        # 安全，放行
    LOW = 1         # 低风险，记录日志
    MEDIUM = 2      # 中风险，暂停+通知
    HIGH = 3        # 高风险，拦截+立即通知
    CRITICAL = 4    # 极高风险，拦截+立即通知+挂起AI


class Action:
    """动作对象"""
    def __init__(self, level, action_type, message, details=None, can_proceed=False):
        self.level = level
        self.action_type = action_type  # BLOCK / PAUSE / ALLOW / LOG
        self.message = message
        self.details = details or {}
        self.can_proceed = can_proceed  # AI 能否继续
        self.timestamp = time.time()
        
    def to_dict(self):
        return {
            "level": self.level,
            "action_type": self.action_type,
            "message": self.message,
            "details": self.details,
            "can_proceed": self.can_proceed,
            "timestamp": self.timestamp,
        }


class RiskDetector:
    """风险检测器"""
    
    # 危险操作规则
    RULES = {
        # 核心文件删除 → 极高风险
        ("AGENTS.md", "DELETE"): RiskLevel.CRITICAL,
        ("SOUL.md", "DELETE"): RiskLevel.CRITICAL,
        ("MEMORY.md", "DELETE"): RiskLevel.CRITICAL,
        ("IDENTITY.md", "DELETE"): RiskLevel.CRITICAL,
        ("USER.md", "DELETE"): RiskLevel.CRITICAL,
        ("HEARTBEAT.md", "DELETE"): RiskLevel.CRITICAL,
        
        # 核心文件修改 → 高风险
        ("AGENTS.md", "MODIFY"): RiskLevel.HIGH,
        ("SOUL.md", "MODIFY"): RiskLevel.HIGH,
        ("MEMORY.md", "MODIFY"): RiskLevel.HIGH,
        
        # 核心目录删除 → 高风险
        ("tasks/", "DELETE"): RiskLevel.HIGH,
        ("memory/", "DELETE"): RiskLevel.HIGH,
        ("shared/", "DELETE"): RiskLevel.HIGH,

        # cron-events/ 目录 → 任务调度通知（创建/修改都是正常的定时任务触发）
        ("cron-events/", "CREATE"): RiskLevel.SAFE,
        ("cron-events/", "MODIFY"): RiskLevel.SAFE,
        ("cron-events/", "DELETE"): RiskLevel.MEDIUM,
        ("tasks/", "CREATE"): RiskLevel.SAFE,
        ("tasks/", "MODIFY"): RiskLevel.SAFE,
        
        # 公共仓 push 操作 → 中风险
        ("PUBLIC_PUSH", "GIT"): RiskLevel.MEDIUM,
        
        # .gitignore 修改 → 中风险
        (".gitignore", "MODIFY"): RiskLevel.MEDIUM,
        
        # 核心文件创建 → 低风险
        ("AGENTS.md", "CREATE"): RiskLevel.LOW,
        ("SOUL.md", "CREATE"): RiskLevel.LOW,
    }
    
    def __init__(self, config_path=None):
        self.config_path = config_path or os.environ.get("CLAWKEEPER_CONFIG", 
            "/root/.openclaw/workspace/clawkeeper/config.json")
        self.config = self._load_config()
        self.notification_level = self.config.get("notification_level", "MEDIUM")
        self.audit_log_path = self.config.get("audit_log", 
            "/root/.openclaw/workspace/clawkeeper/audit.log")
        self.auto_allow = self.config.get("auto_allow", False)
        
    def _load_config(self):
        """加载配置（支持 YAML 和 JSON）"""
        yaml_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), "config.yaml")
        json_path = self.config_path

        # 优先读 YAML
        if os.path.exists(yaml_path):
            try:
                import yaml as _yaml
                with open(yaml_path, 'r', encoding='utf-8') as f:
                    cfg = _yaml.safe_load(f)
                notification = cfg.get('notification', {})
                audit = cfg.get('audit', {})
                return {
                    'notification_level': notification.get('level', 'MEDIUM'),
                    'audit_log': '/root/.openclaw/workspace/clawkeeper/audit.log',
                    'auto_allow': audit.get('auto_allow', False),
                }
            except:
                pass

        # 回退读 JSON
        if os.path.exists(json_path):
            try:
                with open(json_path) as f:
                    return json.load(f)
            except:
                pass
        return {"notification_level": "MEDIUM", "audit_log": "/root/.openclaw/workspace/clawkeeper/audit.log", "auto_allow": False}

    def backup_core_file(self, file_path):
        """
        备份核心文件到 backup/ 目录
        
        Args:
            file_path: 文件路径
            
        Returns:
            backup_path: 备份文件路径，如果失败返回 None
        """
        import shutil
        from datetime import datetime
        
        try:
            path = Path(file_path)
            if not path.exists():
                return None
            
            # 创建备份目录
            backup_dir = Path(self.workspace) / "clawkeeper" / "backup"
            backup_dir.mkdir(parents=True, exist_ok=True)
            
            # 生成带时间戳的备份文件名
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            backup_name = f"{path.name}.{timestamp}.bak"
            backup_path = backup_dir / backup_name
            
            # 复制文件
            shutil.copy2(path, backup_path)
            print(f"[Detector] 已备份核心文件: {path} -> {backup_path}")
            return backup_path
            
        except Exception as e:
            print(f"[Detector] 备份失败: {e}")
            return None

    def restore_core_file(self, backup_path, target_path):
        """
        从备份恢复核心文件
        
        Args:
            backup_path: 备份文件路径
            target_path: 目标文件路径
            
        Returns:
            bool: 是否成功
        """
        import shutil
        
        try:
            shutil.copy2(backup_path, target_path)
            print(f"[Detector] 已恢复核心文件: {backup_path} -> {target_path}")
            return True
        except Exception as e:
            print(f"[Detector] 恢复失败: {e}")
            return False
        
    def _get_rule_level(self, path, event_type):
        """获取规则匹配的风险等级"""
        filename = Path(path).name
        
        # 精确匹配文件名
        rule = (filename, event_type)
        if rule in self.RULES:
            return self.RULES[rule]
            
        # 路径前缀匹配
        for (pattern, evt), level in self.RULES.items():
            if pattern.endswith("/") and str(path).startswith(pattern):
                return level
            if pattern in path and evt == event_type:
                return level
                
        return RiskLevel.SAFE
        
    def _should_notify(self, level):
        """判断是否应该通知（根据配置动态调整）"""
        level_map = {
            "CRITICAL": 0,
            "HIGH": 1,
            "MEDIUM": 2,
            "LOW": 3,
            "OFF": 99,
        }
        
        notify_threshold = level_map.get(self.notification_level, 2)
        return level <= notify_threshold
        
    def evaluate(self, event_info):
        """
        评估事件风险
        返回 Action 对象或 None
        """
        path = event_info["path"]
        event_type = event_info["event"]
        category = event_info.get("category", "")
        
        # 获取风险等级
        level = self._get_rule_level(path, event_type)
        
        # 特殊处理：公共仓 push
        if "push" in path.lower() or "public" in path.lower():
            if event_type in ("MODIFY", "CREATE"):
                level = max(level, RiskLevel.MEDIUM)
                
        # 构建详情
        details = {
            "path": path,
            "event": event_type,
            "category": category,
            "risk_level": level.name,
        }
        
        # 构建消息
        emoji = {
            RiskLevel.SAFE: "✅",
            RiskLevel.LOW: "📝",
            RiskLevel.MEDIUM: "⚠️",
            RiskLevel.HIGH: "🚨",
            RiskLevel.CRITICAL: "🔴",
        }
        
        msg_map = {
            "DELETE": "尝试删除",
            "MODIFY": "尝试修改",
            "CREATE": "尝试创建",
            "MOVED_FROM": "尝试移动（移出）",
            "MOVED_TO": "尝试移动（移入）",
        }
        
        emoji_char = emoji.get(level, "❓")
        msg = msg_map.get(event_type, event_type)
        filename = Path(path).name
        
        full_msg = f"{emoji_char} [{level.name}] {msg} 核心文件：{filename}"
        
        # 写审计日志
        self._write_audit(event_info, level)
        
        # auto_allow 模式下：所有操作自动放行，只记录日志
        if self.auto_allow:
            return Action(level, "ALLOW", full_msg, details, can_proceed=True)

        # 正常模式：按风险等级决定动作
        if level >= RiskLevel.HIGH:
            # CRITICAL/HIGH 级别且是删除操作时，先备份
            if event_type == "DELETE":
                backup_path = self.backup_core_file(path)
                if backup_path:
                    details["backup_path"] = str(backup_path)
                    full_msg += f"\n📦 已自动备份到: {backup_path}"
            return Action(level, "BLOCK", full_msg, details, can_proceed=False)
        elif level == RiskLevel.MEDIUM:
            return Action(level, "PAUSE", full_msg, details, can_proceed=False)
        elif level == RiskLevel.LOW:
            return Action(level, "LOG", full_msg, details, can_proceed=True)
        else:
            return None
            
    def _write_audit(self, event_info, level):
        """写审计日志"""
        log_entry = {
            "time": time.strftime("%Y-%m-%d %H:%M:%S"),
            "level": level.name,
            "path": event_info["path"],
            "event": event_info["event"],
        }
        
        try:
            os.makedirs(os.path.dirname(self.audit_log_path), exist_ok=True)
            with open(self.audit_log_path, "a") as f:
                f.write(json.dumps(log_entry, ensure_ascii=False) + "\n")
        except Exception as e:
            print(f"[Detector] 审计日志写入失败: {e}")
            
    def set_notification_level(self, level):
        """动态调整通知等级"""
        valid = ["CRITICAL", "HIGH", "MEDIUM", "LOW", "OFF"]
        if level not in valid:
            raise ValueError(f"无效等级: {level}，可选: {valid}")
            
        self.notification_level = level
        self.config["notification_level"] = level
        
        try:
            os.makedirs(os.path.dirname(self.config_path), exist_ok=True)
            with open(self.config_path, "w") as f:
                json.dump(self.config, f, indent=2)
        except Exception as e:
            print(f"[Detector] 配置保存失败: {e}")


if __name__ == "__main__":
    detector = RiskDetector()
    
    # 测试用例
    test_events = [
        {"path": "/root/.openclaw/workspace/AGENTS.md", "event": "DELETE", "category": "CORE_FILE"},
        {"path": "/root/.openclaw/workspace/memory/", "event": "DELETE", "category": "CORE_DIR"},
        {"path": "/root/.openclaw/workspace/README.md", "event": "MODIFY", "category": ""},
    ]
    
    for event in test_events:
        action = detector.evaluate(event)
        if action:
            print(f"事件: {event['path']} -> {action.action_type} ({action.level.name})")
            print(f"  消息: {action.message}")
            print()
