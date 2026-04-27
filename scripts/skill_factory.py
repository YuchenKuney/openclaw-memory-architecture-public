#!/usr/bin/env python3
"""skill_factory.py - 自动化skill制造（反黑箱版）"""
import subprocess, sys, os, tempfile

WEBHOOK_SCRIPT = "/root/.openclaw/workspace/scripts/feishu_progress.py"
SSH_CMD = ["ssh", "-o", "StrictHostKeyChecking=no", "-i", "/root/.ssh/id_ed25519"]

def progress(title: str, content: str, color: str = "blue", done: bool = False):
    """通过飞书推送进度（不卡主会话）"""
    color_map = {"running": "blue", "done": "green", "error": "red", "start": "blue"}
    c = color_map.get(color, "blue")
    done_flag = "true" if done else "false"
    os.system(f"python3 {WEBHOOK_SCRIPT} '{title}' '{content}' {c} {done_flag} > /dev/null 2>&1")

def run_ssh(cmd: list, fatal=True):
    """执行SSH命令，返回stdout或None"""
    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode:
        msg = result.stderr[:200]
        print(f"❌ {msg}")
        if fatal:
            progress("Skill Factory 异常", f"SSH失败: {msg[:80]}", "error")
            sys.exit(1)
        return None
    return result.stdout

def main():
    if len(sys.argv) < 4:
        print("用法: skill_factory.py <name> <trigger> <actions>")
        sys.exit(1)

    name, trigger, actions = sys.argv[1], sys.argv[2], sys.argv[3]

    progress("🚀 Skill Factory 启动", f"开始制造 skill: **{name}**", "blue")

    # Step 1: SSH连接新加坡
    progress("Step 1/5: SSH连接", "连接 178.128.52.85...", "blue")
    result = run_ssh(SSH_CMD + ["root@178.128.52.85", "echo ok"])
    if result is None:
        progress("Step 1/5: SSH连接", "❌ 连接失败", "red")
        sys.exit(1)
    progress("Step 1/5: SSH连接", "✅ 连接成功", "done", done=True)

    # Step 2: 创建目录
    progress("Step 2/5: 创建目录", f"mkdir skills/{name}", "blue")
    run_ssh(SSH_CMD + ["root@178.128.52.85", f"mkdir -p /root/.openclaw/workspace/skills/{name} && chmod 755 /root/.openclaw/workspace/skills/{name}"])
    progress("Step 2/5: 创建目录", "✅ 目录创建完成", "done", done=True)

    # Step 3: 写SKILL.md
    progress("Step 3/5: 生成SKILL.md", f"内容: {trigger[:30]}...", "blue")
    content = f"""# {name}

自动生成 | Singapore Skill Factory

## 触发条件
{trigger}

## 执行动作
{actions}

## 安全约束
- 不造金融/支付/社交通讯类skill
- 只造数据处理/分析/自动化类skill
"""
    tmp = tempfile.NamedTemporaryFile(mode='w', suffix='.md', delete=False, prefix='skill_')
    tmp.write(content)
    tmp.close()

    # SCP上传
    scp_cmd = ["scp", "-o", "StrictHostKeyChecking=no", "-i", "/root/.ssh/id_ed25519",
               tmp.name, f"root@178.128.52.85:/root/.openclaw/workspace/skills/{name}/SKILL.md"]
    result = subprocess.run(scp_cmd, capture_output=True, text=True)
    if result.returncode:
        print(f"❌ SCP failed: {result.stderr[:200]}")
        progress("Step 3/5: 生成SKILL.md", "❌ SCP上传失败", "red")
        sys.exit(1)
    os.unlink(tmp.name)
    progress("Step 3/5: 生成SKILL.md", "✅ SKILL.md 已写入新加坡", "done", done=True)

    # Step 4: Git add + commit
    progress("Step 4/5: Git提交", f"git add + commit skills/{name}", "blue")
    git_cmds = [
        "cd /root/.openclaw/workspace",
        "git config user.email singapore-skill-factory@openclaw",
        "git config user.name Singapore-Skill-Factory",
        f"git add skills/{name}/",
        f"git commit -m 'feat(skills): add {name} skill'"
    ]
    run_ssh(SSH_CMD + ["root@178.128.52.85", " && ".join(git_cmds)])
    progress("Step 4/5: Git提交", "✅ Commit完成", "done", done=True)

    # Step 5: Git push
    progress("Step 5/5: 推送到GitHub", "正在push...", "blue")
    push_cmd = "cd /root/.openclaw/workspace && GIT_SSH_COMMAND='ssh -o StrictHostKeyChecking=no -i /root/.ssh/id_ed25519' git push main main"
    result = run_ssh(SSH_CMD + ["root@178.128.52.85", push_cmd])
    if result is None:
        progress("Step 5/5: 推送到GitHub", "❌ push失败", "red")
        sys.exit(1)
    progress("Step 5/5: 推送到GitHub", "✅ 推送成功", "done", done=True)

    # 完成卡片
    progress(
        "✅ Skill Factory 任务完成",
        f"**{name}** skill 制造并推送完毕\n"
        f"触发: {trigger[:50]}...\n"
        f"动作: {actions[:50]}...",
        "green", done=True
    )
    print(f"✅ {name} skill 制造完成并推送")

if __name__ == "__main__":
    main()