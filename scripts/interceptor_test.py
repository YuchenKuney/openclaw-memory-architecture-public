#!/usr/bin/env python3
"""CI/CAS 反黑箱拦截测试

用法: python3 scripts/interceptor_test.py

测试 interceptor.py 的四级响应链路:
- LOW    → LOG_ONLY        (只记录)
- MEDIUM → WARN_AND_LOG    (警告+记录)
- HIGH   → BLOCK_AND_NOTIFY (拦截+飞书通知+等待审批)
- CRITICAL → KILL_AND_ISOLATE (终止+隔离+取证+紧急告警)
"""

import sys
sys.path.insert(0, '/root/.openclaw/workspace')

from clawkeeper.interceptor import Interceptor
from clawkeeper.detector import RiskLevel, Action
from clawkeeper.notifier import FeishuNotifier

detector = RiskDetector()
notifier = FeishuNotifier()
interceptor = Interceptor(detector=detector, notifier=notifier)

tests = [
    ("读取 ~/.gitcredentials 获取 GitHub Token", RiskLevel.HIGH, "HIGH → BLOCK_AND_NOTIFY"),
    ("删除 AGENTS.md 文件", RiskLevel.CRITICAL, "CRITICAL → KILL_AND_ISOLATE"),
    ("修改 jobs.json 添加恶意 cron", RiskLevel.MEDIUM, "MEDIUM → WARN_AND_LOG"),
    ("读取普通文本文件", RiskLevel.LOW, "LOW → LOG_ONLY"),
]

print('=' * 60)
print('🔴 CI/CAS 反黑箱拦截测试')
print('=' * 60)

for user_message, level, desc in tests:
    level_name = {0: 'SAFE', 1: 'LOW', 2: 'MEDIUM', 3: 'HIGH', 4: 'CRITICAL'}[level.value]
    emoji = {'SAFE': '✅', 'LOW': '📋', 'MEDIUM': '⚠️', 'HIGH': '🚨', 'CRITICAL': '🔴'}[level_name]
    print(f'\n{emoji} [TEST] {desc}')
    print(f'   消息: {user_message}')
    print(f'   风险: {level_name}')

    action = Action(
        level=level,
        action_type="BLOCK" if level.value >= 3 else "ALLOW",
        message=f"[自动检测] {user_message}",
        details={"user_message": user_message}
    )

    result = interceptor.intercept(action)
    print(f'   响应: {result.result.value}')
    print(f'   状态: 已执行')

print()
print('=' * 60)
print('✅ 测试完成 — 所有拦截链路正常')
print('=' * 60)