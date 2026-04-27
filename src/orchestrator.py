#!/usr/bin/env python3
"""
Orchestrator - 统一调度大脑

核心功能：统一控制所有模块
- 何时用 rule
- 何时读 memory
- 何时写 log
- 何时触发提炼

架构：
├─ Input Analyzer (分析输入)
├─ Module Router (模块路由)
├─ Context Builder (上下文构建)
├─ Execution Engine (执行引擎)
└─ Result Processor (结果处理)
"""

import os
import sys
import json
import re
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, List, Optional

# 添加脚本目录到路径
sys.path.insert(0, str(Path(__file__).parent))

class Orchestrator:
    """统一调度大脑"""
    
    def __init__(self):
        self.modules = {
            "rule_manager": {"enabled": True, "last_used": None},
            "memory_manager": {"enabled": True, "last_used": None},
            "log_manager": {"enabled": True, "last_used": None},
            "distiller": {"enabled": True, "last_used": None},
            "watchdog": {"enabled": True, "last_used": None}
        }
        
        # 导入相关模块
        try:
            from rule_manager import RuleManager
            self.rule_manager = RuleManager()
        except ImportError:
            self.rule_manager = None
        
        try:
            from context_injector import ContextInjector
            self.context_injector = ContextInjector()
        except ImportError:
            self.context_injector = None
    
    def analyze_input(self, user_input: str) -> Dict:
        """分析输入，决定需要哪些模块"""
        analysis = {
            "needs_rules": False,
            "needs_memory": False,
            "needs_log": False,
            "needs_distill": False,
            "needs_watchdog": False
        }
        
        input_lower = user_input.lower()
        
        # 检查是否需要规则
        rule_keywords = ["规则", "习惯", "偏好", "铁律", "要求", "必须", "不能"]
        for keyword in rule_keywords:
            if keyword in input_lower:
                analysis["needs_rules"] = True
                break
        
        # 检查是否需要记忆
        memory_keywords = ["之前", "上次", "历史", "记忆", "记得", "做过", "任务"]
        for keyword in memory_keywords:
            if keyword in input_lower:
                analysis["needs_memory"] = True
                break
        
        # 检查是否需要写日志
        log_keywords = ["记录", "日志", "记下", "保存", "备忘"]
        for keyword in log_keywords:
            if keyword in input_lower:
                analysis["needs_log"] = True
                break
        
        # 检查是否需要提炼
        distill_keywords = ["总结", "提炼", "精华", "日报", "报告", "汇总"]
        for keyword in distill_keywords:
            if keyword in input_lower:
                analysis["needs_distill"] = True
                break
        
        # 检查是否需要看门狗
        watchdog_keywords = ["检查", "监控", "状态", "健康", "维护", "清理"]
        for keyword in watchdog_keywords:
            if keyword in input_lower:
                analysis["needs_watchdog"] = True
                break
        
        return analysis
    
    def decide_when_to_use_rule(self, analysis: Dict, user_input: str) -> bool:
        """决定何时用 rule"""
        if analysis["needs_rules"]:
            return True
        
        # 检查是否有铁律关键词
        iron_keywords = ["邮件", "汇报", "检测", "确认", "敏感", "仓库"]
        for keyword in iron_keywords:
            if keyword in user_input:
                return True
        
        return False
    
    def decide_when_to_read_memory(self, analysis: Dict, user_input: str) -> bool:
        """决定何时读 memory"""
        if analysis["needs_memory"]:
            return True
        
        # 检查是否有服务器/项目相关查询
        memory_keywords = ["服务器", "项目", "坤哥", "偏好", "习惯"]
        for keyword in memory_keywords:
            if keyword in user_input:
                return True
        
        return False
    
    def decide_when_to_write_log(self, analysis: Dict, user_input: str) -> bool:
        """决定何时写 log"""
        if analysis["needs_log"]:
            return True
        
        # 重要操作需要记录
        important_keywords = ["执行", "完成", "成功", "失败", "错误", "问题"]
        for keyword in important_keywords:
            if keyword in user_input:
                return True
        
        return False
    
    def decide_when_to_trigger_distill(self, analysis: Dict) -> bool:
        """决定何时触发提炼"""
        if analysis["needs_distill"]:
            return True
        
        # 检查距离上次提炼的时间
        if self.modules["distiller"]["last_used"]:
            last_time = datetime.fromisoformat(self.modules["distiller"]["last_used"])
            hours_since = (datetime.now() - last_time).total_seconds() / 3600
            if hours_since >= 24:  # 每24小时自动提炼一次
                return True
        
        return False
    
    def execute_rule_usage(self, user_input: str):
        """执行规则使用"""
        print("📋 [Orchestrator] 使用规则...")
        
        if self.rule_manager:
            # 这里可以调用 rule_manager 的相关方法
            print("  ✅ 规则管理器已加载")
        else:
            print("  ⚠️ 规则管理器未加载")
        
        self.modules["rule_manager"]["last_used"] = datetime.now().isoformat()
    
    def execute_memory_reading(self, user_input: str):
        """执行记忆读取"""
        print("🧠 [Orchestrator] 读取记忆...")
        
        if self.context_injector:
            memory = self.context_injector.retrieve_memory(user_input)
            if memory:
                print(f"  ✅ 检索到相关记忆 ({len(memory)} 字符)")
            else:
                print("  ℹ️ 未找到相关记忆")
        else:
            print("  ⚠️ 上下文注入器未加载")
        
        self.modules["memory_manager"]["last_used"] = datetime.now().isoformat()
    
    def execute_log_writing(self, user_input: str):
        """执行日志写入"""
        print("📝 [Orchestrator] 写入日志...")
        
        # 创建日志目录
        memory_dir = Path("/root/.openclaw/workspace/memory")
        memory_dir.mkdir(exist_ok=True)
        
        # 写入日志
        today = datetime.now().strftime("%Y-%m-%d")
        log_file = memory_dir / f"{today}.md"
        
        log_entry = f"## {datetime.now().strftime('%H:%M')}\n"
        log_entry += f"用户输入: {user_input}\n\n"
        
        with open(log_file, 'a') as f:
            f.write(log_entry)
        
        print(f"  ✅ 日志已写入: {log_file.name}")
        
        self.modules["log_manager"]["last_used"] = datetime.now().isoformat()
    
    def execute_distill_trigger(self):
        """执行提炼触发"""
        print("🔍 [Orchestrator] 触发日志提炼...")
        
        # 检查是否有未提炼的日志
        memory_dir = Path("/root/.openclaw/workspace/memory")
        today = datetime.now()
        
        undistilled = []
        for i in range(7):  # 检查最近7天
            d = today - timedelta(days=i)
            date_str = d.strftime("%Y-%m-%d")
            log_file = memory_dir / f"{date_str}.md"
            distilled_file = memory_dir / f"{date_str}_distilled.md"
            
            if log_file.exists() and not distilled_file.exists():
                undistilled.append(date_str)
        
        if undistilled:
            print(f"  📋 发现 {len(undistilled)} 个未提炼日志")
            # 这里可以调用 distiller 模块
        else:
            print("  ✅ 所有日志已提炼")
        
        self.modules["distiller"]["last_used"] = datetime.now().isoformat()
    
    def execute_watchdog_check(self):
        """执行看门狗检查"""
        print("🐕 [Orchestrator] 执行看门狗检查...")
        
        # 这里可以调用 watchdog 模块
        print("  🔍 系统健康检查...")
        
        self.modules["watchdog"]["last_used"] = datetime.now().isoformat()
    
    def orchestrate(self, user_input: str) -> Dict:
        """统一调度主函数"""
        print("=" * 80)
        print(f"🧠 Orchestrator - {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        print("=" * 80)
        
        # 1. 分析输入
        analysis = self.analyze_input(user_input)
        print(f"📊 输入分析: {json.dumps(analysis, ensure_ascii=False)}")
        
        # 2. 决策
        decisions = {
            "use_rule": self.decide_when_to_use_rule(analysis, user_input),
            "read_memory": self.decide_when_to_read_memory(analysis, user_input),
            "write_log": self.decide_when_to_write_log(analysis, user_input),
            "trigger_distill": self.decide_when_to_trigger_distill(analysis),
            "watchdog_check": analysis["needs_watchdog"]
        }
        
        print(f"🤔 调度决策: {json.dumps(decisions, ensure_ascii=False)}")
        
        # 3. 执行
        executed_modules = []
        
        if decisions["use_rule"]:
            self.execute_rule_usage(user_input)
            executed_modules.append("rule_usage")
        
        if decisions["read_memory"]:
            self.execute_memory_reading(user_input)
            executed_modules.append("memory_reading")
        
        if decisions["write_log"]:
            self.execute_log_writing(user_input)
            executed_modules.append("log_writing")
        
        if decisions["trigger_distill"]:
            self.execute_distill_trigger()
            executed_modules.append("distill_trigger")
        
        if decisions["watchdog_check"]:
            self.execute_watchdog_check()
            executed_modules.append("watchdog_check")
        
        # 4. 构建上下文
        context = ""
        if self.context_injector:
            context = self.context_injector.build_context(user_input)
        
        # 5. 返回结果
        result = {
            "input": user_input,
            "analysis": analysis,
            "decisions": decisions,
            "executed_modules": executed_modules,
            "context_length": len(context) if context else 0,
            "timestamp": datetime.now().isoformat()
        }
        
        print("=" * 80)
        print(f"✅ 调度完成: {len(executed_modules)} 个模块已执行")
        print("=" * 80)
        
        return result

def test():
    """测试函数"""
    orchestrator = Orchestrator()
    
    test_inputs = [
        "帮我检查服务器状态",
        "邮件监控怎么样了",
        "记录一下今天的任务完成情况",
        "总结一下本周的工作",
        "坤哥有什么偏好"
    ]
    
    for test_input in test_inputs:
        result = orchestrator.orchestrate(test_input)
        print(f"\n📋 测试输入: {test_input}")
        print(f"📊 分析结果: {json.dumps(result['analysis'], ensure_ascii=False)}")
        print(f"🤔 调度决策: {json.dumps(result['decisions'], ensure_ascii=False)}")
        print(f"🔄 执行模块: {result['executed_modules']}")
        print("-" * 80)

if __name__ == "__main__":
    test()
