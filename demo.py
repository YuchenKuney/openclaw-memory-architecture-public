#!/usr/bin/env python3
"""
Clawkeeper 演示启动脚本

用法：
  python3 demo.py                    # 交互式启动（推荐）
  python3 demo.py --webhook URL      # 直接指定 webhook
  python3 demo.py --group ID        # 直接指定群 ID
  python3 demo.py --check           # 只检查依赖和配置
  python3 demo.py --populate        # 只填充知识图谱

首次使用时会提示输入飞书 webhook 和群 ID。
配置后会保存到 ~/.clawkeeper_demo_config.json（不包含敏感信息，仅做记录）。

本脚本会启动以下服务：
  1. Clawkeeper watcher（文件监控 + 事件拦截）
  2. Knowledge Graph 填充（从 memory/ 抽取实体）
  3. 透明化 cron 任务（喂鱼提醒等）
"""

import os
import sys

# ============ 反馈提示（必须最先执行）============
print("=" * 60)
print("🐱 OpenClaw Demo 启动中...")
print("=" * 60)
print("💬 友情提示：")
print(" 这是作者倾注心血的项目，我在非常认真地做这件事。")
print(" 也希望你能认真对待它，哪怕只给我一条小小的建议。")
print(" 让我知道，我不是一个人在战斗。")
print(" Issue地址：https://github.com/YuchenKuney/openclaw-memory-architecture-public/issues")
print("=" * 60)

confirm = input("是否已提交反馈？(y/n)：")

if confirm.lower() != "y":
    print("\n😅 没关系，你也可以先去看看项目文档~")
    print("等你准备好提交反馈了，再回来运行吧！")
    sys.exit()

print("\n🎉 感谢你的反馈！OpenClaw Demo 即将启动...\n")

# ============ 正式逻辑 ============
import json
import argparse
from pathlib import Path
from datetime import datetime

CONFIG_FILE = Path.home() / ".clawkeeper_demo_config.json"
WORKSPACE = Path("/root/.openclaw/workspace")

# ============ 颜色输出 ============

RED = "\033[91m"
GREEN = "\033[92m"
YELLOW = "\033[93m"
BLUE = "\033[94m"
CYAN = "\033[96m"
BOLD = "\033[1m"
RESET = "\033[0m"


def cprint(text, color=None, bold=False, end="\n"):
    prefix = ""
    if bold:
        prefix += BOLD
    if color:
        prefix += color
    print(f"{prefix}{text}{RESET}", end=end)


def header(text):
    cprint(f"\n{'=' * 60}", CYAN)
    cprint(f"  {text}", CYAN, bold=True)
    cprint(f"{'=' * 60}", CYAN)


def step(num, text):
    cprint(f"  [{num}] {text}", BLUE)


def ok(text):
    cprint(f"  ✅ {text}", GREEN)


def warn(text):
    cprint(f"  ⚠️  {text}", YELLOW)


def error(text):
    cprint(f"  ❌ {text}", RED)


# ============ 配置加载 ============

def load_config():
    """加载已有配置"""
    if CONFIG_FILE.exists():
        try:
            with open(CONFIG_FILE, 'r') as f:
                return json.load(f)
        except Exception:
            pass
    return {}


def save_config(config):
    """保存配置（非敏感，仅记录）"""
    # 不保存真实 webhook 内容，仅记录是否已配置
    safe_config = {
        "webhook_configured": bool(config.get("webhook")),
        "group_configured": bool(config.get("group")),
        "last_used": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
    }
    with open(CONFIG_FILE, 'w') as f:
        json.dump(safe_config, f, indent=2)


# ============ 飞书配置 ============

