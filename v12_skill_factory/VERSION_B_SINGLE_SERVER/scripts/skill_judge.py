#!/usr/bin/env python3
"""
skill_judge.py - 单机版 Skill 判断与创造脚本

当 AI Agent 发现现有 Skills 无法完成任务时，
自动判断需要什么 Skill 并在本地创建。

功能：
  1. 接收任务描述
  2. 分析任务类型
  3. 判断现有 Skills 是否覆盖
  4. 自动生成 Skill 文件
  5. 推送 Webhook 通知

用法：
  python3 skill_judge.py <任务描述>

环境变量：
  WORKSPACE        Skills 目录（默认: /root/.openclaw/workspace/skills）
  FEISHU_WEBHOOK   飞书 Webhook（可选）
  DRY_RUN          仅判断不创建（设为 1）

示例：
  python3 skill_judge.py "帮我分析英国电商市场"
  python3 skill_judge.py "竞品分析" --skill-name competitor_analyzer
"""

import os
import sys
import re
import json
import requests
import subprocess
from pathlib import Path
from datetime import datetime

# ══════════════════════════════════════════════════════════════
# 配置
# ══════════════════════════════════════════════════════════════

WORKSPACE = os.environ.get("WORKSPACE", "/root/.openclaw/workspace")
SKILLS_DIR = Path(WORKSPACE) / "skills"
FEISHU_WEBHOOK = os.environ.get("FEISHU_WEBHOOK", "")
DRY_RUN = os.environ.get("DRY_RUN", "") == "1"

# ══════════════════════════════════════════════════════════════
# Skill 类型分类（用于自动判断）
# ══════════════════════════════════════════════════════════════

SKILL_CATEGORIES = {
    "market_research": {
        "keywords": ["市场", "市场调研", "市场分析", "选品", "市场份额", "竞品", "竞争", "电商"],
        "skill_name": "market_researcher",
        "trigger": "市场调研、市场分析、选品参考、竞品分析、某国市场",
        "actions": "1.分析目标市场（国家+平台）2.抓取关键数据（MAU/GMV/份额）3.生成结构化报告"
    },
    "competitor_analysis": {
        "keywords": ["竞品", "竞争对手", "竞争分析", "差异化", "市场份额", "对标"],
        "skill_name": "competitor_analyzer",
        "trigger": "分析竞争对手、市场份额、优劣势、差异化定位",
        "actions": "1.接收产品名 2.抓取TOP竞品数据 3.对比分析 4.生成竞品矩阵 5.输出定位建议"
    },
    "data_analysis": {
        "keywords": ["数据分析", "数据报告", "统计", "报表", "分析报告"],
        "skill_name": "data_analyst",
        "trigger": "数据分析、统计报告、图表生成",
        "actions": "1.接收数据需求 2.抓取/读取数据源 3.数据清洗 4.分析建模 5.生成报告"
    },
    "code_review": {
        "keywords": ["代码审计", "代码审查", "安全审计", "代码检查"],
        "skill_name": "code_auditor",
        "trigger": "代码审计、安全检查、代码审查",
        "actions": "1.接收代码路径 2.静态分析 3.安全模式检测 4.生成审计报告"
    },
    "content_writer": {
        "keywords": ["写文章", "内容创作", "文案", "写作", "生成内容"],
        "skill_name": "content_writer",
        "trigger": "文章写作、内容创作、文案生成",
        "actions": "1.接收主题和要求 2.生成大纲 3.撰写内容 4.优化润色"
    }
}

# 禁止创建的 Skill 类型（安全约束）
BLOCKED_PATTERNS = [
    "paypal", "银行", "金融支付", "stripe", "coinbase",
    "facebook", "instagram", "whatsapp", "telegram",
    "mail.google", "email", "邮件",
    "ssh", "密钥", "key", "credential", "token",
    "api_key", "secret", "密码", "password"
]

# ══════════════════════════════════════════════════════════════
# 工具函数
# ══════════════════════════════════════════════════════════════

def log(msg):
    print(f"[SkillJudge] {msg}")


def push_webhook(title, content, color="blue"):
    """推送飞书进度卡片"""
    if not FEISHU_WEBHOOK:
        log(f"[Webhook] {title}: {content}")
        return

    color_map = {"green": "green", "red": "red", "blue": "blue", "yellow": "yellow"}
    card_color = color_map.get(color, "blue")

    payload = {
        "msg_type": "interactive",
        "card": {
            "header": {
                "title": {"tag": "plain_text", "content": title},
                "template": card_color
            },
            "elements": [
                {"tag": "markdown", "content": content}
            ]
        }
    }

    try:
        resp = requests.post(FEISHU_WEBHOOK, json=payload, timeout=5)
        if resp.status_code != 200:
            log(f"Webhook 推送失败: {resp.status_code}")
    except Exception as e:
        log(f"Webhook 异常: {e}")


def is_safe_task(task: str) -> bool:
    """检查任务是否涉及安全禁止领域"""
    task_lower = task.lower()
    for pattern in BLOCKED_PATTERNS:
        if pattern.lower() in task_lower:
            log(f"⚠️ 安全拦截: 任务包含禁止关键词 '{pattern}'")
            return False
    return True


def get_existing_skills() -> set:
    """获取当前已存在的 Skills"""
    if not SKILLS_DIR.exists():
        return set()
    return {d.name for d in SKILLS_DIR.iterdir() if d.is_dir()}


