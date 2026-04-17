#!/usr/bin/env python3
"""
Context Builder - 上下文构建器

核心功能：在每次推理前，主动注入相关上下文
解决"文件存在但模型看不到"的问题

架构：
1. 接收用户输入
2. 匹配相关规则
3. 检索相关记忆
4. 查询知识图谱
5. 构建完整上下文
6. 返回给模型

使用方式：
from context_builder import build_context
context = build_context("帮我检查服务器状态")
"""

import os
import sys
import json
from pathlib import Path
from typing import Dict, List, Optional, Tuple
import re

# 添加脚本目录到路径
sys.path.insert(0, str(Path(__file__).parent))

from rule_manager import RuleManager
from knowledge_graph import KnowledgeGraph
from memory_lifecycle import LifecycleManager

class ContextBuilder:
    """上下文构建器"""
    
    def __init__(self):
        self.rule_manager = RuleManager()
        self.knowledge_graph = KnowledgeGraph()
        self.lifecycle = LifecycleManager()
        
    def match_rules(self, user_input: str) -> List[Dict]:
        """匹配相关规则"""
        matched_rules = []
        
        for rule_id, rule in self.rule_manager.rules.items():
            # 基于规则文本内容匹配
            rule_text = rule.text.lower()
            user_input_lower = user_input.lower()
            
            # 简单关键词匹配
            # 提取规则中的关键词（非停用词）
            words = re.findall(r'\b\w{3,}\b', rule_text)
            for word in words:
                if word in user_input_lower:
                    matched_rules.append({
                        "id": rule_id,
                        "title": f"规则 {rule.id}",
                        "content": rule.text,
                        "category": rule.category,
                        "confidence": rule.confidence
                    })
                    break
        
        # 按置信度排序
        matched_rules.sort(key=lambda x: x["confidence"], reverse=True)
        
        return matched_rules[:5]  # 最多返回5条
    
    def retrieve_memory(self, user_input: str) -> Dict:
        """检索相关记忆"""
        memory_context = {
            "user_preferences": [],
            "recent_tasks": [],
            "important_events": []
        }
        
        # 1. 从 MEMORY.md 提取用户偏好
        memory_path = Path("/root/.openclaw/workspace/MEMORY.md")
        if memory_path.exists():
            with open(memory_path, 'r') as f:
                content = f.read()
                
            # 提取铁律部分
            iron_rules = []
            if "## ⚠️ 铁律" in content:
                start = content.find("## ⚠️ 铁律")
                end = content.find("## ", start + 1)
                if end == -1:
                    end = len(content)
                iron_section = content[start:end]
                lines = iron_section.split('\n')
                for line in lines:
                    if line.strip() and line.strip()[0].isdigit():
                        iron_rules.append(line.strip())
            
            if iron_rules:
                memory_context["user_preferences"] = iron_rules
        
        # 2. 从最近任务中提取
        tasks_dir = Path("/root/.openclaw/workspace/tasks")
        if tasks_dir.exists():
            recent_tasks = []
            for task_file in sorted(tasks_dir.glob("*.md"), key=lambda x: x.stat().st_mtime, reverse=True)[:3]:
                with open(task_file, 'r') as f:
                    content = f.read()
                    # 提取任务标题
                    if content.startswith("# "):
                        title = content.split('\n')[0][2:].strip()
                        recent_tasks.append({
                            "file": task_file.name,
                            "title": title
                        })
            memory_context["recent_tasks"] = recent_tasks
        
        return memory_context
    
    def query_knowledge_graph(self, user_input: str) -> Dict:
        """查询知识图谱"""
        kg_context = {
            "entities": [],
            "relationships": []
        }
        
        # 关键词匹配实体
        keywords = user_input.lower().split()
        matched_entities = []
        
        for entity_id, entity in self.knowledge_graph.entities.items():
            entity_name = entity.name.lower()
            entity_type = entity.type.lower()
            
            # 检查是否匹配
            for keyword in keywords:
                if len(keyword) > 3:  # 只匹配长度大于3的关键词
                    if keyword in entity_name or keyword in entity_type:
                        matched_entities.append({
                            "id": entity_id,
                            "name": entity.name,
                            "type": entity.type,
                            "properties": entity.properties
                        })
                        break
        
        # 获取相关关系
        if matched_entities:
            for entity in matched_entities[:3]:  # 最多3个实体
                entity_id = entity["id"]
                relationships = self.knowledge_graph.get_relationships(entity_id)
                if relationships:
                    kg_context["relationships"].extend(relationships)
        
        kg_context["entities"] = matched_entities[:5]  # 最多5个实体
        
        return kg_context
    
    def build_context(self, user_input: str) -> str:
        """构建完整上下文"""
        # 1. 匹配规则
        matched_rules = self.match_rules(user_input)
        
        # 2. 检索记忆
        memory_context = self.retrieve_memory(user_input)
        
        # 3. 查询知识图谱
        kg_context = self.query_knowledge_graph(user_input)
        
        # 4. 构建上下文字符串
        context_parts = []
        
        # 添加规则
        if matched_rules:
            context_parts.append("## 📋 相关规则")
            for rule in matched_rules:
                context_parts.append(f"### {rule['title']} (置信度: {rule['confidence']:.2f})")
                context_parts.append(rule['content'])
                context_parts.append("")
        
        # 添加用户偏好
        if memory_context["user_preferences"]:
            context_parts.append("## ⚠️ 用户偏好/铁律")
            for rule in memory_context["user_preferences"]:
                context_parts.append(f"- {rule}")
            context_parts.append("")
        
        # 添加最近任务
        if memory_context["recent_tasks"]:
            context_parts.append("## 📅 最近任务")
            for task in memory_context["recent_tasks"]:
                context_parts.append(f"- {task['title']} ({task['file']})")
            context_parts.append("")
        
        # 添加知识图谱
        if kg_context["entities"]:
            context_parts.append("## 🏗️ 相关实体")
            for entity in kg_context["entities"]:
                context_parts.append(f"### {entity['name']} ({entity['type']})")
                for key, value in entity["properties"].items():
                    context_parts.append(f"  - {key}: {value}")
                context_parts.append("")
        
        if kg_context["relationships"]:
            context_parts.append("## 🔗 相关关系")
            for rel in kg_context["relationships"][:3]:  # 最多3个关系
                context_parts.append(f"- {rel['source']} → {rel['target']}: {rel['type']}")
            context_parts.append("")
        
        # 添加原始输入
        context_parts.append("## 💬 用户输入")
        context_parts.append(user_input)
        
        return "\n".join(context_parts)
    
    def build_light_context(self, user_input: str) -> str:
        """构建轻量级上下文（用于简单查询）"""
        # 只匹配高置信度规则
        matched_rules = self.match_rules(user_input)
        high_confidence_rules = [r for r in matched_rules if r["confidence"] > 0.8]
        
        context_parts = []
        
        if high_confidence_rules:
            context_parts.append("📋 相关规则:")
            for rule in high_confidence_rules[:2]:  # 最多2条
                context_parts.append(f"- {rule['title']}: {rule['content'][:100]}...")
        
        # 检查是否有铁律相关
        memory_context = self.retrieve_memory(user_input)
        if memory_context["user_preferences"]:
            # 检查用户输入是否包含铁律关键词
            iron_keywords = ["邮件", "汇报", "检测", "确认", "敏感", "仓库"]
            for keyword in iron_keywords:
                if keyword in user_input:
                    context_parts.append("⚠️ 铁律提醒:")
                    for rule in memory_context["user_preferences"][:2]:
                        context_parts.append(f"- {rule}")
                    break
        
        if context_parts:
            return "\n".join(context_parts) + "\n\n" + user_input
        
        return user_input

def build_context(user_input: str, light: bool = False) -> str:
    """构建上下文（主函数）"""
    builder = ContextBuilder()
    if light:
        return builder.build_light_context(user_input)
    return builder.build_context(user_input)

def test():
    """测试函数"""
    test_inputs = [
        "帮我检查服务器状态",
        "邮件监控怎么样了",
        "模型切换通知发了吗",
        "今天有什么重要事项"
    ]
    
    builder = ContextBuilder()
    
    for test_input in test_inputs:
        print("=" * 80)
        print(f"测试输入: {test_input}")
        print("=" * 80)
        
        # 测试完整上下文
        context = builder.build_light_context(test_input)
        print(context)
        print("\n")

if __name__ == "__main__":
    test()
