#!/usr/bin/env python3
"""
SessionRefiner - 飞书对话后实时提炼脚本
灵感来源：hermes-agent 实时学习，但用虾哥自己的记忆架构

原理：
  每次飞书对话结束后（主会话收到消息）
  → 提炼本轮对话中的关键模式
  → 写入 memory/sessions/YYYY-MM-DD-SESSION.json
  → 供18:30 cron 蒸馏系统提纯为 Belief

不照搬 hermes-agent：
  - 不做 .md 技能文件（沿用我们自己的 Belief 结构）
  - 不做多渠道（只接飞书）
  - 用已有的 memory 框架，不新增文件格式
"""

import json
import sys
import os
from datetime import datetime
from pathlib import Path

WORKSPACE = Path("/root/.openclaw/workspace")
SESSION_DIR = WORKSPACE / "memory" / "sessions"
SESSION_DIR.mkdir(parents=True, exist_ok=True)


def extract_patterns_from_session(conversation: str) -> dict:
    """
    从对话文本中提炼关键模式
    返回：{patterns: [], facts: [], skills: [], warnings: []}
    """
    patterns = []
    facts = []
    skills = []
    warnings = []

    lines = conversation.split("\n")
    for line in lines:
        line = line.strip()
        if not line:
            continue

        # 识别关键动作（坤哥做了什么）
        action_keywords = [
            ("git commit", "git操作", "git"),
            ("git push", "git推送", "git"),
            ("cron", "定时任务设置", "system"),
            ("飞书", "飞书API调用", "feishu"),
            ("webhook", "Webhook推送", "integration"),
            ("python3", "Python脚本执行", "code"),
            ("docker", "容器操作", "devops"),
            ("sqlite|mysql", "数据库操作", "data"),
            ("rclone", "云盘同步", "cloud"),
            ("openclaw", "OpenClaw配置", "system"),
            ("memory", "记忆系统操作", "memory"),
            ("clawkeeper", "安全审计", "security"),
            ("robots.txt", "合规检查", "compliance"),
        ]

        for keyword, label, category in action_keywords:
            if keyword.lower() in line.lower():
                patterns.append({"keyword": keyword, "label": label, "category": category})
                break

        # 识别新知识（坤哥教我的）
        learning_keywords = ["我记住了", "这个是", "你要记住", "请记录"]
        for kw in learning_keywords:
            if kw in line:
                facts.append(line[:100])
                break

        # 识别坤哥偏好
        preference_keywords = ["我喜欢", "坤哥喜欢", "不要", "请勿", "必须"]
        for kw in preference_keywords:
            if kw in line:
                facts.append(f"[偏好] {line[:100]}")
                break

        # 识别风险操作
        risk_keywords = ["api_key", "token", "secret", "password", "credential"]
        for kw in risk_keywords:
            if kw.lower() in line.lower() and ("sk-" in line or "ghp_" in line or "nvapi-" in line):
                warnings.append(f"[⚠️ 风险] 敏感词出现在对话中: {line[:50]}")
                break

    return {
        "patterns": patterns[:20],  # 最多20条
        "facts": facts[:10],
        "skills": skills[:10],
        "warnings": warnings,
    }


def distill_to_memory(session_refine: dict, session_id: str) -> str:
    """
    把提炼结果写入 memory/sessions/ 目录
    文件名格式：YYYY-MM-DD-SESSIONID.json
    """
    filename = f"{datetime.now().strftime('%Y-%m-%d')}-{session_id[:12]}.json"
    filepath = SESSION_DIR / filename

    # 追加写入（同一分钟多轮对话不覆盖）
    existing = {}
    if filepath.exists():
        try:
            existing = json.loads(filepath.read_text())
        except Exception:
            pass

    # 合并 patterns（去重）
    new_patterns = session_refine.get("patterns", [])
    existing_patterns = existing.get("patterns", [])
    seen = {p["keyword"] for p in existing_patterns}
    merged_patterns = existing_patterns + [p for p in new_patterns if p["keyword"] not in seen]

    # 合并 facts
    new_facts = session_refine.get("facts", [])
    existing_facts = existing.get("facts", [])
    seen_facts = set(existing_facts)
    merged_facts = existing_facts + [f for f in new_facts if f not in seen_facts]

    output = {
        "session_id": session_id,
        "refined_at": datetime.now().isoformat(),
        "patterns": merged_patterns[:20],
        "facts": merged_facts[:10],
        "warnings": session_refine.get("warnings", []),
        "status": "refined",  # refined → 等待18:30蒸馏为 Belief
    }

    filepath.write_text(json.dumps(output, ensure_ascii=False, indent=2))
    return str(filepath)


def main():
    if len(sys.argv) < 2:
        print("Usage: session_refiner.py <session_id> [conversation]")
        sys.exit(1)

    session_id = sys.argv[1]

    if len(sys.argv) >= 3:
        conversation = sys.argv[2]
    else:
        # 无对话内容，只更新 timestamp
        conversation = ""

    if not conversation.strip():
        # 无内容，快速写一个空壳标记
        filename = f"{datetime.now().strftime('%Y-%m-%d')}-{session_id[:12]}.json"
        filepath = SESSION_DIR / filename
        data = {
            "session_id": session_id,
            "refined_at": datetime.now().isoformat(),
            "patterns": [],
            "facts": [],
            "warnings": [],
            "status": "idle",
        }
        filepath.write_text(json.dumps(data, ensure_ascii=False, indent=2))
        print(f"✅ Session refined (idle): {filepath}")
        return

    patterns = extract_patterns_from_session(conversation)
    filepath = distill_to_memory(patterns, session_id)

    pattern_count = len(patterns.get("patterns", []))
    fact_count = len(patterns.get("facts", []))
    warn_count = len(patterns.get("warnings", []))

    print(f"✅ Session refined:")
    print(f"  📁 {filepath}")
    print(f"  🔑 patterns: {pattern_count}")
    print(f"  📝 facts: {fact_count}")
    if warn_count > 0:
        print(f"  ⚠️  warnings: {warn_count}")
        for w in patterns["warnings"]:
            print(f"     {w}")


if __name__ == "__main__":
    main()
