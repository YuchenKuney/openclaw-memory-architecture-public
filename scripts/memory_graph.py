#!/usr/bin/env python3
"""
memory_graph.py - 结构化记忆系统

借鉴 coolmanns/openclaw-memory-architecture 的 facts.db 设计

功能：
- facts.db: 实体-键-值 结构化存储
- FTS5: 全文搜索
- 衰减模型: decay_score 每日衰减
- 别名: 昵称解析
- 关系图: subject-predicate-object 三元组

用法：
    python3 scripts/memory_graph.py init          # 初始化数据库
    python3 scripts/memory_graph.py add "坤哥" "时区" "Europe/Berlin" people
    python3 scripts/memory_graph.py get "坤哥" "时区"
    python3 scripts/memory_graph.py search "时区"
    python3 scripts/memory_graph.py decay         # 运行衰减
    python3 scripts/memory_graph.py stats        # 查看统计
"""

import os
import sys
import sqlite3
import argparse
from datetime import datetime, timezone
from pathlib import Path

WORKSPACE = Path("/root/.openclaw/workspace")
DB_PATH = WORKSPACE / "memory" / "facts.db"
SCHEMA_PATH = WORKSPACE / "schema" / "facts.sql"

# 衰减参数
DECAY_RATE = 0.95       # 每日衰减率 (5% decay/day)
FLOOR = 0.01             # 最低分数
COLD_THRESHOLD = 0.10   # 冷事实阈值

# 永久类别（不过期）
PERMANENT_CATEGORIES = {"person", "family", "friend", "decision", "preference"}


def get_db():
    """获取数据库连接"""
    os.makedirs(DB_PATH.parent, exist_ok=True)
    db = sqlite3.connect(str(DB_PATH))
    db.row_factory = sqlite3.Row
    db.execute("PRAGMA journal_mode=WAL")
    return db


def init_db():
    """初始化 facts.db"""
    if not SCHEMA_PATH.exists():
        print(f"❌ Schema文件不存在: {SCHEMA_PATH}")
        return False

    os.makedirs(DB_PATH.parent, exist_ok=True)
    db = get_db()

    with open(SCHEMA_PATH) as f:
        db.executescript(f.read())

    count = db.execute("SELECT COUNT(*) FROM facts").fetchone()[0]
    print(f"✅ facts.db 初始化完成 ({count} existing facts)")
    db.close()
    return True


def add_fact(entity: str, key: str, value: str, category: str, 
             source: str = "manual", permanent: bool = None):
    """添加事实"""
    db = get_db()

    # 检查是否已存在
    existing = db.execute(
        "SELECT id FROM facts WHERE entity=? AND key=?",
        (entity, key)
    ).fetchone()

    if existing:
        # 更新
        db.execute(
            "UPDATE facts SET value=?, source=?, last_accessed=datetime('now'), access_count=access_count+1 WHERE id=?",
            (value, source, existing[0])
        )
        print(f"🔄 更新: {entity}.{key} = {value}")
    else:
        # 自动判断是否永久
        if permanent is None:
            permanent = category in PERMANENT_CATEGORIES

        db.execute(
            """INSERT INTO facts (entity, key, value, category, source, permanent, decay_score)
               VALUES (?, ?, ?, ?, ?, ?, ?)""",
            (entity, key, value, category, source, 1 if permanent else 0, 1.0)
        )
        print(f"✅ 添加: {entity}.{key} = {value} ({'permanent' if permanent else 'decaying'})")

    # 记录changelog
    db.execute(
        """INSERT INTO facts_changelog (entity, key, operation, new_value, source)
           VALUES (?, ?, 'upsert', ?, ?)""",
        (entity, key, value, source)
    )

    db.commit()
    db.close()


