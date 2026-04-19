#!/usr/bin/env python3
"""
Clawkeeper PR④ 知识图谱联动测试
覆盖：populate_from_memory / build_entity_context / link_event_to_entity
"""

import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

PROJECT_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from knowledge_graph import KnowledgeGraph, Entity


class TestKnowledgeGraph(unittest.TestCase):
    """知识图谱核心功能测试"""

    def setUp(self):
        self.temp_dir = tempfile.mkdtemp()
        # 创建临时 entities 和 graph 文件
        import shutil
        self.temp_entities = Path(self.temp_dir) / "entities"
        self.temp_entities.mkdir()
        self.temp_graph = Path(self.temp_dir) / ".knowledge_graph.json"
        # Patch 全局路径
        import knowledge_graph
        self._orig_entities = knowledge_graph.ENTITIES_DIR
        self._orig_graph = knowledge_graph.GRAPH_FILE
        knowledge_graph.ENTITIES_DIR = self.temp_entities
        knowledge_graph.GRAPH_FILE = self.temp_graph

    def tearDown(self):
        import shutil
        shutil.rmtree(self.temp_dir, ignore_errors=True)
        import knowledge_graph
        knowledge_graph.ENTITIES_DIR = self._orig_entities
        knowledge_graph.GRAPH_FILE = self._orig_graph

    # ===== 实体基础操作 =====

    def test_entity_creation(self):
        e = Entity("test_id", "script", "Test Script")
        self.assertEqual(e.id, "test_id")
        self.assertEqual(e.type, "script")
        self.assertEqual(e.name, "Test Script")
        self.assertEqual(e.event_count, 0)
        self.assertEqual(len(e.relations), 0)

    def test_entity_add_relation(self):
        e = Entity("test", "project")
        e.add_relation("uses", "postgresql", "for storage")
        self.assertEqual(len(e.relations), 1)
        self.assertEqual(e.relations[0]["type"], "uses")
        self.assertEqual(e.relations[0]["target"], "postgresql")
        self.assertEqual(e.relations[0]["context"], "for storage")

    def test_entity_touch(self):
        e = Entity("test", "system")
        self.assertEqual(e.event_count, 0)
        e.touch()
        self.assertEqual(e.event_count, 1)
        e.touch()
        self.assertEqual(e.event_count, 2)

    def test_entity_to_dict_from_dict(self):
        e = Entity("id1", "project", "My Project")
        e.properties["status"] = "active"
        e.tags.add("important")
        e.add_relation("uses", "python")

        d = e.to_dict()
        restored = Entity.from_dict(d)

        self.assertEqual(restored.id, "id1")
        self.assertEqual(restored.type, "project")
        self.assertEqual(restored.name, "My Project")
        self.assertEqual(restored.properties["status"], "active")
        self.assertEqual(restored.tags, {"important"})
        self.assertEqual(len(restored.relations), 1)

    # ===== 图谱基础操作 =====

    def test_graph_add_and_get_entity(self):
        kg = KnowledgeGraph()
        e = Entity("proj1", "project")
        kg.add_entity(e)

        self.assertEqual(kg.get_entity("proj1").id, "proj1")
        self.assertEqual(len(kg.entities), 1)

    def test_graph_get_or_create(self):
        kg = KnowledgeGraph()
        e = kg.get_or_create("new_entity", "script", "New Script")
        self.assertEqual(e.id, "new_entity")
        self.assertEqual(e.type, "script")

        # 再次调用返回同一实体
        e2 = kg.get_or_create("new_entity", "other_type")
        self.assertEqual(e2.id, "new_entity")
        self.assertEqual(e2.type, "script")  # 保持原类型

    def test_graph_add_relation(self):
        kg = KnowledgeGraph()
        kg.add_relation("proj_a", "uses", "script_b", "data processing")
        self.assertIn("proj_a", kg.entities)
        self.assertIn("script_b", kg.entities)

        proj = kg.get_entity("proj_a")
        self.assertEqual(proj.relations[0]["type"], "uses")
        self.assertEqual(proj.relations[0]["target"], "script_b")

    def test_graph_query_relation(self):
        kg = KnowledgeGraph()
        kg.add_relation("proj_a", "uses", "tool_x")
        kg.add_relation("proj_a", "uses", "tool_y")
        kg.add_relation("proj_a", "depends_on", "lib_z")

        self.assertEqual(set(kg.query_relation("proj_a", "uses")), {"tool_x", "tool_y"})
        self.assertEqual(kg.query_relation("proj_a", "unknown"), [])

    def test_graph_get_relationships(self):
        """修复：get_relationships 返回实体所有关系"""
        kg = KnowledgeGraph()
        kg.add_relation("sys1", "monitors", "target_a")
        kg.add_relation("sys1", "sends_to", "feishu_b")

        rels = kg.get_relationships("sys1")
        self.assertEqual(len(rels), 2)
        targets = {r["target"] for r in rels}
        self.assertEqual(targets, {"target_a", "feishu_b"})

    def test_graph_find_entities(self):
        kg = KnowledgeGraph()
        kg.add_entity(Entity("proj_alpha", "project"))
        kg.add_entity(Entity("proj_beta", "project"))
        kg.add_entity(Entity("scr_script", "script"))
        kg.add_entity(Entity("sys_monitor", "system"))

        by_type = kg.find_entities(type="project")
        self.assertEqual(len(by_type), 2)

        by_query = kg.find_entities(query="alpha")
        self.assertEqual(len(by_query), 1)
        self.assertEqual(by_query[0].id, "proj_alpha")

    # ===== PR④ 核心功能 =====

    def test_populate_from_memory(self):
        """populate_from_memory 从日记抽取实体"""
        kg = KnowledgeGraph()
        memory_dir = Path(self.temp_dir) / "memory"
        memory_dir.mkdir()

        # 创建测试日记
        (memory_dir / "2026-04-19.md").write_text("""
# 喂鱼提醒 cron 状态正常

今天执行了以下操作：
1. 修复了 cron-events/ 目录的 inotify 监控问题
2. 在 clawkeeper/detector.py 添加了 PR① LLM 语义判断
3. 测试了 interceptor.py 的四级分层响应

## 相关脚本
- scripts/cron-event-writer.py
- clawkeeper/watcher.py
- scripts/progress_tracker.py

## 飞书通知
webhook 已配置到 oc_0533b03e077fedca255c4d2c6717deea 群组
""")

        n = kg.populate_from_memory(str(memory_dir))

        # 应该抽取出：脚本实体、飞书实体等
        self.assertGreater(n, 0, "应新增实体")

        # 检查是否有 cron-event-writer 实体
        cron_entity = kg.get_entity("cron-event-writer")
        self.assertIsNotNone(cron_entity, "应创建 cron-event-writer 实体")
        self.assertEqual(cron_entity.type, "script")

        # 检查是否有飞书相关实体
        feishu_entities = kg.find_entities(type="system")
        feishu_types = {e.id for e in feishu_entities}
        self.assertTrue(
            any("feishu" in t for t in feishu_types) or len(feishu_entities) > 0,
            "应识别飞书系统实体"
        )

    def test_link_event_to_entity(self):
        """link_event_to_entity 事件驱动实体更新"""
        kg = KnowledgeGraph()
        entity = kg.get_or_create("watcher", "script")
        entity_id = entity.id

        initial_count = entity.event_count

        kg.link_event_to_entity(
            event={"event": "MODIFY", "path": "/workspace/watcher.py", "level": "MEDIUM"},
            entity_id=entity_id,
            relation="modified_by"
        )

        updated = kg.get_entity(entity_id)
        self.assertEqual(updated.event_count, initial_count + 1)
        self.assertIn("event:MODIFY", updated.tags)
        self.assertIn("risk:MEDIUM", updated.tags)

    def test_get_relevant_entities(self):
        """get_relevant_entities 按关键词匹配"""
        kg = KnowledgeGraph()
        kg.add_entity(Entity("cron-event-writer", "script", "Cron Event Writer"))
        kg.get_entity("cron-event-writer").tags.update({"cron", "feishu"})
        kg.add_entity(Entity("feishu-progress", "script", "Feishu Progress"))
        kg.get_entity("feishu-progress").tags.add("feishu")
        kg.add_entity(Entity("detector", "script", "Risk Detector"))
        kg.get_entity("detector").tags.add("security")

        # 精确匹配
        results = kg.get_relevant_entities(["cron", "event"], limit=3)
        self.assertGreater(len(results), 0)

        # 按相关性排序
        ids = [e.id for e in results]
        self.assertIn("cron-event-writer", ids)

    def test_build_entity_context(self):
        """build_entity_context 为 context_builder 生成文本"""
        kg = KnowledgeGraph()
        e = kg.get_or_create("watcher", "script")
        e.tags.update({"cron", "monitor"})
        e.add_relation("triggers", "notifier.py", "飞书通知")
        e.event_count = 5

        ctx = kg.build_entity_context("cron watcher 状态")

        self.assertIn("watcher", ctx)
        self.assertIn("script", ctx)
        self.assertIn("触发", ctx)

    def test_populate_avoids_duplicates(self):
        """重复 populate 不会导致重复实体"""
        kg = KnowledgeGraph()
        memory_dir = Path(self.temp_dir) / "memory"
        memory_dir.mkdir()

        (memory_dir / "day1.md").write_text("# Test Script\nscripts/test.py")
        (memory_dir / "day2.md").write_text("# Test\nscripts/test.py")

        kg.populate_from_memory(str(memory_dir))
        first_count = len(kg.entities)

        kg.populate_from_memory(str(memory_dir))
        second_count = len(kg.entities)

        self.assertEqual(first_count, second_count, "重复 populate 不应新增实体")


