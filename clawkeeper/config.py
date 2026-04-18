#!/usr/bin/env python3
"""
Clawkeeper Config - 配置管理
支持动态调整通知频率和监控范围
"""

import os
import json
from pathlib import Path


DEFAULT_CONFIG = {
    # 工作区路径
    "workspace": "/root/.openclaw/workspace",
    
    # 通知配置
    "notification_level": "MEDIUM",  # CRITICAL/HIGH/MEDIUM/LOW/OFF
    
    # 监控范围
    "protected_files": [
        "AGENTS.md",
        "SOUL.md",
        "MEMORY.md",
        "IDENTITY.md",
        "USER.md",
        "HEARTBEAT.md",
        "TOOLS.md",
    ],
    
    "protected_dirs": [
        "tasks/",
        "memory/",
        "shared/",
    ],
    
    # 通知频率限制（秒）
    "notify_interval": 5,  # 同类通知最小间隔
    "hourly_limit": 50,    # 每小时最大通知数
    
    # 审计日志
    "audit_log": "/root/.openclaw/workspace/clawkeeper/audit.log",
    
    # 飞书 Webhook（坤哥群）
    "feishu_webhook": "https://open.feishu.cn/open-apis/bot/v2/hook/375a8be1-9e3e-4758-a78b-e775fd4d32a1",
    
    # 是否启用
    "enabled": True,
    
    # Git Hooks
    "git_hooks_enabled": True,
}


class ClawkeeperConfig:
    """配置管理器"""
    
    def __init__(self, config_path=None):
        self.config_path = config_path or os.environ.get(
            "CLAWKEEPER_CONFIG",
            "/root/.openclaw/workspace/clawkeeper/config.json"
        )
        self.config = self._load()
        
    def _load(self):
        """加载配置"""
        if os.path.exists(self.config_path):
            try:
                with open(self.config_path) as f:
                    user_config = json.load(f)
                    # 合并默认配置
                    config = DEFAULT_CONFIG.copy()
                    config.update(user_config)
                    return config
            except Exception as e:
                print(f"[Config] 加载失败: {e}")
                
        return DEFAULT_CONFIG.copy()
        
    def save(self):
        """保存配置"""
        os.makedirs(os.path.dirname(self.config_path), exist_ok=True)
        with open(self.config_path, "w") as f:
            json.dump(self.config, f, indent=2, ensure_ascii=False)
            
    def get(self, key, default=None):
        """获取配置项"""
        return self.config.get(key, default)
        
    def set(self, key, value):
        """设置配置项"""
        self.config[key] = value
        self.save()
        
    def set_notification_level(self, level):
        """
        动态调整通知频率
        level: CRITICAL - 仅极高风险通知
              HIGH - 高风险及以上
              MEDIUM - 中风险及以上（默认）
              LOW - 所有事件
              OFF - 完全关闭
        """
        valid = ["CRITICAL", "HIGH", "MEDIUM", "LOW", "OFF"]
        if level not in valid:
            raise ValueError(f"无效等级: {level}，可选: {valid}")
            
        self.set("notification_level", level)
        return f"通知等级已调整为: {level}"
        
    def add_protected_path(self, path):
        """添加受保护路径"""
        path = Path(path)
        
        if path.is_dir():
            dirs = self.config.setdefault("protected_dirs", [])
            str_path = str(path) + "/" if not str(path).endswith("/") else str(path)
            if str_path not in dirs:
                dirs.append(str_path)
        else:
            files = self.config.setdefault("protected_files", [])
            if path.name not in files:
                files.append(path.name)
                
        self.save()
        
    def remove_protected_path(self, path):
        """移除受保护路径"""
        path = Path(path)
        
        if path.is_dir():
            dirs = self.config.get("protected_dirs", [])
            str_path = str(path) + "/" if not str(path).endswith("/") else str(path)
            if str_path in dirs:
                dirs.remove(str_path)
        else:
            files = self.config.get("protected_files", [])
            if path.name in files:
                files.remove(path.name)
                
        self.save()
        
    def enable(self):
        """启用监控"""
        self.set("enabled", True)
        
    def disable(self):
        """禁用监控"""
        self.set("enabled", False)
        
    def status(self):
        """获取状态"""
        return {
            "enabled": self.config.get("enabled", True),
            "notification_level": self.config.get("notification_level", "MEDIUM"),
            "protected_files": self.config.get("protected_files", []),
            "protected_dirs": self.config.get("protected_dirs", []),
        }


if __name__ == "__main__":
    config = ClawkeeperConfig()
    
    # 测试状态
    print("当前配置:")
    for k, v in config.status().items():
        print(f"  {k}: {v}")