def get_fact(entity: str, key: str = None):
    """获取事实"""
    db = get_db()

    if key:
        # 精确查询
        row = db.execute(
            "SELECT * FROM facts WHERE entity=? AND key=?",
            (entity, key)
        ).fetchone()

        if row:
            # 更新访问时间和次数
            db.execute(
                "UPDATE facts SET last_accessed=datetime('now'), access_count=access_count+1 WHERE id=?",
                (row["id"],)
            )
            db.commit()
            db.close()
            return dict(row)
        else:
            db.close()
            return None
    else:
        # 获取该entity所有事实
        rows = db.execute(
            "SELECT * FROM facts WHERE entity=? ORDER BY key",
            (entity,)
        ).fetchall()

        # 更新访问时间
        for row in rows:
            db.execute(
                "UPDATE facts SET last_accessed=datetime('now'), access_count=access_count+1 WHERE id=?",
                (row["id"],)
            )
        db.commit()
        db.close()
        return [dict(r) for r in rows]


def search_facts(query: str, category: str = None, limit: int = 20):
    """全文搜索事实"""
    db = get_db()

    if category:
        rows = db.execute("""
            SELECT f.*, facts_fts.rank
            FROM facts_fts
            JOIN facts f ON facts_fts.rowid = f.id
            WHERE facts_fts MATCH ? AND f.category = ?
            ORDER BY rank
            LIMIT ?
        """, (query, category, limit)).fetchall()
    else:
        rows = db.execute("""
            SELECT f.*, facts_fts.rank
            FROM facts_fts
            JOIN facts f ON facts_fts.rowid = f.id
            WHERE facts_fts MATCH ?
            ORDER BY rank
            LIMIT ?
        """, (query, limit)).fetchall()

    db.close()
    return [dict(r) for r in rows]


def delete_fact(entity: str, key: str):
    """删除事实"""
    db = get_db()

    # 先获取旧值
    row = db.execute(
        "SELECT * FROM facts WHERE entity=? AND key=?",
        (entity, key)
    ).fetchone()

    if row:
        db.execute("DELETE FROM facts WHERE entity=? AND key=?", (entity, key))
        db.execute(
            """INSERT INTO facts_changelog (entity, key, operation, old_value)
               VALUES (?, ?, 'delete', ?)""",
            (entity, key, row["value"])
        )
        db.commit()
        print(f"🗑️ 删除: {entity}.{key}")
    else:
        print(f"⚠️ 未找到: {entity}.{key}")

    db.close()


def run_decay():
    """运行每日衰减"""
    if not DB_PATH.exists():
        print(f"❌ facts.db 不存在")
        return

    db = get_db()

    # 确保有decay_score列
    cols = [c[1] for c in db.execute("PRAGMA table_info(facts)").fetchall()]
    if "decay_score" not in cols:
        db.execute("ALTER TABLE facts ADD COLUMN decay_score REAL DEFAULT 1.0")
        db.execute("ALTER TABLE facts ADD COLUMN last_accessed TEXT")
        print("  [init] 添加 decay_score 和 last_accessed 列")

    # 初始化 NULL 分数
    db.execute("""
        UPDATE facts 
        SET decay_score = 1.0 
        WHERE decay_score IS NULL AND (permanent = 0 OR permanent IS NULL)
    """)

    # 应用衰减
    db.execute(f"""
        UPDATE facts
        SET decay_score = MAX({FLOOR}, decay_score * {DECAY_RATE})
        WHERE permanent = 0 OR permanent IS NULL
    """)
    db.commit()

    # 统计
    stats = get_stats(db)
    db.close()

    now = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    print(f"📉 衰减完成 @ {now}")
    print(f"  总事实: {stats['total']}")
    print(f"  永久: {stats['permanent']}")
    print(f"  热(≥0.90): {stats['hot']}")
    print(f"  冷(<{COLD_THRESHOLD}): {stats['cold']}")
    print(f"  平均分: {stats['avg_score']:.3f}")


def get_stats(db=None):
    """获取统计"""
    if db is None:
        db = get_db()

    total = db.execute("SELECT COUNT(*) FROM facts").fetchone()[0]
    permanent = db.execute("SELECT COUNT(*) FROM facts WHERE permanent = 1").fetchone()[0]
    hot = db.execute("SELECT COUNT(*) FROM facts WHERE permanent = 0 AND decay_score >= 0.90").fetchone()[0]
    cold = db.execute(f"SELECT COUNT(*) FROM facts WHERE permanent = 0 AND decay_score < {COLD_THRESHOLD}").fetchone()[0]
    avg_score = db.execute("SELECT AVG(decay_score) FROM facts WHERE permanent = 0").fetchone()[0] or 0.0

    db.close()
    return {
        "total": total,
        "permanent": permanent,
        "hot": hot,
        "cold": cold,
        "avg_score": avg_score,
    }


