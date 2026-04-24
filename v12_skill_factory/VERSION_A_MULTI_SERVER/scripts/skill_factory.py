#!/usr/bin/env python3
"""
skill_factory.py - 多服务器版 Skill 制造脚本

通过 SSH 连接到新加坡服务器，自动创建 Skill 文件，
通过 Git + VPN 隧道同步回主服务器。

依赖：
  - Python 3.8+
  - SSH Key 认证（无密码）
  - WireGuard VPN 连接
  - Git

用法：
  python3 skill_factory.py <skill名称> <触发条件> <执行动作>

环境变量：
  SG_SERVER_IP     新加坡公网IP（默认从环境读取）
  SG_SSH_KEY       SSH私钥路径
  SYNC_REPO        Git同步仓库路径
  FEISHU_WEBHOOK   飞书Webhook（可选）
"""

import os
import sys
import subprocess
import tempfile
import json
import requests
from pathlib import Path

# ══════════════════════════════════════════════════════════════
# 配置（可通过环境变量覆盖）
# ══════════════════════════════════════════════════════════════

SG_SERVER_IP = os.environ.get("SG_SERVER_IP", "${SG_SERVER_IP}")  # 新加坡公网IP
SG_SSH_KEY = os.environ.get("SG_SSH_KEY", "/root/.ssh/id_ed25519")
SG_SSH_USER = os.environ.get("SG_SSH_USER", "root")
SG_SSH_PORT = os.environ.get("SG_SSH_PORT", "22")

SYNC_REPO = os.environ.get("SYNC_REPO", "/root/.openclaw/skill_sync.git")
SG_WORKSPACE = os.environ.get("SG_WORKSPACE", "/root/.openclaw/workspace")

FEISHU_WEBHOOK = os.environ.get("FEISHU_WEBHOOK", "")
FEISHU_ENABLED = bool(FEISHU_WEBHOOK)

# ══════════════════════════════════════════════════════════════
# 工具函数
# ══════════════════════════════════════════════════════════════

def run_cmd(cmd, check=True, capture=True):
    """执行shell命令"""
    if capture:
        r = subprocess.run(cmd, shell=True, capture_output=True, text=True)
    else:
        r = subprocess.run(cmd, shell=True)
    if check and r.returncode != 0:
        print(f"❌ 命令失败: {cmd}")
        if r.stderr:
            print(r.stderr[:200])
        sys.exit(1)
    return r.stdout.strip() if capture else ""


def push_webhook(title, content, color="blue"):
    """推送飞书进度卡片"""
    if not FEISHU_ENABLED:
        print(f"[Webhook] {title}: {content}")
        return

    payload = {
        "msg_type": "interactive",
        "card": {
            "header": {
                "title": {"tag": "plain_text", "content": title},
                "template": color
            },
            "elements": [
                {"tag": "markdown", "content": content}
            ]
        }
    }

    try:
        requests.post(FEISHU_WEBHOOK, json=payload, timeout=5)
    except Exception as e:
        print(f"[Webhook] 推送失败: {e}")


def ssh_cmd(cmd):
    """通过SSH执行远程命令"""
    ssh_base = [
        "ssh", "-o", "StrictHostKeyChecking=no",
        "-i", SG_SSH_KEY,
        "-p", SG_SSH_PORT,
        f"{SG_SSH_USER}@{SG_SERVER_IP}"
    ]
    full_cmd = " ".join(ssh_base) + f" '{cmd}'"
    return run_cmd(full_cmd)


def scp_file(local_path, remote_path):
    """通过SCP传输文件"""
    scp_cmd = [
        "scp", "-o", "StrictHostKeyChecking=no",
        "-i", SG_SSH_KEY,
        "-P", SG_SSH_PORT,
        local_path,
        f"{SG_SSH_USER}@{SG_SERVER_IP}:{remote_path}"
    ]
    run_cmd(" ".join(scp_cmd))


# ══════════════════════════════════════════════════════════════
# 核心逻辑
# ══════════════════════════════════════════════════════════════