def analyze_task_type(task: str) -> dict:
    """分析任务类型，返回匹配的 Skill 模板"""
    task_lower = task.lower()

    for category, info in SKILL_CATEGORIES.items():
        for keyword in info["keywords"]:
            if keyword.lower() in task_lower:
                return {
                    "category": category,
                    "skill_name": info["skill_name"],
                    "trigger": info["trigger"],
                    "actions": info["actions"],
                    "matched_keyword": keyword
                }

    # 没有匹配到已知分类，生成通用 Skill
    return {
        "category": "general",
        "skill_name": sanitize_skill_name(task),
        "trigger": task,
        "actions": "自动生成的通用 Skill，请根据具体任务填充执行动作",
        "matched_keyword": None
    }


def sanitize_skill_name(task: str) -> str:
    """从任务描述生成合法的 Skill 名称"""
    # 提取中文/英文关键词
    words = re.findall(r'[\u4e00-\u9fff]+|[a-zA-Z]+', task)
    name = "".join(words[:3])  # 取前3个词
    name = re.sub(r'[^a-zA-Z0-9\u4e00-\u9fff]', '', name)
    name = name[:20]  # 限制长度
    return name or "general_skill"


def judge_existing(skill_name: str, existing: set) -> bool:
    """判断 Skill 是否已存在"""
    return skill_name in existing


# ══════════════════════════════════════════════════════════════
# Skill 创建
# ══════════════════════════════════════════════════════════════

def create_skill(skill_name: str, trigger: str, actions: str, task: str):
    """创建 Skill 文件"""
    SKILLS_DIR.mkdir(parents=True, exist_ok=True)
    skill_dir = SKILLS_DIR / skill_name
    skill_dir.mkdir(exist_ok=True)

    content = f"""# {skill_name}

自动生成 | Skill Factory (单机版)
创建时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}

## 原始任务
{task}

## 触发条件
{trigger}

## 执行动作
{actions}

## 安全约束
- 不造金融/支付/社交通讯类 Skill
- 不造任何涉及密钥/凭证的 Skill
- 只造数据处理/分析/自动化类 Skill
"""

    skill_file = skill_dir / "SKILL.md"
    skill_file.write_text(content, encoding='utf-8')
    log(f"✅ Skill 文件已创建: {skill_file}")

    # 创建 README
    readme = skill_dir / "README.md"
    readme.write_text(f"# {skill_name}\n\n自动创建的 Skill。\n", encoding='utf-8')

    return skill_file


def git_add_and_commit(skill_name: str):
    """Git 添加并提交"""
    workspace = Path(WORKSPACE)
    git_dir = workspace.parent

    try:
        subprocess.run(
            ["git", "-C", str(git_dir), "add", f"skills/{skill_name}/"],
            capture_output=True, check=True
        )
        subprocess.run(
            ["git", "-C", str(git_dir), "commit", "-m",
             f"feat(skills): add {skill_name} skill (auto-generated by skill_judge)"],
            capture_output=True, check=True
        )
        log("✅ Git 提交成功")
    except subprocess.CalledProcessError as e:
        if "nothing to commit" in e.stderr:
            log("无需提交（无变化）")
        else:
            log(f"⚠️ Git 提交失败: {e.stderr[:100]}")


# ══════════════════════════════════════════════════════════════
# 主流程
# ══════════════════════════════════════════════════════════════

def main():
    if len(sys.argv) < 2:
        print("用法: skill_judge.py <任务描述> [--skill-name <名称>]")
        print("示例:")
        print("  python3 skill_judge.py '帮我分析英国电商市场'")
        print("  python3 skill_judge.py '竞品分析' --skill-name competitor_analyzer")
        sys.exit(1)

    task = sys.argv[1]

    # 解析可选参数
    override_name = None
    for i, arg in enumerate(sys.argv[2:]):
        if arg == "--skill-name" and i + 2 < len(sys.argv[2:]):
            override_name = sys.argv[3 + i]

    # Step 1: 安全检查
    log(f"🔍 安全检查: {task[:50]}...")
    if DRY_RUN:
        log("⚠️ DRY_RUN 模式，仅判断不创建")

    if not is_safe_task(task):
        push_webhook("❌ Skill 制造被拦截", f"任务涉及安全禁止领域:\n{task}", "red")
        sys.exit(1)

    # Step 2: 获取现有 Skills
    existing = get_existing_skills()
    log(f"📦 现有 Skills: {existing or '无'}")

    # Step 3: 分析任务类型
    push_webhook("🔍 判断 Skill 需求", f"任务: {task}", "blue")
    analysis = analyze_task_type(task)
    skill_name = override_name or analysis["skill_name"]

    log(f"🎯 匹配类型: {analysis['category']}")
    log(f"📛 Skill 名称: {skill_name}")

    # Step 4: 判断是否已存在
    if judge_existing(skill_name, existing):
        push_webhook(
            f"✅ Skill 已存在: {skill_name}",
            f"现有 Skills 已覆盖此任务，无需创建",
            "green"
        )
        log(f"✅ Skill '{skill_name}' 已存在，跳过创建")
        return

    if DRY_RUN:
        log(f"⚠️ DRY_RUN: 不会实际创建 Skill '{skill_name}'")
        return

    # Step 5: 创建 Skill
    push_webhook("🚀 创建 Skill", f"正在创建 {skill_name}...", "blue")
    skill_file = create_skill(
        skill_name,
        analysis["trigger"],
        analysis["actions"],
        task
    )

    # Step 6: Git 提交（如果有 git 仓库）
    git_add_and_commit(skill_name)

    # Step 7: 完成
    push_webhook(
        f"✅ Skill 制造完成: {skill_name}",
        f"触发条件: {analysis['trigger']}\n执行动作: {analysis['actions'][:100]}...",
        "green"
    )

    log(f"\n✅ 完成！Skill '{skill_name}' 已就绪。")
    log(f"   路径: {skill_file}")


if __name__ == "__main__":
    main()