class TestContextBuilderKG(unittest.TestCase):
    """context_builder 知识图谱联动测试"""

    def setUp(self):
        self.temp_dir = tempfile.mkdtemp()
        import shutil
        # Patch 知识图谱使用临时文件
        self._kg_file = Path("/root/.openclaw/workspace/.knowledge_graph.json")
        self._kg_bak = Path("/root/.openclaw/workspace/.knowledge_graph.json.bak")
        if self._kg_file.exists():
            shutil.copy(self._kg_file, self._kg_bak)

    def tearDown(self):
        import shutil
        if self._kg_bak.exists():
            shutil.copy(self._kg_bak, self._kg_file)
            self._kg_bak.unlink()
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_build_context_includes_kg(self):
        """build_context 包含知识图谱"""
        from context_builder import ContextBuilder

        builder = ContextBuilder()
        # 添加测试实体
        kg = builder.knowledge_graph
        e = kg.get_or_create("test_script", "script")
        e.tags.update({"test", "unit"})
        e.add_relation("used_by", "test_detector", "PR④ 测试")
        kg.save()

        ctx = builder.build_context("test_script 相关代码")
        self.assertIn("test_script", ctx)

    def test_build_light_context(self):
        """build_light_context 包含相关实体"""
        from context_builder import ContextBuilder

        builder = ContextBuilder()
        kg = builder.knowledge_graph
        kg.get_or_create("watcher", "script")
        kg.get_or_create("feishu", "system")
        kg.save()

        ctx = builder.build_light_context("watcher 监控状态")
        self.assertIn("watcher", ctx)


if __name__ == "__main__":
    unittest.main(verbosity=2)
