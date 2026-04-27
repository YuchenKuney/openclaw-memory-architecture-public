#!/usr/bin/env python3
"""
Context Injection Layer - 上下文注入层

核心架构：
def build_context(input):
    rules = match_rules(input)
    memory = retrieve_memory(input)
    return rules + memory + input

解决"模型看不到优化"问题
"""

import os
import sys
import re
from pathlib import Path
from typing import Dict, List, Optional

# 添加脚本目录到路径
sys.path.insert(0, str(Path(__file__).parent))

class ContextInjector:
    """上下文注入器"""
    
    def __init__(self):
        self.memory_path = Path("/root/.openclaw/workspace/MEMORY.md")
        self.user_path = Path("/root/.openclaw/workspace/USER.md")
        self.rules_path = Path("/root/.openclaw/workspace/rules")
    
    def match_rules(self, user_input: str) -> str:
        """匹配相关规则"""
        rules_text = ""
        
        # 从 MEMORY.md 提取铁律
        if self.memory_path.exists():
            with open(self.memory_path, 'r') as f:
                content = f.read()
            
            # 提取铁律部分
            if "## ⚠️ 铁律" in content:
                start = content.find("## ⚠️ 铁律")
                end = content.find("## ", start + 1)
                if end == -1:
                    end = len(content)
                iron_section = content[start:end]
                
                # 检查用户输入是否触发铁律
                iron_keywords = ["邮件", "汇报", "检测", "确认", "敏感", "仓库"]
                for keyword in iron_keywords:
                    if keyword in user_input:
                        rules_text += "## ⚠️ 铁律提醒\n"
                        lines = iron_section.split('\n')
                        for line in lines:
                            if line.strip() and line.strip()[0].isdigit():
                                rules_text += f"- {line.strip()}\n"
                        rules_text += "\n"
                        break
        
        # 从 USER.md 提取用户偏好
        if self.user_path.exists():
            with open(self.user_path, 'r') as f:
                content = f.read()
            
            # 检查是否匹配用户偏好
            user_keywords = ["坤哥", "偏好", "习惯", "风格"]
            for keyword in user_keywords:
                if keyword in user_input:
                    rules_text += "## 👤 用户偏好\n"
                    # 提取坤哥基本信息
                    if "## 坤哥基本信息" in content:
                        start = content.find("## 坤哥基本信息")
                        end = content.find("## ", start + 1)
                        if end == -1:
                            end = len(content)
                        user_section = content[start:end]
                        rules_text += user_section + "\n\n"
                    break
        
        return rules_text
    
    def retrieve_memory(self, user_input: str) -> str:
        """检索相关记忆"""
        memory_text = ""
        
        # 检查是否有相关任务
        tasks_dir = Path("/root/.openclaw/workspace/tasks")
        if tasks_dir.exists():
            task_keywords = ["任务", "项目", "工作", "执行", "完成"]
            for keyword in task_keywords:
                if keyword in user_input:
                    # 查找最近任务
                    recent_tasks = []
                    for task_file in sorted(tasks_dir.glob("*.md"), key=lambda x: x.stat().st_mtime, reverse=True)[:3]:
                        with open(task_file, 'r') as f:
                            content = f.read()
                            if content.startswith("# "):
                                title = content.split('\n')[0][2:].strip()
                                recent_tasks.append(f"- {title} ({task_file.name})")
                    
                    if recent_tasks:
                        memory_text += "## 📅 最近任务\n"
                        memory_text += "\n".join(recent_tasks) + "\n\n"
                    break
        
        # 检查是否有服务器相关查询
        server_keywords = ["服务器", "IP", "域名", "网站", "服务"]
        for keyword in server_keywords:
            if keyword in user_input:
                # 从 MEMORY.md 提取服务器信息
                if self.memory_path.exists():
                    with open(self.memory_path, 'r') as f:
                        content = f.read()
                    
                    if "服务器：" in content:
                        memory_text += "## 🖥️ 服务器资产\n"
                        # 提取服务器信息
                        import re
                        server_pattern = r'服务器：([^\n]+)'
                        server_match = re.search(server_pattern, content)
                        if server_match:
                            server_text = server_match.group(1)
                            server_items = re.findall(r'([^()]+)\(([\d\.]+)\)', server_text)
                            for name, ip in server_items:
                                clean_name = name.strip().replace('、', '').strip()
                                memory_text += f"- {clean_name}: {ip}\n"
                        memory_text += "\n"
                break
        
        return memory_text
    
    def build_context(self, user_input: str) -> str:
        """构建完整上下文"""
        # 1. 匹配规则
        rules = self.match_rules(user_input)
        
        # 2. 检索记忆
        memory = self.retrieve_memory(user_input)
        
        # 3. 返回组合上下文
        context = ""
        if rules:
            context += rules
        if memory:
            context += memory
        
        # 4. 添加原始输入
        if context:
            context += "## 💬 用户输入\n"
        
        context += user_input
        
        return context

def build_context(user_input: str) -> str:
    """主函数：构建上下文"""
    injector = ContextInjector()
    return injector.build_context(user_input)

def test():
    """测试函数"""
    test_inputs = [
        "帮我检查服务器状态",
        "邮件监控怎么样了",
        "坤哥有什么偏好",
        "最近有什么任务"
    ]
    
    injector = ContextInjector()
    
    for test_input in test_inputs:
        print("=" * 80)
        print(f"测试输入: {test_input}")
        print("=" * 80)
        
        context = injector.build_context(test_input)
        print(context)
        print("\n")

if __name__ == "__main__":
    test()
