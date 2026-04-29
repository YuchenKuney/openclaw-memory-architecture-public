-- facts.db schema - 结构化记忆系统 for OpenClaw
-- 借鉴 coolmanns/openclaw-memory-architecture
-- 
-- 核心表: facts (实体-键-值 三元组)
-- 支持: FTS5全文搜索 / 衰减模型 / 别名 / 关系图

-- ============================================================================
-- Core facts table
-- ============================================================================
CREATE TABLE IF NOT EXISTS facts (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    entity TEXT NOT NULL,          -- 实体: "坤哥", "skill_factory", "decision"
    key TEXT NOT NULL,            -- 键: "时区", "版本", "always use"
    value TEXT NOT NULL,           -- 值: "Europe/Berlin", "v12", "trash"
    category TEXT NOT NULL,        -- 分类: people/tech/decision/preference/project
    source TEXT,                   -- 来源: "manual", "metabolism", "conversation"
    created_at TEXT NOT NULL DEFAULT (datetime('now')),
    last_accessed TEXT,            -- 上次访问时间(用于衰减)
    access_count INTEGER DEFAULT 0, -- 访问次数
    permanent BOOLEAN DEFAULT 0,   -- 1=永久不过期
    decay_score REAL DEFAULT 1.0,  -- 衰减分数 (0.0-1.0)
    activation REAL DEFAULT 0.0,    -- 激活度
    importance REAL DEFAULT 0.5    -- 重要度 (0.0-1.0)
);

-- Valid categories:
--   people: person, family, friend
--   tech: project, infrastructure, tool, skill
--   decisions: decision, preference, convention
--   ops: automation, workflow
--   knowledge: reference, research

-- Born permanent: person, family, friend, decision, preference

CREATE INDEX IF NOT EXISTS idx_facts_entity ON facts(entity);
CREATE INDEX IF NOT EXISTS idx_facts_category ON facts(category);
CREATE INDEX IF NOT EXISTS idx_facts_entity_key ON facts(entity, key);

-- ============================================================================
-- Full-text search on facts (FTS5)
-- ============================================================================
CREATE VIRTUAL TABLE IF NOT EXISTS facts_fts USING fts5(
    entity, key, value,
    content=facts,
    content_rowid=id
);

CREATE TRIGGER IF NOT EXISTS facts_ai AFTER INSERT ON facts BEGIN
    INSERT INTO facts_fts(rowid, entity, key, value)
    VALUES (new.id, new.entity, new.key, new.value);
END;

CREATE TRIGGER IF NOT EXISTS facts_ad AFTER DELETE ON facts BEGIN
    INSERT INTO facts_fts(facts_fts, rowid, entity, key, value)
    VALUES('delete', old.id, old.entity, old.key, old.value);
END;

CREATE TRIGGER IF NOT EXISTS facts_au AFTER UPDATE ON facts BEGIN
    INSERT INTO facts_fts(facts_fts, rowid, entity, key, value)
    VALUES('delete', old.id, old.entity, old.key, old.value);
    INSERT INTO facts_fts(rowid, entity, key, value)
    VALUES (new.id, new.entity, new.key, new.value);
END;

-- ============================================================================
-- Co-occurrences: 相关事实图谱边
-- 用于联想检索 - 访问事实A时关联推送事实B
-- ============================================================================
CREATE TABLE IF NOT EXISTS co_occurrences (
    fact_a INTEGER NOT NULL,
    fact_b INTEGER NOT NULL,
    weight REAL DEFAULT 1.0,
    last_wired TEXT,
    PRIMARY KEY (fact_a, fact_b),
    FOREIGN KEY (fact_a) REFERENCES facts(id),
    FOREIGN KEY (fact_b) REFERENCES facts(id)
);

CREATE INDEX IF NOT EXISTS idx_co_occ_a ON co_occurrences(fact_a);
CREATE INDEX IF NOT EXISTS idx_co_occ_b ON co_occurrences(fact_b);

-- ============================================================================
-- Aliases: 别名表
-- e.g. "坤哥" → "坤哥", "老大", "老板"
-- ============================================================================
CREATE TABLE IF NOT EXISTS aliases (
    alias TEXT NOT NULL COLLATE NOCASE,
    entity TEXT NOT NULL COLLATE NOCASE,
    PRIMARY KEY (alias, entity)
);

CREATE INDEX IF NOT EXISTS idx_aliases_entity ON aliases(entity);

-- ============================================================================
-- Relations: 关系三元组
-- e.g. ("坤哥", "使用", "Neural Tunnel")
-- ============================================================================
CREATE TABLE IF NOT EXISTS relations (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    subject TEXT NOT NULL,
    predicate TEXT NOT NULL,
    object TEXT NOT NULL,
    source TEXT DEFAULT 'manual',
    category TEXT DEFAULT 'tech',
    permanent BOOLEAN DEFAULT 1,
    created_at TEXT DEFAULT (datetime('now')),
    activation REAL DEFAULT 0.0,
    access_count INTEGER DEFAULT 0,
    decay_score REAL DEFAULT 1.0
);

CREATE INDEX IF NOT EXISTS idx_rel_subject ON relations(subject);
CREATE INDEX IF NOT EXISTS idx_rel_predicate ON relations(predicate);
CREATE INDEX IF NOT EXISTS idx_rel_object ON relations(object);
CREATE UNIQUE INDEX IF NOT EXISTS idx_rel_triple ON relations(subject, predicate, object);

CREATE VIRTUAL TABLE IF NOT EXISTS relations_fts USING fts5(
    subject, predicate, object,
    content=relations,
    content_rowid=id
);

-- ============================================================================
-- Changelog: 操作审计日志
-- ============================================================================
CREATE TABLE IF NOT EXISTS facts_changelog (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    entity TEXT NOT NULL,
    key TEXT NOT NULL,
    operation TEXT NOT NULL,       -- "insert", "update", "delete", "prune"
    old_value TEXT,
    new_value TEXT,
    source TEXT,
    timestamp TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE INDEX IF NOT EXISTS idx_changelog_entity ON facts_changelog(entity);
CREATE INDEX IF NOT EXISTS idx_changelog_timestamp ON facts_changelog(timestamp);