def get_feishu_config():
    """
    获取飞书配置（优先环境变量 > 交互式输入）
    """
    # 1. 优先从环境变量读取
    webhook = os.environ.get("FEISHU_WEBHOOK")
    group_id = os.environ.get("FEISHU_GROUP_ID")

    if webhook and group_id:
        cprint("  使用环境变量: FEISHU_WEBHOOK / FEISHU_GROUP_ID", GREEN)
        return webhook, group_id

    # 2. 尝试从 clawkeeper 配置读取
    config_path = WORKSPACE / "clawkeeper" / "config.yaml"
    if config_path.exists():
        content = config_path.read_text()
        import re
        wh_match = re.search(r'webhook:\s*["\']?(https://[^\"\']+)["\']?', content)
        gr_match = re.search(r'group_id:\s*["\']?(oc_[^\"\']+)["\']?', content)
        if wh_match and gr_match:
            cprint("  从 clawkeeper/config.yaml 读取配置", GREEN)
            return wh_match.group(1), gr_match.group(1)

    # 3. 交互式输入
    print()
    cprint("  首次配置需要设置飞书机器人信息", YELLOW)
    print()

    # webhook
    print(f"  {'─' * 50}")
    cprint("  📡 飞书 Webhook URL", CYAN, bold=True)
    cprint("  请输入 webhook 地址，例如：", BLUE)
    cprint("  https://open.feishu.cn/open-apis/bot/v2/hook/xxxx", BLUE)
    while True:
        webhook = input(f"  输入 webhook（直接回车跳过）: ").strip()
        if not webhook:
            break
        if webhook.startswith("https://open.feishu.cn"):
            break
        error("webhook 应以 https://open.feishu.cn 开头，请重新输入")

    # group ID
    print()
    cprint("  👥 飞书群 ID", CYAN, bold=True)
    cprint("  请输入群 ID（以 oc_ 开头），例如：", BLUE)
    cprint("  oc_0533b03e077fedca255c4d2c6717deea", BLUE)
    while True:
        group_id = input(f"  输入群 ID（直接回车跳过）: ").strip()
        if not group_id:
            break
        if group_id.startswith("oc_"):
            break
        error("群 ID 应以 oc_ 开头，请重新输入")

    if webhook:
        os.environ["FEISHU_WEBHOOK"] = webhook
    if group_id:
        os.environ["FEISHU_GROUP_ID"] = group_id

    # 保存到 clawkeeper config.yaml
    if webhook or group_id:
        save_to_config(webhook, group_id)

    return webhook, group_id


def save_to_config(webhook, group_id):
    """保存到 clawkeeper/config.yaml"""
    config_path = WORKSPACE / "clawkeeper" / "config.yaml"
    content = ""
    if config_path.exists():
        content = config_path.read_text()

    import re
    if webhook:
        if "webhook:" in content:
            content = re.sub(r'webhook:\s*["\']?https://[^\"\']*["\']?', f'webhook: "{webhook}"', content)
        else:
            content = f'webhook: "{webhook}"\n' + content
    if group_id:
        if "group_id:" in content:
            content = re.sub(r'group_id:\s*["\']?oc_[^\"\']*["\']?', f'group_id: "{group_id}"', content)
        else:
            content = content + f'\ngroup_id: "{group_id}"\n'

    try:
        config_path.write_text(content)
        ok(f"配置已保存到 {config_path}")
    except Exception as e:
        warn(f"无法保存配置: {e}")


# ============ 依赖检查 ============

def check_dependencies():
    """检查依赖"""
    header("依赖检查")

    deps = [
        ("python3", "Python 3"),
        ("inotify", "python-inotify"),
    ]

    all_ok = True
    for cmd, name in deps:
        result = os.system(f"which {cmd.split()[0]} > /dev/null 2>&1")
        if result == 0:
            ok(f"{name} ✓")
        else:
            if "inotify" in cmd:
                result = os.system(f"python3 -c 'import inotify' > /dev/null 2>&1")
                if result == 0:
                    ok(f"{name} ✓")
                else:
                    error(f"{name} ✗ (运行: pip install inotify)")
                    all_ok = False
            else:
                error(f"{name} ✗")
                all_ok = False

    return all_ok


# ============ 知识图谱填充 ============

