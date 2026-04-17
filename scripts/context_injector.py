#!/usr/bin/env python3
"""
Context Injection Layer - 上下文注入层

核心：在每次推理前主动注入相关规则、记忆、知识
"""

import re
import json
from typing import List, Dict, Optional
from pathlib import Path

# 导入规则管理器和知识图谱
import sys
sys.path.insert(0, str(Path(__file__).parent))

from knowledge_graph import KnowledgeGraph
from rule_manager import RuleManager

CONTEXT_TEMPLATE = """
═══════════════════════════════════════════════════════════════
📋 CONTEXT INJECTION - 上下文注入
═══════════════════════════════════════════════════════════════

## 🎯 当前任务分析
{user_input}

## ⭐ 相关规则（置信度排序）
{rules}

## 🧠 相关记忆
{memory}

## 🕸️ 相关知识图谱
{knowledge}

═══════════════════════════════════════════════════════════════
"""

class ContextInjector:
    """上下文注入器"""
    
    def __init__(self):
        self.kg = KnowledgeGraph()
        self.rm = RuleManager()
        self.load_memory()
    
    def load_memory(self):
        """加载记忆"""
        self.memory = []
        memory_dir = Path("/root/.openclaw/workspace/memory")
        if memory_dir.exists():
            for f in sorted(memory_dir.glob("*.md")):
                if f.name.startswith('.') or f.name == "index.md":
                    continue
                try:
                    with open(f, 'r') as mf:
                        content = mf.read()
                        # 提取关键信息
                        lines = [l.strip() for l in content.split('\n') if l.strip()]
                        # 取前10行作为摘要
                        summary = '\n'.join(lines[:10])
                        self.memory.append({
                            "date": f.stem,
                            "content": content,
                            "summary": summary
                        })
                except:
                    pass
    
    def extract_entities(self, user_input: str) -> List[str]:
        """从用户输入中提取实体"""
        entities = []
        
        # 实体名称列表（从知识图谱）
        for entity in self.kg.entities.values():
            if entity.id.lower() in user_input.lower():
                entities.append(entity.id)
            if entity.name.lower() in user_input.lower():
                entities.append(entity.id)
        
        # 提取关键项目名
        project_patterns = [
            r'(stylefitgw|hegr|mysstylefitgw)',
            r'(shopee|tiktok)',
            r'(postgresql|mysql|redis)',
            r'(服务器|数据库|项目)',
        ]
        for pattern in project_patterns:
            matches = re.findall(pattern, user_input, re.IGNORECASE)
            entities.extend(matches)
        
        return list(set(entities))
    
    def match_rules(self, user_input: str, entities: List[str]) -> List[Dict]:
        """匹配相关规则"""
        matched = []
        
        for rule in self.rm.rules.values():
            if rule.status != "active":
                continue
            
            # 检查规则文本是否与输入相关
            rule_text = rule.text.lower()
            input_lower = user_input.lower()
            
            if any(kw in input_lower for kw in [rule_text[:20], rule.category]):
                matched.append(rule.to_dict())
            elif any(entity in rule_text for entity in entities):
                matched.append(rule.to_dict())
        
        # 按置信度排序
        matched.sort(key=lambda x: x.get('confidence', 0), reverse=True)
        return matched[:5]  # 最多5条
    
    def select_memory(self, user_input: str, entities: List[str], limit: int = 5) -> List[Dict]:
        """选择相关记忆"""
        relevant = []
        
        for mem in reversed(self.memory):  # 最新优先
            # 检查日期
            score = 0
            
            # 检查实体是否在记忆中
            mem_lower = mem["content"].lower()
            for entity in entities:
                if entity.lower() in mem_lower:
                    score += 2
            
            # 检查关键词
            keywords = ["服务器", "电商", "项目", "配置", "错误"]
            for kw in keywords:
                if kw in user_input and kw in mem_lower:
                    score += 1
            
            if score > 0:
                relevant.append({**mem, "score": score})
        
        # 按分数排序
        relevant.sort(key=lambda x: x["score"], reverse=True)
        return relevant[:limit]
    
    def select_knowledge(self, entities: List[str]) -> List[str]:
        """选择相关知识"""
        knowledge_lines = []
        
        for entity_id in entities:
            entity = self.kg.get_entity(entity_id)
            if not entity:
                continue
            
            # 获取实体的直接关系
            for rel in entity.relations:
                line = f"• {entity.name} --{rel['type']}--> {rel['target']}"
                if 'context' in rel:
                    line += f" ({rel['context']})"
                knowledge_lines.append(line)
        
        return knowledge_lines
    
    def build_context(self, user_input: str) -> str:
        """构建上下文"""
        # 1. 提取实体
        entities = self.extract_entities(user_input)
        
        # 2. 匹配规则
        rules = self.match_rules(user_input, entities)
        rules_text = "\n".join([
            f"[P{r['confidence']:.0%}] [{r['category']}] {r['text']}"
            for r in rules
        ]) if rules else "（无相关规则）"
        
        # 3. 选择记忆
        memory = self.select_memory(user_input, entities)
        memory_text = "\n".join([
            f"[{m['date']}] {m['summary'][:100]}..."
            for m in memory
        ]) if memory else "（无相关记忆）"
        
        # 4. 选择知识
        knowledge = self.select_knowledge(entities)
        knowledge_text = "\n".join(knowledge) if knowledge else "（无相关知识）"
        
        # 5. 构建
        return CONTEXT_TEMPLATE.format(
            user_input=user_input,
            rules=rules_text,
            memory=memory_text,
            knowledge=knowledge_text
        )
    
    def inject(self, user_input: str) -> str:
        """注入上下文（对外接口）"""
        context = self.build_context(user_input)
        return context

def main():
    import argparse
    parser = argparse.ArgumentParser(description='Context Injection Layer')
    parser.add_argument('input', nargs='?', help='用户输入文本')
    parser.add_argument('--test', '-t', action='store_true', help='测试模式')
    args = parser.parse_args()
    
    injector = ContextInjector()
    
    if args.test or not args.input:
        # 测试
        test_input = "查看印尼地坪漆项目的情况"
        print(f"📝 测试输入: {test_input}")
        print()
        print(injector.build_context(test_input))
    else:
        print(injector.build_context(args.input))

if __name__ == '__main__':
    main()
