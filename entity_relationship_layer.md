# Entity Relationship Layer - 实体关系层

> 从"聪明"到"真正智能"的跨越

## 问题

当前系统是**平面文本**：
```
MEMORY.md: "stylefitgw使用PostgreSQL数据库"
MEMORY.md: "MySQL已被替换为PostgreSQL"
MEMORY.md: "stylefitgw是印尼染发膏项目"
```

问题：
- 模型不知道这些是**同一个项目**
- 无法推理 `MySQL → PostgreSQL` 的替换关系
- 无法回答 "stylefitgw 用什么数据库？"

## 解决方案：知识图谱

### 实体 (Entity)
```yaml
Entity:
  id: "stylefitgw"
  type: "project"
  name: "印尼染发膏商城"
  properties:
    platform: "Shopee/TikTok"
    region: "Indonesia"
    status: "active"
```

### 关系 (Relationship)
```yaml
Relationship:
  from: "stylefitgw"
  type: "uses"
  to: "postgresql"
  
Relationship:
  from: "postgresql"
  type: "replaced"
  to: "mysql"
  context: "在 stylefitgw 项目中"
```

### 属性 (Property)
```yaml
Property:
  entity: "stylefitgw"
  key: "domain"
  value: "[已脱敏]"
```

## 实体类型

| 类型 | 说明 | 示例 |
|------|------|------|
| project | 项目 | stylefitgw, hegr |
| server | 服务器 | mysstylefitgw,印尼地坪漆 |
| database | 数据库 | PostgreSQL, MySQL |
| person | 人物 | 坤哥 |
| brand | 品牌 | StyleFit |
| platform | 平台 | Shopee, TikTok Shop |
| tool | 工具 | OpenClaw, Gmail |
| behavior | 行为模式 | 每天日报, 喂鱼 |

## 关系类型

| 关系 | 说明 | 示例 |
|------|------|------|
| uses | 使用 | stylefitgw uses postgresql |
| replaced | 替换 | postgresql replaced mysql |
| part_of | 属于 | nginx part_of stylefitgw |
| managed_by | 管理 | stylefitgw managed_by 坤哥 |
| located_at | 位于 | 服务器 located_at AWS |
| runs_on | 运行在 | 网站 runs_on nginx |
| sends_to | 发送到 | 日报 sends_to 电商群 |
| scheduled_at | 定时于 | 日报 scheduled_at 9:00 |

## 查询示例

```python
# 简单查询
stylefitgw.uses  # → [postgresql]

# 关系推理
postgresql.replaced_by  # → [mysql]
mysql.in_stylefitgw  # → True

# 路径查询
坤哥 --manages--> stylefitgw --uses--> postgresql
```

## 文件结构

```
entities/
├── index.md           # 实体索引
├── projects/          # 项目实体
│   └── stylefitgw.md
├── servers/          # 服务器实体
│   └── mysstylefitgw.md
├── databases/        # 数据库实体
│   └── postgresql.md
└── relationships.md  # 关系列表
```

## 实现

```python
class Entity:
    def __init__(self, id, type):
        self.id = id
        self.type = type
        self.properties = {}
        self.relations = []
    
    def relate_to(self, target, relation):
        self.relations.append({
            "type": relation,
            "target": target,
            "bidirectional": relation in ["replaced", "related"]
        })

class KnowledgeGraph:
    def __init__(self):
        self.entities = {}
    
    def add_entity(self, entity):
        self.entities[entity.id] = entity
    
    def query(self, entity_id, relation):
        entity = self.entities.get(entity_id)
        return [r for r in entity.relations if r["type"] == relation]
```

---

_设计: 2026-04-16_