def add_alias(alias: str, entity: str):
    """添加别名"""
    db = get_db()
    db.execute("INSERT OR REPLACE INTO aliases (alias, entity) VALUES (?, ?)",
               (alias, entity))
    db.commit()
    db.close()
    print(f"✅ 别名: '{alias}' → '{entity}'")


def resolve_alias(alias: str):
    """解析别名"""
    db = get_db()
    row = db.execute("SELECT entity FROM aliases WHERE alias=?", (alias,)).fetchone()
    db.close()
    return row["entity"] if row else None


def add_relation(subject: str, predicate: str, obj: str, category: str = "tech"):
    """添加关系三元组"""
    db = get_db()
    db.execute("""
        INSERT OR REPLACE INTO relations (subject, predicate, object, category)
        VALUES (?, ?, ?, ?)
    """, (subject, predicate, obj, category))
    db.commit()
    db.close()
    print(f"🔗 关系: ({subject}, {predicate}, {obj})")


def main():
    parser = argparse.ArgumentParser(description="结构化记忆系统")
    sub = parser.add_subparsers(dest="cmd")

    # init
    sub.add_parser("init", help="初始化 facts.db")

    # add
    add_p = sub.add_parser("add", help="添加事实")
    add_p.add_argument("entity")
    add_p.add_argument("key")
    add_p.add_argument("value")
    add_p.add_argument("category", nargs="?", default="knowledge")
    add_p.add_argument("--source", default="manual")
    add_p.add_argument("--permanent", action="store_true")

    # get
    get_p = sub.add_parser("get", help="获取事实")
    get_p.add_argument("entity")
    get_p.add_argument("key", nargs="?")

    # search
    search_p = sub.add_parser("search", help="搜索事实")
    search_p.add_argument("query")
    search_p.add_argument("--category")
    search_p.add_argument("--limit", type=int, default=20)

    # delete
    del_p = sub.add_parser("delete", help="删除事实")
    del_p.add_argument("entity")
    del_p.add_argument("key")

    # decay
    sub.add_parser("decay", help="运行衰减")

    # stats
    sub.add_parser("stats", help="查看统计")

    # alias
    alias_p = sub.add_parser("alias", help="添加别名")
    alias_p.add_argument("alias")
    alias_p.add_argument("entity")

    # relation
    rel_p = sub.add_parser("rel", help="添加关系")
    rel_p.add_argument("subject")
    rel_p.add_argument("predicate")
    rel_p.add_argument("object")
    rel_p.add_argument("category", nargs="?", default="tech")

    args = parser.parse_args()

    if args.cmd == "init":
        init_db()

    elif args.cmd == "add":
        add_fact(args.entity, args.key, args.value, args.category,
                args.source, args.permanent)

    elif args.cmd == "get":
        result = get_fact(args.entity, args.key)
        if result:
            if isinstance(result, list):
                for r in result:
                    print(f"  {r['key']}: {r['value']} [{r['category']}]")
            else:
                print(f"  {result['value']}")
        else:
            print(f"  未找到")

    elif args.cmd == "search":
        results = search_facts(args.query, args.category, args.limit)
        for r in results:
            print(f"  [{r['category']}] {r['entity']}.{r['key']}: {r['value']}")

    elif args.cmd == "delete":
        delete_fact(args.entity, args.key)

    elif args.cmd == "decay":
        run_decay()

    elif args.cmd == "stats":
        stats = get_stats()
        print(f"📊 Facts.db 统计:")
        print(f"  总事实: {stats['total']}")
        print(f"  永久: {stats['permanent']}")
        print(f"  热(≥0.90): {stats['hot']}")
        print(f"  冷(<{COLD_THRESHOLD}): {stats['cold']}")
        print(f"  平均分: {stats['avg_score']:.3f}")

    elif args.cmd == "alias":
        add_alias(args.alias, args.entity)

    elif args.cmd == "rel":
        add_relation(args.subject, args.predicate, args.object, args.category)

    else:
        parser.print_help()


if __name__ == "__main__":
    main()