def create_skill_on_sg(skill_name, trigger, actions):
    """在新加坡创建 Skill 文件"""
    push_webhook(
        f"🚀 制造 Skill: {skill_name}",
        f"触发条件: {trigger}\n执行动作: {actions}",
        "blue"
    )

    # 构造 SKILL.md 内容
    content = f"""# {skill_name}

自动生成 | Singapore Skill Factory
Created: {run_cmd('date')}

## 触发条件
{trigger}

## 执行动作
{actions}

## 安全约束
- 不造金融/支付/社交通讯类 Skill
- 只造数据处理/分析/自动化类 Skill
- 敏感信息通过环境变量注入
"""

    # 写到临时文件
    with tempfile.NamedTemporaryFile(
        mode='w', suffix='.md', delete=False, prefix=f'skill_'
    ) as f:
        f.write(content)
        tmp_path = f.name

    try:
        # SCP 传到新加坡
        remote_dir = f"{SG_WORKSPACE}/skills/{skill_name}"
        remote_file = f"{remote_dir}/SKILL.md"

        # 先创建目录
        ssh_cmd(f"mkdir -p {remote_dir} && chmod 755 {remote_dir}")

        # SCP 传文件
        scp_file(tmp_path, remote_file)
        print(f"✅ 已传输到新加坡: {remote_file}")

    finally:
        os.unlink(tmp_path)

    return content


def git_push_from_sg(skill_name):
    """在新加坡执行 git add + commit + push"""
    push_webhook(f"📤 同步 Skill: {skill_name}", "Git push 到主服务器...", "blue")

    git_script = f"""
cd {SG_WORKSPACE}
git config user.email 'singapore-skill-factory@openclaw'
git config user.name 'Singapore Skill Factory'
git add skills/{skill_name}/
git commit -m 'feat(skills): add {skill_name} skill (auto-generated)'
GIT_SSH_COMMAND='ssh -o StrictHostKeyChecking=no -i {SG_SSH_KEY}' git push main main
echo GIT_DONE
"""

    # 执行多行 SSH 脚本
    ssh_base = [
        "ssh", "-o", "StrictHostKeyChecking=no",
        "-i", SG_SSH_KEY,
        "-p", SG_SSH_PORT
    ]

    result = subprocess.run(
        ssh_base + [f"{SG_SSH_USER}@{SG_SERVER_IP}", git_script],
        capture_output=True, text=True
    )

    if "GIT_DONE" not in result.stdout:
        print(f"❌ Git push 失败: {result.stderr[:200]}")
        push_webhook(f"❌ 同步失败: {skill_name}", result.stderr[:200], "red")
        sys.exit(1)

    print(f"✅ Git push 成功")
    return True


def pull_to_main(skill_name):
    """在主服务器 Pull Skill 仓库"""
    push_webhook(f"📥 接收 Skill: {skill_name}", "从 Git 仓库拉取...", "blue")

    # 更新 git仓库
    run_cmd(f"cd {SYNC_REPO} && GIT_DIR=. git pull")

    # 克隆验证
    verify_dir = tempfile.mkdtemp(prefix=f"skill_verify_")
    run_cmd(f"git clone {SYNC_REPO} {verify_dir}")

    skill_file = Path(verify_dir) / "skills" / skill_name / "SKILL.md"
    if skill_file.exists():
        content = skill_file.read_text()
        print(f"✅ 验证成功，内容预览:\n{content[:200]}")
        push_webhook(f"✅ Skill 就绪: {skill_name}", f"已同步到主服务器\n预览: {content[:100]}...", "green")
    else:
        print(f"⚠️ 验证文件不存在")

    # 清理
    run_cmd(f"rm -rf {verify_dir}", check=False)


# ══════════════════════════════════════════════════════════════
# 主流程
# ══════════════════════════════════════════════════════════════

def main():
    if len(sys.argv) < 4:
        print("用法: skill_factory.py <skill名称> <触发条件> <执行动作>")
        print("示例:")
        print("  python3 skill_factory.py competitor_analyzer 分析竞品市场份额 '1接收 2抓取 3分析'")
        sys.exit(1)

    skill_name = sys.argv[1]
    trigger = sys.argv[2]
    actions = sys.argv[3]

    print(f"🚀 开始制造 Skill: {skill_name}")
    print(f"   触发: {trigger}")
    print(f"   动作: {actions}")

    # Step 1: 在新加坡创建 Skill 文件
    push_webhook(f"Step 1/3: 创建 Skill 文件", f"正在新加坡创建 {skill_name}...", "blue")
    create_skill_on_sg(skill_name, trigger, actions)

    # Step 2: Git 推送到主服务器
    push_webhook("Step 2/3: Git 同步", "正在通过 VPN 推送...", "blue")
    git_push_from_sg(skill_name)

    # Step 3: 主服务器接收并验证
    push_webhook("Step 3/3: 接收验证", "正在主服务器验证...", "blue")
    pull_to_main(skill_name)

    # 完成
    push_webhook(
        f"✅ Skill 制造完成: {skill_name}",
        f"Skill 已就绪，可立即使用",
        "green"
    )
    print(f"\n✅ 全流程完成！Skill '{skill_name}' 已就绪。")


if __name__ == "__main__":
    main()
