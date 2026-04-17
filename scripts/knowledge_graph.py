#!/usr/bin/env python3
"""
Entity Knowledge Graph - 实体知识图谱

实现结构化认知：Entity / Relationship / Property
"""

import json
from typing import List, Dict, Optional
from pathlib import Path

ENTITIES_DIR = Path("/root/.openclaw/workspace/entities")
GRAPH_FILE = Path("/root/.openclaw/workspace/.knowledge_graph.json")

class Entity:
    def __init__(self, id: str, type: str, name: str = None):
        self.id = id
        self.type = type
        self.name = name or id
        self.properties: Dict = {}
        self.relations: List[Dict] = []
    
    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "type": self.type,
            "name": self.name,
            "properties": self.properties,
            "relations": self.relations
        }
    
    @classmethod
    def from_dict(cls, d: dict) -> 'Entity':
        e = cls(d["id"], d["type"], d.get("name"))
        e.properties = d.get("properties", {})
        e.relations = d.get("relations", [])
        return e
    
    def add_relation(self, relation_type: str, target: str, context: str = None):
        """添加关系"""
        relation = {
            "type": relation_type,
            "target": target
        }
        if context:
            relation["context"] = context
        # 避免重复
        if relation not in self.relations:
            self.relations.append(relation)
    
    def get_relations(self, relation_type: str = None) -> List[Dict]:
        """获取关系"""
        if relation_type:
            return [r for r in self.relations if r["type"] == relation_type]
        return self.relations
    
    def __repr__(self):
        return f"Entity({self.id}, {self.type})"

class KnowledgeGraph:
    """知识图谱"""
    
    RELATION_TYPES = {
        "uses": "使用某技术/工具",
        "replaced": "替换了某事物",
        "part_of": "属于某项目",
        "managed_by": "由某人管理",
        "located_at": "位于某地",
        "runs_on": "运行在某环境",
        "sends_to": "发送到某渠道",
        "scheduled_at": "定时于某时间",
        "member_of": "是某组织成员",
        "depends_on": "依赖某事物",
    }
    
    def __init__(self):
        self.entities: Dict[str, Entity] = {}
        self.load()
    
    def load(self):
        """加载知识图谱"""
        if GRAPH_FILE.exists():
            with open(GRAPH_FILE, 'r') as f:
                data = json.load(f)
                for eid, edata in data.get("entities", {}).items():
                    self.entities[eid] = Entity.from_dict(edata)
    
    def save(self):
        """保存知识图谱"""
        data = {
            "entities": {eid: e.to_dict() for eid, e in self.entities.items()}
        }
        with open(GRAPH_FILE, 'w') as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
    
    def add_entity(self, entity: Entity):
        """添加实体"""
        self.entities[entity.id] = entity
        self.save()
    
    def get_entity(self, id: str) -> Optional[Entity]:
        """获取实体"""
        return self.entities.get(id)
    
    def find_entities(self, type: str = None, query: str = None) -> List[Entity]:
        """搜索实体"""
        results = list(self.entities.values())
        if type:
            results = [e for e in results if e.type == type]
        if query:
            query = query.lower()
            results = [e for e in results 
                      if query in e.id.lower() or query in e.name.lower()]
        return results
    
    def query_relation(self, entity_id: str, relation_type: str) -> List[str]:
        """查询关系"""
        entity = self.entities.get(entity_id)
        if not entity:
            return []
        return [r["target"] for r in entity.get_relations(relation_type)]
    
    def add_relation(self, from_id: str, relation_type: str, to_id: str, context: str = None):
        """添加关系"""
        from_entity = self.entities.get(from_id)
        to_entity = self.entities.get(to_id)
        
        if not from_entity:
            from_entity = Entity(from_id, "unknown")
            self.entities[from_id] = from_entity
        if not to_entity:
            to_entity = Entity(to_id, "unknown")
            self.entities[to_id] = to_entity
        
        from_entity.add_relation(relation_type, to_id, context)
        
        # 双向关系
        if relation_type in ["replaced", "related"]:
            to_entity.add_relation(f"replaced_by", from_id, context)
        
        self.save()
    
    def print_graph(self):
        """打印知识图谱"""
        print("=" * 60)
        print("🕸️  Knowledge Graph - 知识图谱")
        print("=" * 60)
        
        # 按类型分组
        by_type = {}
        for entity in self.entities.values():
            if entity.type not in by_type:
                by_type[entity.type] = []
            by_type[entity.type].append(entity)
        
        for etype, entities in by_type.items():
            print(f"\n📦 {etype} ({len(entities)}):")
            for e in entities:
                print(f"  • {e.id}")
                for r in e.relations[:3]:
                    print(f"    └── {r['type']}: {r['target']}")
                if len(e.relations) > 3:
                    print(f"    └── ...还有 {len(e.relations) - 3} 条")
        
        print("\n" + "=" * 60)

def main():
    import argparse
    parser = argparse.ArgumentParser(description='Knowledge Graph - 实体知识图谱')
    parser.add_argument('--show', '-s', action='store_true', help='显示知识图谱')
    parser.add_argument('--add', '-a', nargs=3, metavar=('FROM', 'RELATION', 'TO'),
                        help='添加关系: --add stylefitgw uses postgresql')
    parser.add_argument('--query', '-q', nargs=2, metavar=('ENTITY', 'RELATION'),
                        help='查询关系: --query stylefitgw uses')
    parser.add_argument('--find', '-f', metavar='TYPE', help='查找实体类型: --find project')
    args = parser.parse_args()
    
    kg = KnowledgeGraph()
    
    if args.show or (not args.add and not args.query and not args.find):
        kg.print_graph()
    
    elif args.add:
        from_id, relation, to_id = args.add
        kg.add_relation(from_id, relation, to_id)
        print(f"✅ 添加关系: {from_id} --{relation}--> {to_id}")
    
    elif args.query:
        entity_id, relation = args.query
        results = kg.query_relation(entity_id, relation)
        if results:
            print(f"{entity_id} --{relation}--> {', '.join(results)}")
        else:
            print(f"无结果")
    
    elif args.find:
        entities = kg.find_entities(type=args.find)
        if entities:
            print(f"找到 {len(entities)} 个 {args.find}:")
            for e in entities:
                print(f"  • {e.id}: {e.name}")
        else:
            print(f"未找到")

if __name__ == '__main__':
    main()
