#!/usr/bin/env python3
"""
Entity Knowledge Graph - 实体知识图谱

PR④ 落地实现：三层记忆联动
- 感知层：检测器发现风险事件 → 更新图谱
- 认知层：知识图谱 → 为 context_builder 提供实体关系上下文
- 记忆层：memory/ 日记文件 → 自动抽取实体填充图谱

核心改进：
1. 新增 get_relationships() 方法（修复 context_builder 兼容）
2. 新增 populate_from_memory() 从 memory/ 自动抽取实体
3. 新增 link_event_to_entity() 事件驱动实体更新
4. 新增 get_relevant_entities() 按关键词返回相关实体
"""

import json
import os
import re
from typing import List, Dict, Optional, Set
from pathlib import Path
from datetime import datetime

ENTITIES_DIR = Path("/root/.openclaw/workspace/entities")
GRAPH_FILE = Path("/root/.openclaw/workspace/.knowledge_graph.json")


class Entity:
    """实体"""
    def __init__(self, id: str, type: str, name: str = None):
        self.id = id
        self.type = type
        self.name = name or id
        self.properties: Dict = {}
        self.relations: List[Dict] = []
        self.first_seen: str = datetime.now().strftime("%Y-%m-%d")
        self.last_updated: str = self.first_seen
        self.tags: Set[str] = set()
        self.event_count: int = 0

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "type": self.type,
            "name": self.name,
            "properties": self.properties,
            "relations": self.relations,
            "first_seen": self.first_seen,
            "last_updated": self.last_updated,
            "tags": list(self.tags),
            "event_count": self.event_count,
        }

    @classmethod
    def from_dict(cls, d: dict) -> 'Entity':
        e = cls(d["id"], d["type"], d.get("name"))
        e.properties = d.get("properties", {})
        e.relations = d.get("relations", [])
        e.first_seen = d.get("first_seen", datetime.now().strftime("%Y-%m-%d"))
        e.last_updated = d.get("last_updated", e.first_seen)
        e.tags = set(d.get("tags", []))
        e.event_count = d.get("event_count", 0)
        return e

    def add_relation(self, relation_type: str, target: str, context: str = None):
        relation = {"type": relation_type, "target": target}
        if context:
            relation["context"] = context
        if relation not in self.relations:
            self.relations.append(relation)

    def get_relations(self, relation_type: str = None) -> List[Dict]:
        if relation_type:
            return [r for r in self.relations if r["type"] == relation_type]
        return self.relations

    def touch(self):
        """更新 last_updated 和 event_count"""
        self.last_updated = datetime.now().strftime("%Y-%m-%d")
        self.event_count += 1

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
        "triggers": "触发某操作",
        "monitors": "监控某目标",
        "blocked_by": "被某事件阻塞",
        "approved_by": "经某审批通过",
    }

    # 实体类型定义
    ENTITY_TYPES = {
        "project": "项目",
        "person": "人物",
        "location": "地点",
        "system": "系统/服务",
        "schedule": "定时任务",
        "file": "文件",
        "script": "脚本",
        "skill": "技能模块",
        "channel": "通信渠道",
        "rule": "安全规则",
        "event": "事件",
        "vulnerability": "漏洞/风险",
    }

    def __init__(self):
        self.entities: Dict[str, Entity] = {}
        self.load()

    def load(self):
        """加载知识图谱"""
        if GRAPH_FILE.exists():
            try:
                with open(GRAPH_FILE, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    for eid, edata in data.get("entities", {}).items():
                        self.entities[eid] = Entity.from_dict(edata)
            except (json.JSONDecodeError, KeyError):
                self.entities = {}

    def save(self):
        """保存知识图谱"""
        data = {
            "entities": {eid: e.to_dict() for eid, e in self.entities.items()},
            "meta": {
                "updated_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                "total_entities": len(self.entities),
            }
        }
        with open(GRAPH_FILE, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=2, ensure_ascii=False)

    def add_entity(self, entity: Entity):
        """添加实体"""
        self.entities[entity.id] = entity
        self.save()

    def get_or_create(self, entity_id: str, entity_type: str, name: str = None) -> Entity:
        """获取或创建实体"""
        if entity_id in self.entities:
            return self.entities[entity_id]
        entity = Entity(entity_id, entity_type, name or entity_id)
        self.entities[entity_id] = entity
        return entity

    def get_entity(self, id: str) -> Optional[Entity]:
        return self.entities.get(id)

    def find_entities(self, type: str = None, query: str = None) -> List[Entity]:
        results = list(self.entities.values())
        if type:
            results = [e for e in results if e.type == type]
        if query:
            query = query.lower()
            results = [e for e in results
                      if query in e.id.lower() or query in e.name.lower()]
        return results

    def query_relation(self, entity_id: str, relation_type: str) -> List[str]:
        entity = self.entities.get(entity_id)
        if not entity:
            return []
        return [r["target"] for r in entity.get_relations(relation_type)]

    def get_relationships(self, entity_id: str) -> List[Dict]:
        """获取实体的所有关系（修复 context_builder 兼容性）"""
        entity = self.entities.get(entity_id)
        if not entity:
            return []
        return entity.relations

    def get_relevant_entities(self, keywords: List[str], limit: int = 5) -> List[Entity]:
        """根据关键词返回相关实体"""
        matched = []
        for entity in self.entities.values():
            score = 0
            name_lower = entity.name.lower()
            id_lower = entity.id.lower()
            type_lower = entity.type.lower()
            for kw in keywords:
                kw_lower = kw.lower()
                if len(kw_lower) > 2:
                    if kw_lower in name_lower:
                        score += 3
                    if kw_lower in id_lower:
                        score += 2
                    if kw_lower in type_lower:
                        score += 1
                    for tag in entity.tags:
                        if kw_lower in tag.lower():
                            score += 2
            if score > 0:
                matched.append((entity, score))
        matched.sort(key=lambda x: x[1], reverse=True)
        return [e for e, _ in matched[:limit]]

    def add_relation(self, from_id: str, relation_type: str, to_id: str, context: str = None):
        from_entity = self.entities.get(from_id)
        to_entity = self.entities.get(to_id)

        if not from_entity:
            from_entity = Entity(from_id, "unknown")
            self.entities[from_id] = from_entity
        if not to_entity:
            to_entity = Entity(to_id, "unknown")
            self.entities[to_id] = to_entity

        from_entity.add_relation(relation_type, to_id, context)
        from_entity.touch()

        if relation_type in ["replaced", "related"]:
            to_entity.add_relation(f"replaced_by", from_id, context)
            to_entity.touch()

        self.save()

    def link_event_to_entity(self, event: Dict, entity_id: str, relation: str = "triggers"):
        """将事件关联到已有实体（检测器联动）"""
        entity = self.get_or_create(entity_id, "system")
        entity.touch()

        # 记录事件
        event_record = {
            "type": event.get("event", "unknown"),
            "path": event.get("path", ""),
            "time": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        }
        if "level" in event:
            event_record["level"] = event["level"]

        # 添加事件标签
        event_type = event.get("event", "")
        entity.tags.add(f"event:{event_type}")

        if "level" in event:
            entity.tags.add(f"risk:{event['level']}")

        entity.properties["last_event"] = event_record

        # 关联到实体
        entity.add_relation(relation, event.get("path", ""), f"event:{event.get('event')}")
        self.save()
        return entity

    def populate_from_memory(self, memory_dir: str = None) -> int:
        """
        从 memory/ 日记文件自动抽取实体填充图谱
        PR④ 核心：记忆层 → 认知层

        返回：新增实体数量
        """
        memory_dir = memory_dir or "/root/.openclaw/workspace/memory"
        mem_path = Path(memory_dir)
        if not mem_path.exists():
            return 0

        new_count = 0

        # 模式：识别脚本路径
        SCRIPT_PATTERN = re.compile(r'(scripts/[\w_\-\.]+\.py|clawkeeper/[\w_\-\.]+\.py)')
        # 模式：识别时间戳
        TIME_PATTERN = re.compile(r'\d{4}-\d{2}-\d{2}|\d{2}:\d{2}')
        # 模式：识别项目名（以字母开头的标识符）
        PROJECT_PATTERN = re.compile(r'\b([A-Za-z][\w]{2,20})\b')

        for md_file in mem_path.glob("*.md"):
            try:
                content = md_file.read_text(encoding='utf-8', errors='ignore')
            except Exception:
                continue

            # 抽取脚本实体
            for match in SCRIPT_PATTERN.finditer(content):
                script_path = match.group(1)
                script_name = Path(script_path).stem
                entity = self.get_or_create(script_name, "script", script_path)
                entity.properties["path"] = script_path
                entity.tags.add("from_memory")
                if "memory" not in entity.tags:
                    new_count += 1

            # 按行分析，识别实体类型
            lines = content.split('\n')
            for line in lines:
                if '# ' in line:
                    # Markdown 标题作为实体名称
                    title = line.replace('# ', '').strip()
                    if 2 < len(title) < 50 and not title.startswith('TODO'):
                        entity = self.get_or_create(title.replace(' ', '_'), "event")
                        entity.name = title
                        entity.tags.add("from_memory:heading")

            # 识别关键模式
            patterns = {
                "schedule": re.compile(r'(喂鱼提醒|记忆同步|定时任务|cron)'),
                "feishu": re.compile(r'(飞书|Feishu|webhook|群ID)'),
                "github": re.compile(r'(GitHub|PAT|git push|仓库)'),
                "security": re.compile(r'(CRITICAL|HIGH|拦截|审批|安全)'),
                "memory": re.compile(r'(memory|MEMORY|记忆)'),
            }

            for ptype, pattern in patterns.items():
                if pattern.search(content):
                    entity = self.get_or_create(ptype, "system" if ptype in ["schedule", "feishu", "github"] else "rule")
                    entity.tags.add(ptype)
                    entity.tags.add("from_memory")

            # 识别文件路径作为实体
            for fp_match in re.finditer(r'/([\w\-\.]+/[\w\-\.]+\.(py|sh|yaml|json|md))', content):
                fpath = fp_match.group(1)
                fname = Path(fpath).stem
                entity = self.get_or_create(fname, "file")
                entity.properties["path"] = fpath
                entity.tags.add("from_memory:path")

        self.save()
        return new_count

    def build_entity_context(self, user_input: str) -> str:
        """根据用户输入构建实体上下文（用于 context_builder）"""
        keywords = [w for w in user_input.split() if len(w) > 2]
        entities = self.get_relevant_entities(keywords, limit=5)

        if not entities:
            return ""

        parts = ["## 🕸️ 知识图谱上下文"]
        for e in entities:
            parts.append(f"**{e.name}** ({e.type})")
            if e.tags:
                parts.append(f"  标签: {', '.join(list(e.tags)[:5])}")
            if e.relations:
                parts.append(f"  关系:")
                for r in e.relations[:3]:
                    parts.append(f"    - {r['type']}: {r['target']}")
            if e.event_count > 0:
                parts.append(f"  触发次数: {e.event_count}")
            parts.append("")

        return "\n".join(parts)

    def print_graph(self):
        """打印知识图谱"""
        print("=" * 60)
        print("🕸️  Knowledge Graph - 知识图谱")
        print("=" * 60)

        by_type = {}
        for entity in self.entities.values():
            if entity.type not in by_type:
                by_type[entity.type] = []
            by_type[entity.type].append(entity)

        for etype, entities in by_type.items():
            print(f"\n📦 {etype} ({len(entities)}):")
            for e in entities:
                print(f"  • {e.id} [{e.name}] (事件:{e.event_count})")
                for r in e.relations[:3]:
                    print(f"    └── {r['type']}: {r['target']}")
                if len(e.relations) > 3:
                    print(f"    └── ...还有 {len(e.relations) - 3} 条")

        print(f"\n总计: {len(self.entities)} 个实体")
        print("=" * 60)


def main():
    import argparse
    parser = argparse.ArgumentParser(description='Knowledge Graph')
    parser.add_argument('--show', '-s', action='store_true', help='显示知识图谱')
    parser.add_argument('--populate', '-p', action='store_true', help='从 memory/ 填充实体')
    parser.add_argument('--add', '-a', nargs=3, metavar=('FROM', 'RELATION', 'TO'),
                        help='添加关系')
    parser.add_argument('--query', '-q', nargs=2, metavar=('ENTITY', 'RELATION'),
                        help='查询关系')
    parser.add_argument('--context', '-c', metavar='TEXT', help='根据输入构建实体上下文')
    args = parser.parse_args()

    kg = KnowledgeGraph()

    if args.show or (not args.add and not args.query and not args.populate and not args.context):
        kg.print_graph()

    elif args.populate:
        n = kg.populate_from_memory()
        print(f"✅ 从 memory/ 填充完成，新增 {n} 个实体")

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
            print("无结果")

    elif args.context:
        ctx = kg.build_entity_context(args.context)
        if ctx:
            print(ctx)
        else:
            print("无相关实体")


if __name__ == '__main__':
    main()
