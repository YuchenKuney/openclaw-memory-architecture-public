#!/usr/bin/env python3
"""
Orchestrator - 统一调度器

核心功能：协调所有模块，作为系统的大脑
负责：
1. 什么时候用 rule
2. 什么时候写 memory
3. 什么时候触发 distill
4. 什么时候执行 watchdog
5. 什么时候查询知识图谱

架构：
├─ Input Analyzer (输入分析)
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
from typing import Dict, List, Optional, Any
import threading
import time

# 添加脚本目录到路径
sys.path.insert(0, str(Path(__file__).parent))

from rule_manager import RuleManager
from knowledge_graph import KnowledgeGraph
from memory_lifecycle import LifecycleManager
from log_distiller import LogDistiller
from context_builder import ContextBuilder

class Orchestrator:
    """统一调度器"""
    
    def __init__(self):
        self.rule_manager = RuleManager()
        self.knowledge_graph = KnowledgeGraph()
        self.lifecycle = LifecycleManager()
        self.distiller = LogDistiller()
        self.context_builder = ContextBuilder()
        
        # 模块状态
        self.modules = {
            "rule_manager": {"enabled": True, "last_run": None},
            "knowledge_graph": {"enabled": True, "last_run": None},
            "memory_lifecycle": {"enabled": True, "last_run": None},
            "log_distiller": {"enabled": True, "last_run": None},
            "context_builder": {"enabled": True, "last_run": None}
        }
        
        # 调度配置
        self.config = {
            "auto_distill_days": 7,
            "auto_cleanup_threshold": 10,
            "rule_extraction_interval": 24,  # 小时
            "knowledge_update_interval": 12,  # 小时
            "context_injection_enabled": True
        }
        
        # 加载配置
        self.load_config()
    
    def load_config(self):
        """加载配置"""
        config_file = Path("/root/.openclaw/workspace/.orchestrator.json")
        if config_file.exists():
            with open(config_file, 'r') as f:
                self.config.update(json.load(f))
    
    def save_config(self):
        """保存配置"""
        config_file = Path("/root/.openclaw/workspace/.orchestrator.json")
        with open(config_file, 'w') as f:
            json.dump(self.config, f, indent=2)
    
    def analyze_input(self, user_input: str) -> Dict:
        """分析用户输入，决定需要哪些模块"""
        analysis = {
            "needs_rules": False,
            "needs_memory": False,
            "needs_knowledge": False,
            "needs_distill": False,
            "needs_watchdog": False,
            "priority": "normal"
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
        
        # 检查是否需要知识图谱
        knowledge_keywords = ["项目", "服务器", "数据库", "域名", "IP", "配置", "实体"]
        for keyword in knowledge_keywords:
            if keyword in input_lower:
                analysis["needs_knowledge"] = True
                break
        
        # 检查是否需要提炼
        distill_keywords = ["总结", "提炼", "精华", "日报", "日志", "报告"]
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
        
        # 设置优先级
        urgent_keywords = ["紧急", "立刻", "马上", "现在", "立即", "快"]
        for keyword in urgent_keywords:
            if keyword in input_lower:
                analysis["priority"] = "urgent"
                break
        
        return analysis
    
    def route_to_modules(self, analysis: Dict) -> List[str]:
        """根据分析结果路由到相应模块"""
        modules_to_run = []
        
        if analysis["needs_rules"]:
            modules_to_run.append("rule_manager")
        
        if analysis["needs_memory"]:
            modules_to_run.append("memory_lifecycle")
        
        if analysis["needs_knowledge"]:
            modules_to_run.append("knowledge_graph")
        
        if analysis["needs_distill"]:
            modules_to_run.append("log_distiller")
        
        if analysis["needs_watchdog"]:
            modules_to_run.append("memory_lifecycle")
        
        return modules_to_run
    
    def build_context(self, user_input: str, analysis: Dict) -> str:
        """构建上下文"""
        if not self.config["context_injection_enabled"]:
            return user_input
        
        # 使用 context_builder
        return self.context_builder.build_light_context(user_input)
    
    def execute_rule_extraction(self):
        """执行规则提取"""
        print("📋 [Orchestrator] 执行规则提取...")
        
        # 检查是否需要提取
        last_run = self.modules["rule_manager"]["last_run"]
        if last_run:
            last_time = datetime.fromisoformat(last_run)
            hours_since = (datetime.now() - last_time).total_seconds() / 3600
            if hours_since < self.config["rule_extraction_interval"]:
                print(f"  ⏰ 距离上次提取 {hours_since:.1f} 小时，跳过")
                return
        
        # 提取规则
        memory_dir = Path("/root/.openclaw/workspace/memory")
        today = datetime.now().strftime("%Y-%m-%d")
        log_file = memory_dir / f"{today}.md"
        
        if log_file.exists():
            with open(log_file, 'r') as f:
                content = f.read()
            
            # 简单规则提取逻辑
            rules_found = []
            lines = content.split('\n')
            for line in lines:
                if "必须" in line or "不能" in line or "要" in line or "不要" in line:
                    if len(line) > 10 and len(line) < 200:
                        rules_found.append(line.strip())
            
            if rules_found:
                print(f"  ✅ 提取到 {len(rules_found)} 条规则")
                # 这里可以调用 rule_manager 的提取方法
                # self.rule_manager.extract_from_text(content)
        
        self.modules["rule_manager"]["last_run"] = datetime.now().isoformat()
    
    def execute_knowledge_update(self):
        """执行知识图谱更新"""
        print("🏗️ [Orchestrator] 执行知识图谱更新...")
        
        last_run = self.modules["knowledge_graph"]["last_run"]
        if last_run:
            last_time = datetime.fromisoformat(last_run)
            hours_since = (datetime.now() - last_time).total_seconds() / 3600
            if hours_since < self.config["knowledge_update_interval"]:
                print(f"  ⏰ 距离上次更新 {hours_since:.1f} 小时，跳过")
                return
        
        # 更新知识图谱
        # 这里可以添加自动从记忆文件中提取实体的逻辑
        
        self.modules["knowledge_graph"]["last_run"] = datetime.now().isoformat()
    
    def execute_auto_distill(self):
        """执行自动日志提炼"""
        print("📝 [Orchestrator] 检查是否需要日志提炼...")
        
        # 检查最近7天的日志
        memory_dir = Path("/root/.openclaw/workspace/memory")
        today = datetime.now()
        
        undistilled = []
        for i in range(self.config["auto_distill_days"]):
            d = today - timedelta(days=i)
            date_str = d.strftime("%Y-%m-%d")
            log_file = memory_dir / f"{date_str}.md"
            
            if log_file.exists():
                # 检查是否已经提炼过
                distilled_file = memory_dir / f"{date_str}_distilled.md"
                if not distilled_file.exists():
                    undistilled.append(date_str)
        
        if undistilled:
            print(f"  📋 发现 {len(undistilled)} 个未提炼日志")
            # 这里可以调用 distiller
            # for date_str in undistilled[:2]:  # 最多2个
            #     self.distiller.distill(date_str)
        else:
            print("  ✅ 所有日志已提炼")
    
    def execute_auto_cleanup(self):
        """执行自动清理"""
        print("🧹 [Orchestrator] 检查是否需要清理...")
        
        stats = self.lifecycle.check()
        if stats['to_archive'] >= self.config["auto_cleanup_threshold"]:
            print(f"  ⚠️ 待归档文件 {stats['to_archive']} >= 阈值 {self.config['auto_cleanup_threshold']}")
            # 这里可以调用 lifecycle.run_cleanup()
        else:
            print(f"  ✅ 待归档文件 {stats['to_archive']} < 阈值，跳过")
    
    def process_user_input(self, user_input: str) -> Dict:
        """处理用户输入"""
        print("=" * 80)
        print(f"🧠 Orchestrator - {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        print("=" * 80)
        
        # 1. 分析输入
        analysis = self.analyze_input(user_input)
        print(f"📊 输入分析: {json.dumps(analysis, ensure_ascii=False, indent=2)}")
        
        # 2. 路由到模块
        modules_to_run = self.route_to_modules(analysis)
        print(f"🔄 模块路由: {modules_to_run}")
        
        # 3. 构建上下文
        context = self.build_context(user_input, analysis)
        print(f"📝 上下文构建完成 ({len(context)} 字符)")
        
        # 4. 执行后台任务（如果需要）
        if "rule_manager" in modules_to_run:
            self.execute_rule_extraction()
        
        if "knowledge_graph" in modules_to_run:
            self.execute_knowledge_update()
        
        if "log_distiller" in modules_to_run:
            self.execute_auto_distill()
        
        if "memory_lifecycle" in modules_to_run:
            self.execute_auto_cleanup()
        
        # 5. 返回结果
        result = {
            "analysis": analysis,
            "modules_executed": modules_to_run,
            "context": context,
            "timestamp": datetime.now().isoformat()
        }
        
        print("=" * 80)
        print("✅ Orchestrator 处理完成")
        print("=" * 80)
        
        return result
    
    def run_scheduled_tasks(self):
        """运行定时任务"""
        print("⏰ [Orchestrator] 执行定时任务...")
        
        tasks = [
            ("规则提取", self.execute_rule_extraction),
            ("知识图谱更新", self.execute_knowledge_update),
            ("自动提炼检查", self.execute_auto_distill),
            ("自动清理检查", self.execute_auto_cleanup)
        ]
        
        for task_name, task_func in tasks:
            try:
                task_func()
            except Exception as e:
                print(f"  ❌ {task_name} 失败: {str(e)}")

def test():
    """测试函数"""
    orchestrator = Orchestrator()
    
    test_inputs = [
        "帮我检查服务器状态",
        "邮件监控怎么样了",
        "总结一下今天的日志",
        "提取一下最近的规则",
        "更新知识图谱",
        "紧急！立即检查所有服务"
    ]
    
    for test_input in test_inputs:
        result = orchestrator.process_user_input(test_input)
        print(f"\n📋 测试输入: {test_input}")
        print(f"📊 分析结果: {json.dumps(result['analysis'], ensure_ascii=False)}")
        print(f"🔄 执行模块: {result['modules_executed']}")
        print(f"📝 上下文预览: {result['context'][:200]}...")
        print("-" * 80)

if __name__ == "__main__":
    test()