def populate_knowledge_graph():
    """填充知识图谱"""
    header("知识图谱填充")
    try:
        sys.path.insert(0, str(WORKSPACE))
        from knowledge_graph import KnowledgeGraph
        kg = KnowledgeGraph()
        n = kg.populate_from_memory()
        ok(f"从 memory/ 填充完成，新增 {n} 个实体")
        cprint(f"  当前图谱共 {len(kg.entities)} 个实体", BLUE)
    except Exception as e:
        error(f"知识图谱填充失败: {e}")
        import traceback
        traceback.print_exc()


# ============ Clawkeeper 启动 ============

def check_clawkeeper():
    """检查 clawkeeper 状态"""
    result = os.popen("ps aux | grep -E '[c]lawkeeper|[w]atcher' | grep -v grep").read()
    if result:
        cprint("  Clawkeeper 进程运行中:", YELLOW)
        for line in result.strip().split('\n'):
            cprint(f"    {line}", BLUE)
        return True
    return False


def start_clawkeeper():
    """启动 clawkeeper"""
    header("启动 Clawkeeper")

    if check_clawkeeper():
        warn("Clawkeeper 已在运行")
        return

    start_script = WORKSPACE / "clawkeeper" / "start.sh"
    if start_script.exists():
        step(1, "执行 start.sh")
        result = os.system(f"bash {start_script} > /dev/null 2>&1")
        if result == 0:
            ok("Clawkeeper 已启动")
        else:
            error("start.sh 启动失败")
    else:
        # 直接用 python 启动
        step(1, "直接启动 watcher")
        result = os.system(f"cd {WORKSPACE} && python3 clawkeeper/watcher.py > /dev/null 2>&1 &")
        if result == 0:
            ok("watcher.py 已后台启动")
        else:
            error("启动失败")


# ============ 透明化 cron 任务检查 ============

def check_cron_transparency():
    """检查透明化 cron 任务"""
    header("透明化 Cron 任务")
    jobs_file = Path("/root/.openclaw/cron/jobs.json")
    if not jobs_file.exists():
        warn("未找到 jobs.json")
        return

    try:
        jobs = json.loads(jobs_file.read_text())
        transparent = [j for j in jobs if "透明" in j.get("name", "")]
        normal = [j for j in jobs if "透明" not in j.get("name", "")]

        cprint(f"  共 {len(jobs)} 个 cron 任务", BLUE)
        if transparent:
            cprint(f"  透明化任务 ({len(transparent)}):", GREEN)
            for j in transparent:
                cprint(f"    • {j['name']}", BLUE)
                cprint(f"      调度: {j.get('schedule', {}).get('expr', '?')} ({j.get('tz', 'UTC')})", BLUE)
        if normal:
            cprint(f"  普通任务 ({len(normal)}):", YELLOW)
            for j in normal:
                cprint(f"    • {j['name']}", BLUE)
    except Exception as e:
        error(f"读取 jobs.json 失败: {e}")


# ============ 信息展示 ============

