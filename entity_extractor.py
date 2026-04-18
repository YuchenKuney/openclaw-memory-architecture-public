#!/usr/bin/env python3
"""
Entity Extractor - 实体提取器

从记忆文件中自动提取实体和关系
支持：
- 项目 (project)
- 服务器 (server)
- 数据库 (database)
- 域名 (domain)
- 邮箱 (email)
- 人物 (person)
- 任务 (task)
"""

import re
import json
from datetime import datetime
from pathlib import Path
from typing import List, Dict, Optional

MEMORY_DIR = Path("/root/.openclaw/workspace/memory")
MEMORY_FILE = Path("/root/.openclaw/workspace/MEMORY.md")
USER_FILE = Path("/root/.openclaw/workspace/USER.md")

class EntityExtractor:
    """实体提取器"""
    
    def __init__(self):
        self.entities = []
        self.relationships = []
    
    def extract_from_memory_md(self) -> List[Dict]:
        """从 MEMORY.md 提取实体"""
        if not MEMORY_FILE.exists():
            return []
        
        with open(MEMORY_FILE, 'r') as f:
            content = f.read()
        
        entities = []
        
        # 提取服务器信息
        server_pattern = r'服务器：([^\n]+)'
        server_match = re.search(server_pattern, content)
        if server_match:
            server_text = server_match.group(1)
            # 解析服务器格式: 马来西亚染发膏([已脱敏])、印尼地坪漆([已脱敏])、印尼染发膏([已脱敏])
            server_items = re.findall(r'([^()]+)\(([\d\.]+)\)', server_text)
            for name, ip in server_items:
                # 清理服务器名称
                clean_name = name.strip().replace('、', '').strip()
                entities.append({
                    "type": "server",
                    "name": clean_name,
                    "properties": {
                        "ip": ip.strip(),
                        "description": f"{clean_name} 服务器"
                    }
                })
        
        # 提取邮箱
        email_pattern = r"[\w\.-]+@[\w\.-]+\.\w+"
        emails = re.findall(email_pattern, content)
        for email in emails:
            entities.append({
                "type": "email",
                "name": email,
                "properties": {"address": email}
            })
        
        # 提取域名
        domain_pattern = r'域名：([^\n]+)'
        domain_match = re.search(domain_pattern, content)
        if domain_match:
            domain_text = domain_match.group(1)
            # 提取 [已脱敏] 后缀域名
            qzz_domains = re.findall(r'([\w\-]+\.qzz\.io)', domain_text)
            for domain in qzz_domains:
                entities.append({
                    "type": "domain",
                    "name": domain,
                    "properties": {"url": f"https://{domain}"}
                })
        
        # 提取任务
        task_pattern = r'- (\d{2}:\d{2}) ([^\n]+)'
        tasks = re.findall(task_pattern, content)
        for time_desc, description in tasks:
            if "电商早报" in description or "提醒喂鱼" in description or "检查" in description:
                entities.append({
                    "type": "task",
                    "name": f"定时任务: {time_desc}",
                    "properties": {
                        "time": time_desc,
                        "description": description.strip()
                    }
                })
        
        return entities
    
    def extract_from_user_md(self) -> List[Dict]:
        """从 USER.md 提取实体"""
        if not USER_FILE.exists():
            return []
        
        with open(USER_FILE, 'r') as f:
            content = f.read()
        
        entities = []
        
        # 提取人物
        person_pattern = r"## 坤哥基本信息\n- 名字：([^\n]+)\n- 称呼：([^\n]+)\n- 时区：([^\n]+)\n- 邮箱：([^\n]+)"
        person_match = re.search(person_pattern, content)
        if person_match:
            name, title, timezone, emails = person_match.groups()
            entities.append({
                "type": "person",
                "name": name.strip(),
                "properties": {
                    "title": title.strip(),
                    "timezone": timezone.strip(),
                    "emails": [e.strip() for e in emails.split(',')]
                }
            })
        
        # 提取宠物
        pet_pattern = r"## 宠物\n- ([^\n]+)"
        pet_match = re.search(pet_pattern, content)
        if pet_match:
            pet_desc = pet_match.group(1)
            entities.append({
                "type": "pet",
                "name": "热带鱼",
                "properties": {
                    "description": pet_desc.strip(),
                    "feeding_times": ["09:00", "15:50"]
                }
            })
        
        return entities
    
    def extract_relationships(self, entities: List[Dict]) -> List[Dict]:
        """提取实体间的关系"""
        relationships = []
        
        # 建立服务器-域名关系
        servers = [e for e in entities if e["type"] == "server"]
        domains = [e for e in entities if e["type"] == "domain"]
        
        for server in servers:
            server_domain = server["properties"].get("domain")
            if server_domain:
                for domain in domains:
                    if domain["name"] == server_domain:
                        relationships.append({
                            "source": server["name"],
                            "target": domain["name"],
                            "type": "has_domain",
                            "properties": {"relation": "服务器拥有域名"}
                        })
        
        # 建立人物-邮箱关系
        people = [e for e in entities if e["type"] == "person"]
        emails = [e for e in entities if e["type"] == "email"]
        
        for person in people:
            person_emails = person["properties"].get("emails", [])
            for email in emails:
                if email["name"] in person_emails:
                    relationships.append({
                        "source": person["name"],
                        "target": email["name"],
                        "type": "owns_email",
                        "properties": {"relation": "拥有邮箱"}
                    })
        
        # 建立任务-宠物关系
        tasks = [e for e in entities if e["type"] == "task"]
        pets = [e for e in entities if e["type"] == "pet"]
        
        for task in tasks:
            task_desc = task["properties"].get("description", "")
            if "喂鱼" in task_desc:
                for pet in pets:
                    relationships.append({
                        "source": task["name"],
                        "target": pet["name"],
                        "type": "feeds",
                        "properties": {"relation": "喂食任务"}
                    })
        
        return relationships
    
    def extract_all(self) -> Dict:
        """提取所有实体和关系"""
        print("🔍 [Entity Extractor] 开始提取实体...")
        
        # 从不同来源提取
        entities_memory = self.extract_from_memory_md()
        entities_user = self.extract_from_user_md()
        
        # 合并实体（去重）
        all_entities = []
        seen_names = set()
        
        for entity in entities_memory + entities_user:
            if entity["name"] not in seen_names:
                all_entities.append(entity)
                seen_names.add(entity["name"])
        
        # 提取关系
        relationships = self.extract_relationships(all_entities)
        
        # 统计
        entity_counts = {}
        for entity in all_entities:
            entity_type = entity["type"]
            entity_counts[entity_type] = entity_counts.get(entity_type, 0) + 1
        
        print(f"  ✅ 提取到 {len(all_entities)} 个实体:")
        for entity_type, count in entity_counts.items():
            print(f"     - {entity_type}: {count}")
        
        print(f"  🔗 提取到 {len(relationships)} 个关系")
        
        return {
            "entities": all_entities,
            "relationships": relationships,
            "timestamp": datetime.now().isoformat(),
            "stats": {
                "total_entities": len(all_entities),
                "entity_types": entity_counts,
                "total_relationships": len(relationships)
            }
        }
    
    def save_to_knowledge_graph(self, extraction_result: Dict):
        """保存到知识图谱"""
        from knowledge_graph import KnowledgeGraph, Entity
        
        kg = KnowledgeGraph()
        
        # 添加实体
        for entity_data in extraction_result["entities"]:
            entity_id = f"{entity_data['type']}_{entity_data['name'].replace(' ', '_')}"
            
            # 检查是否已存在
            if entity_id not in kg.entities:
                entity = Entity(
                    id=entity_id,
                    type=entity_data["type"],
                    name=entity_data["name"]
                )
                entity.properties = entity_data.get("properties", {})
                kg.add_entity(entity)
        
        # 添加关系
        for rel_data in extraction_result["relationships"]:
            source_name = rel_data["source"]
            target_name = rel_data["target"]
            
            # 查找实体ID
            source_id = None
            target_id = None
            
            for entity_id, entity in kg.entities.items():
                if entity.name == source_name:
                    source_id = entity_id
                if entity.name == target_name:
                    target_id = entity_id
            
            if source_id and target_id:
                kg.add_relation(source_id, rel_data["type"], target_id)
        
        kg.save()
        print(f"  💾 已保存到知识图谱: {len(kg.entities)} 个实体")

def main():
    """主函数"""
    extractor = EntityExtractor()
    
    # 提取实体
    result = extractor.extract_all()
    
    # 保存到知识图谱
    extractor.save_to_knowledge_graph(result)
    
    # 输出结果
    print("\n" + "=" * 80)
    print("📊 实体提取结果")
    print("=" * 80)
    
    print(f"\n🏷️ 实体 ({result['stats']['total_entities']} 个):")
    for entity in result["entities"]:
        print(f"  - {entity['type']}: {entity['name']}")
        for key, value in entity.get("properties", {}).items():
            if isinstance(value, list):
                print(f"    {key}: {', '.join(value)}")
            else:
                print(f"    {key}: {value}")
    
    print(f"\n🔗 关系 ({result['stats']['total_relationships']} 个):")
    for rel in result["relationships"]:
        print(f"  - {rel['source']} → {rel['target']}: {rel['type']}")
    
    print("\n" + "=" * 80)

if __name__ == "__main__":
    main()
