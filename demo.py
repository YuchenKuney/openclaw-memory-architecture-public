#!/usr/bin/env python3
"""
Demo 入口脚本

用法：
    python3 demo.py                    # 交互式选择 demo
    python3 demo.py --demo 1           # 运行 Demo 1（长连接审批）
    python3 demo.py --demo 2           # 运行 Demo 2（回调地址审批）
    python3 demo.py --demo ecommerce   # 运行电商记忆演进场景

前置条件：
    export FEISHU_APP_ID=cli_xxx
    export FEISHU_APP_SECRET=xxx
    export FEISHU_VERIFICATION_TOKEN=xxx
    export FEISHU_GROUP_ID=oc_xxx
"""

import sys
import os

# 确保 clawkeeper 在路径中
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import argparse


def main():
    parser = argparse.ArgumentParser(description="Demo 脚本集")
    parser.add_argument("--demo", default="menu",
                        choices=["menu", "1", "2", "ecommerce"],
                        help="选择 demo: 1=长连接审批, 2=回调地址审批, ecommerce=电商记忆演进")
    parser.add_argument("--scenario", action="store_true",
                        help="运行电商场景（交互式）")
    args = parser.parse_args()

    if args.demo == "ecommerce" or args.scenario:
        # 电商记忆演进场景
        from demo.scenarios.ecommerce import SCENARIO
        from demo.engine.runner import run_scenario

        print("🛒 电商记忆演进 Demo")
        print("=" * 50)
        result = run_scenario(SCENARIO)
        if result:
            print("\n✅ Demo 完成！")
        else:
            print("\n❌ Demo 中途退出")

    elif args.demo == "1":
        # Demo 1: 长连接审批模式
        from demo.demo1_longpoll import demo_approval_scenario
        demo_approval_scenario()

    elif args.demo == "2":
        # Demo 2: 回调地址审批模式
        from demo.demo2_callback import demo_approval_scenario
        demo_approval_scenario()

    else:
        # 交互式菜单
        print("""
╔══════════════════════════════════════════════════════════════╗
║                    OpenClaw Memory Demo                      ║
╠══════════════════════════════════════════════════════════════╣
║                                                              ║
║  🛒 电商记忆演进 Demo（Demo 0 / ecommerce）                  ║
║     python3 demo.py --demo ecommerce --scenario              ║
║     展示 AI 在电商场景中「逐步变聪明」的过程                  ║
║                                                              ║
║  📡 Demo 1: 长连接审批模式                                   ║
║     python3 demo.py --demo 1                                 ║
║     原理：OpenClaw 每5秒轮询飞书群，检测@审批命令             ║
║     优点：简单（只需读取消息权限）                            ║
║     缺点：有5秒轮询延迟                                      ║
║                                                              ║
║  🔗 Demo 2: 回调地址审批模式                                 ║
║     python3 demo.py --demo 2                                 ║
║     原理：公网回调地址 + 飞书事件订阅                        ║
║     优点：卡片按钮 + toast 弹窗 + 实时响应                  ║
║     缺点：需公网地址 + 事件订阅配置                         ║
║                                                              ║
║  环境变量（脱敏）：                                          ║
║     FEISHU_APP_ID / FEISHU_APP_SECRET                       ║
║     FEISHU_VERIFICATION_TOKEN / FEISHU_GROUP_ID             ║
║                                                              ║
╚══════════════════════════════════════════════════════════════╝
        """)


if __name__ == "__main__":
    main()