def show_project_info():
    """展示项目信息"""
    header("Clawkeeper 项目概览")

    # 文件统计
    py_files = list(WORKSPACE.glob("**/*.py"))
    py_files = [f for f in py_files if "__pycache__" not in str(f)]
    md_files = list(WORKSPACE.glob("*.md"))
    clwk_files = list((WORKSPACE / "clawkeeper").glob("*.py"))

    cprint(f"  工作区: {WORKSPACE}", BLUE)
    cprint(f"  Python 文件: {len(py_files)} 个", BLUE)
    cprint(f"  文档文件: {len(md_files)} 个", BLUE)
    cprint(f"  Clawkeeper 模块: {len(clwk_files)} 个", BLUE)
    print()

    # 模块说明
    modules = [
        ("watcher.py", "文件监控 + inotify 事件拦截"),
        ("detector.py", "PR① 正则 + LLM 语义双层风险检测"),
        ("interceptor.py", "PR② 四级分层响应（LOG→WARN→BLOCK→KILL）"),
        ("auditor.py", "PR③ 主动扫描（CVE/完整性/Skill模式）"),
        ("notifier.py", "飞书卡片通知"),
        ("config.yaml", "配置文件（webhook/群ID/规则）"),
    ]

    cprint("  核心模块:", CYAN, bold=True)
    for name, desc in modules:
        cprint(f"    • {name}", GREEN)
        cprint(f"      {desc}", BLUE)

    # PR 说明
    print()
    cprint("  PR 进度:", CYAN, bold=True)
    prs = [
        ("PR① LLM 语义判断", "✅ 已完成", GREEN),
        ("PR② 分层拦截器", "✅ 已完成", GREEN),
        ("PR③ 主动扫描+完整性", "✅ 已完成", GREEN),
        ("PR④ 知识图谱联动", "✅ 已完成", GREEN),
        ("PR⑤ 测试用例", "✅ 已完成", GREEN),
    ]
    for name, status, color in prs:
        cprint(f"    • {name}: {status}", color)

    # 安全规则状态
    print()
    cprint("  安全规则:", CYAN, bold=True)
    rules = [
        ("AGENTS.md/SOUL.md/MEMORY.md 删除", "CRITICAL 🔴", RED),
        ("~/.gitcredentials 读取", "HIGH 🚨", RED),
        ("cron-events/ 目录删除", "MEDIUM ⚠️", YELLOW),
        ("authorized_keys 写入", "HIGH 🚨", RED),
        ("jobs.json 修改", "HIGH 🚨", RED),
    ]
    for name, level, color in rules:
        cprint(f"    • {name}", BLUE)
        cprint(f"      → {level}", color)


# ============ 主函数 ============

def main():
    parser = argparse.ArgumentParser(
        description="Clawkeeper 演示启动脚本",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
示例：
  python3 demo.py                    交互式启动
  python3 demo.py --check           只检查依赖
  python3 demo.py --populate       只填充知识图谱
  python3 demo.py --webhook URL     指定 webhook
  python3 demo.py --group ID       指定群 ID
        """
    )
    parser.add_argument("--check", action="store_true", help="只检查依赖和配置")
    parser.add_argument("--populate", action="store_true", help="只填充知识图谱")
    parser.add_argument("--webhook", metavar="URL", help="飞书 webhook URL")
    parser.add_argument("--group", metavar="ID", help="飞书群 ID")
    parser.add_argument("--info", action="store_true", help="显示项目信息")
    args = parser.parse_args()

    # 解析参数设置环境变量
    if args.webhook:
        os.environ["FEISHU_WEBHOOK"] = args.webhook
    if args.group:
        os.environ["FEISHU_GROUP_ID"] = args.group

    print()
    cprint("  ╔══════════════════════════════════════════╗", CYAN, bold=True)
    cprint("  ║   Clawkeeper  反黑箱安全监控系统  v2.0   ║", CYAN, bold=True)
    cprint("  ╚══════════════════════════════════════════╝", CYAN, bold=True)
    print()
    cprint("  全链路透明化 · 四级分层响应 · 三层记忆联动", BLUE)
    print()

    # --info
    if args.info:
        show_project_info()
        return

    # --check
    if args.check:
        check_dependencies()
        get_feishu_config()
        check_cron_transparency()
        return

    # --populate
    if args.populate:
        populate_knowledge_graph()
        return

    # 完整启动流程
    step(1, "依赖检查")
    deps_ok = check_dependencies()

    step(2, "飞书配置")
    webhook, group_id = get_feishu_config()
    if webhook:
        ok(f"Webhook 已配置: {webhook[:45]}...")
    else:
        warn("Webhook 未配置，跳过飞书通知")
    if group_id:
        ok(f"群 ID 已配置: {group_id}")
    else:
        warn("群 ID 未配置")

    step(3, "透明化 Cron 任务")
    check_cron_transparency()

    step(4, "知识图谱填充")
    populate_knowledge_graph()

    step(5, "Clawkeeper 启动")
    start_clawkeeper()

    # 汇总
    print()
    header("启动完成")
    cprint("  Clawkeeper 已就绪，所有事件将透明化通知到飞书群", GREEN)
    cprint("  使用 --info 查看项目详情，使用 --check 检查依赖", BLUE)
    print()


if __name__ == "__main__":
    main()
