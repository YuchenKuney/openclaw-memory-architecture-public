#!/usr/bin/env python3
"""
Clawkeeper 配置加载器
从 config.yaml 读取配置，支持环境变量覆盖
"""

import os
import yaml
from pathlib import Path

# 默认配置路径
DEFAULT_CONFIG_PATH = os.path.join(os.path.dirname(__file__), "config.yaml")

_config = None


def load_config(config_path=None):
    """加载配置"""
    global _config
    
    if _config is not None and config_path is None:
        return _config
    
    path = config_path or DEFAULT_CONFIG_PATH
    
    if not os.path.exists(path):
        # 返回默认配置
        return {
            "user_id": None,
            "group_id": None,
            "feishu_app_id": None,
            "feishu_app_secret": None,
            "notification": {
                "level": "MEDIUM",
                "feishu_enabled": True,
            }
        }
    
    with open(path, "r", encoding="utf-8") as f:
        _config = yaml.safe_load(f)
    
    # 环境变量覆盖
    if os.environ.get("KUNGE_ID"):
        _config["user_id"] = os.environ["KUNGE_ID"]
    if os.environ.get("FEISHU_GROUP_ID"):
        _config["group_id"] = os.environ["FEISHU_GROUP_ID"]
    if os.environ.get("FEISHU_WEBHOOK"):
        _config["webhook_url"] = os.environ["FEISHU_WEBHOOK"]
    
    return _config


def get_user_id():
    """获取用户ID"""
    return load_config().get("user_id")


def get_group_id():
    """获取群ID"""
    return load_config().get("group_id")


def get_webhook_url():
    """获取Webhook URL"""
    cfg = load_config()
    return cfg.get("webhook_url") or os.environ.get(
        "FEISHU_WEBHOOK",
        "https://open.feishu.cn/open-apis/bot/v2/hook/375a8be1-9e3e-4758-a78b-e775fd4d32a1"
    )


def get_notification_level():
    """获取通知等级"""
    return load_config().get("notification", {}).get("level", "MEDIUM")


def get_feishu_creds():
    """获取飞书凭证"""
    cfg = load_config()
    return cfg.get("feishu_app_id"), cfg.get("feishu_app_secret")
