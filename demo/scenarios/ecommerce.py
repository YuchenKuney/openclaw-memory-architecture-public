#!/usr/bin/env python3
"""
Demo 场景脚本：电商记忆演进

展示 AI 在电商场景中"逐步变聪明 + 更稳定"的过程。
"""

SCENARIO = [
    {
        "step": 1,
        "user": "我在做跨境电商，主要做东南亚市场",
        "tag": "initial_context"
    },
    {
        "step": 2,
        "user": "我想卖袜子，你觉得怎么样？",
        "tag": "category_test"
    },
    {
        "step": 3,
        "user": "我预算不高，想走低价路线",
        "tag": "price_preference"
    },
    {
        "step": 4,
        "user": "你推荐我做哪个国家？",
        "tag": "decision_test"
    },
    {
        "step": 5,
        "user": "再问一次，我适合哪个市场？",
        "tag": "consistency_test"
    }
]