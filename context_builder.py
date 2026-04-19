#!/usr/bin/env python3
"""
Context Builder - 上下文构建器（PR④ 联动版）

核心功能：在每次推理前，主动注入相关上下文

架构（PR④ 三层联动）：
  感知层：detector.py 检测到风险事件
        ↓
  认知层：knowledge_graph.py 管理实体关系
        ↓  link_event_to_entity()
  记忆层：memory/ 日记文件 + MEMORY.md 长期记忆
             ↓ build_entity_context()
        context_builder.py 整合所有层
             ↓
        build_context() → 返回给模型

PR④ 改进：
1. 修复 get_relationships() 方法名（应为 query_relation）
2. 使用新的 build_entity_context() 整合知识图谱
3. 联动 populate_from_memory() 从记忆文件抽取实体
4. 构建 context 时包含知识图谱相关性
"""

import os
import sys
import json
from pathlib import Path
from typing import Dict, List, Optional, Tuple
import re

from knowledge_graph import KnowledgeGraph

# ============ 三层记忆联动 ============

class ContextBuilder:
    """上下文构建器（PR④ 三层联动版）"""

    def __init__(self):
        self.knowledge_graph = KnowledgeGraph()

    def match_rules(self, user_input: str) -> List[Dict]:
        """匹配相关规则（感知层）"""
        # 简化版：通过关键词匹配
        rule_manager_path = Path("/root/.openclaw/workspace/rule_manager.py")
        if not rule_manager_path.exists():
            return []

        try:
            sys.path.insert(0, str(Path("/root/.openclaw/workspace")))
            from rule_manager import RuleManager
            rm = RuleManager()
            matched = []
            for rid, rule in rm.rules.items():
                rule_text = rule.text.lower()
                user_lower = user_input.lower()
                words = re.findall(r'\b\w{3,}\b', rule_text)
                for word in words:
                    if word in user_lower and len(word) > 3:
                        matched.append({
                            "id": rid,
                            "title": f"规则 {rid}",
                            "content": rule.text,
                            "category": rule.category,
                            "confidence": rule.confidence
                        })
                        break
            matched.sort(key=lambda x: x["confidence"], reverse=True)
            return matched[:5]
        except Exception:
            return []

    def retrieve_memory(self, user_input: str) -> Dict:
        """检索记忆层（MEMORY.md + memory/ 日记）"""
        memory_context = {
            "user_preferences": [],
            "recent_tasks": [],
            "important_events": []
        }

        # 1. 从 MEMORY.md 提取铁律
        memory_path = Path("/root/.openclaw/workspace/MEMORY.md")
        if memory_path.exists():
            with open(memory_path, 'r', encoding='utf-8', errors='ignore') as f:
                content = f.read()
            iron_rules = []
            if "## ⚠️ 铁律" in content:
                start = content.find("## ⚠️ 铁律")
                end = content.find("## ", start + 1)
                if end == -1:
                    end = len(content)
                iron_section = content[start:end]
                for line in iron_section.split('\n'):
                    if line.strip() and line.strip()[0].isdigit():
                        iron_rules.append(line.strip())
            memory_context["user_preferences"] = iron_rules

        # 2. 从 tasks/ 提取最近任务
        tasks_dir = Path("/root/.openclaw/workspace/tasks")
        if tasks_dir.exists():
            recent_tasks = []
            for task_file in sorted(
                tasks_dir.glob("*.md"),
                key=lambda x: x.stat().st_mtime,
                reverse=True
            )[:3]:
                try:
                    content = task_file.read_text(encoding='utf-8', errors='ignore')
                    if content.startswith("# "):
                        title = content.split('\n')[0][2:].strip()
                        recent_tasks.append({
                            "file": task_file.name,
                            "title": title
                        })
                except Exception:
                    continue
            memory_context["recent_tasks"] = recent_tasks

        return memory_context

    def query_knowledge_graph(self, user_input: str) -> Dict:
        """查询认知层（知识图谱）"""
        kg_context = {
            "entities": [],
            "relationships": []
        }

        keywords = [w for w in user_input.split() if len(w) > 2]
        matched_entities = self.knowledge_graph.get_relevant_entities(keywords, limit=5)

        for entity in matched_entities:
            kg_context["entities"].append({
                "id": entity.id,
                "name": entity.name,
                "type": entity.type,
                "properties": entity.properties,
                "event_count": entity.event_count,
                "tags": list(entity.tags),
            })
            # 使用 query_relation 而非 get_relationships
            for rel in entity.relations[:3]:
                kg_context["relationships"].append({
                    "source": entity.id,
                    "type": rel["type"],
                    "target": rel["target"],
                    "context": rel.get("context", ""),
                })

        return kg_context

    def build_context(self, user_input: str, include_kg: bool = True) -> str:
        """构建完整上下文（整合三层）"""
        context_parts = []

        # ===== 感知层：相关规则 =====
        matched_rules = self.match_rules(user_input)
        if matched_rules:
            context_parts.append("## 📋 相关规则")
            for rule in matched_rules:
                conf = rule.get("confidence", 0)
                context_parts.append(
                    f"### {rule['title']} (置信度: {conf:.2f}) [{rule.get('category', 'general')}]"
                )
                context_parts.append(rule['content'])
                context_parts.append("")
            context_parts.append("")

        # ===== 认知层：知识图谱（PR④ 联动） =====
        if include_kg:
            kg_context = self.query_knowledge_graph(user_input)
            if kg_context["entities"]:
                context_parts.append("## 🕸️ 知识图谱")
                for entity in kg_context["entities"]:
                    context_parts.append(
                        f"**{entity['name']}** ({entity['type']}) "
                        f"触发:{entity.get('event_count', 0)}次"
                    )
                    tags = entity.get('tags', [])
                    if tags:
                        context_parts.append(f"  标签: {', '.join(tags[:5])}")
                    context_parts.append("")
            if kg_context["relationships"]:
                context_parts.append("## 🔗 相关关系")
                for rel in kg_context["relationships"][:5]:
                    context_parts.append(
                        f"- {rel['source']} --{rel['type']}--> {rel['target']}"
                    )
                context_parts.append("")

        # ===== 记忆层：用户偏好 =====
        memory_context = self.retrieve_memory(user_input)
        if memory_context["user_preferences"]:
            context_parts.append("## ⚠️ 用户偏好/铁律")
            for rule in memory_context["user_preferences"]:
                context_parts.append(f"- {rule}")
            context_parts.append("")

        if memory_context["recent_tasks"]:
            context_parts.append("## 📅 最近任务")
            for task in memory_context["recent_tasks"]:
                context_parts.append(f"- {task['title']} ({task['file']})")
            context_parts.append("")

        # ===== 原始输入 =====
        context_parts.append("## 💬 用户输入")
        context_parts.append(user_input)

        return "\n".join(context_parts)

    def build_light_context(self, user_input: str) -> str:
        """构建轻量级上下文（用于简单查询）"""
        context_parts = []

        # 高置信度规则
        matched_rules = self.match_rules(user_input)
        high_conf = [r for r in matched_rules if r.get("confidence", 0) > 0.8]
        if high_conf:
            context_parts.append("📋 高置信度规则:")
            for rule in high_conf[:2]:
                context_parts.append(f"- {rule['title']}: {rule['content'][:80]}...")

        # 知识图谱实体（轻量）
        keywords = [w for w in user_input.split() if len(w) > 2]
        entities = self.knowledge_graph.get_relevant_entities(keywords, limit=3)
        if entities:
            context_parts.append("🕸️ 相关实体:")
            for e in entities:
                context_parts.append(f"- {e.name} ({e.type})")

        if context_parts:
            return "\n".join(context_parts) + "\n\n" + user_input

        return user_input


# ============ 主函数 ============

def build_context(user_input: str, light: bool = False) -> str:
    """构建上下文（主函数）"""
    builder = ContextBuilder()
    if light:
        return builder.build_light_context(user_input)
    return builder.build_context(user_input)


# ============ 测试 ============

def test():
    """测试三层联动"""
    test_inputs = [
        "帮我检查喂鱼提醒的 cron 状态",
        "memoryIntegrity 相关漏洞",
        "拦截器工作正常吗",
        "今天的安全扫描结果",
        "帮我审计代码仓库",
    ]

    builder = ContextBuilder()

    print("=" * 70)
    print("PR④ Context Builder 三层联动测试")
    print("=" * 70)

    for test_input in test_inputs:
        print(f"\n📥 输入: {test_input}")
        print("-" * 60)
        context = builder.build_light_context(test_input)
        print(context)
        print()


if __name__ == "__main__":
    test()
