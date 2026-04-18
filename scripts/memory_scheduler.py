#!/usr/bin/env python3
"""
Memory Scheduler - 主动记忆调度器

让记忆系统具有"睡眠阶段"：

1. 主动整理（夜间 consolidation）
   - 合并碎片化记忆
   - 提炼零散观察 → 规律

2. 主动总结（生成长期知识）
   - 将频繁出现的模式 → 沉淀为 Belief
   - 将短期经验 → 升华为规则

3. 主动删除（Forgetting Curve）
   - 基于艾宾浩斯遗忘曲线
   - 不重要记忆自然淘汰

4. 日志交叉验证提纯（Cross-Validation Log Purifier）⭐ v5新增
   - Day1 日志 + Day2 日志 → 交叉验证 → 提纯
   - 连续两天出现的 → 高置信度 → 沉淀为 Belief
   - 只出现一天 → 低置信度 → Observation
   - Day3 删除 Day1 原日志（已提纯）

调度时机：
- 空闲时（CPU < 30%）
- 夜间（02:00-04:00）
- 记忆量超过阈值时
"""

import json
import time
import tarfile
import gzip
from pathlib import Path
from datetime import datetime, timedelta
from typing import List, Dict, Optional, Set
from collections import defaultdict

# ============ Forgetting Curve ============

class ForgettingCurve:
    """
    艾宾浩斯遗忘曲线调度

    记忆强度随时间衰减：
    R = e^(-t/S)

    触发删除条件：
    - 记忆强度 < 阈值（默认 0.2）
    - 且访问频率低
    - 且重要性低
    """

    # 艾宾浩斯复习节点（天）
    REVIEW_NODES = [1, 2, 4, 7, 15, 30, 60, 120, 180, 365]

    def __init__(self, min_strength: float = 0.2):
        self.min_strength = min_strength

    def calculate_strength(self, item: dict) -> float:
        """
        计算记忆强度

        公式：R = e^(-t/S) × (1 + boost)

        boost = 重要性加成 + 复习加成
        """
        created = datetime.fromisoformat(item.get("timestamp", datetime.now().isoformat()))
        days_ago = (datetime.now() - created).days

        # 基础衰减
        S = 30  # 稳定期参数（30天后衰减加速）
        strength = 2 ** (-days_ago / S)

        # 重要性加成
        importance = item.get("importance", 0.5)
        importance_boost = importance * 0.3

        # 复习加成（如果在复习节点附近，强度回升）
        access_count = item.get("access_count", 0)
        review_boost = min(0.2, access_count * 0.02)

        final_strength = strength + importance_boost + review_boost
        return min(1.0, final_strength)

    def should_forget(self, item: dict) -> bool:
        """判断是否应该遗忘"""
        strength = self.calculate_strength(item)

        # 强度低于阈值 且 访问次数少 且 重要性低 → 可以遗忘
        if strength < self.min_strength:
            # 重要性高的稍微保护一下
            if item.get("importance", 0) > 0.7:
                return strength < self.min_strength * 0.5
            return True

        return False

    def get_next_review(self, item: dict) -> Optional[datetime]:
        """
        计算下次复习时间
        """
        created = datetime.fromisoformat(item.get("timestamp", datetime.now().isoformat()))
        days_ago = (datetime.now() - created).days

        for node in self.REVIEW_NODES:
            if days_ago < node:
                next_review = created + timedelta(days=node)
                if next_review > datetime.now():
                    return next_review

        return None


# ============ Cross-Validation Log Purifier ============

class CrossValidationLogPurifier:
    """
    日志交叉验证提纯器

    核心原理（坤哥设计）：
    - Day1 日志 + Day2 日志 → 交叉验证 → 提纯摘要
    - 连续两天出现的 → 高置信度 → 沉淀为 Belief/Core
    - 只出现一天 → 低置信度 → Observation
    - Day3 删除 Day1 原日志（已提纯）

    时序逻辑：
    Day N:     记录日志
    Day N+1:   与 Day N 交叉验证 → 提纯
    Day N+2:   删除 Day N 原日志（确认已提纯入库）
    """

    def __init__(self, memory_dir: str = "/root/.openclaw/workspace/memory",
                 backup_dir: str = "/root/.openclaw/workspace/.log_backup",
                 retention_days: int = 2):
        self.memory_dir = Path(memory_dir)
        self.backup_dir = Path(backup_dir)
        self.backup_dir.mkdir(parents=True, exist_ok=True)
        self.retention_days = retention_days  # N+2 天删除

        # 关键事件提取模式
        self.event_patterns = [
            # 错误类
            (r'(?i)(error|failed|失败|异常)', 'error'),
            (r'(?i)(warn|警告|超时)', 'warning'),
            # 业务类
            (r'(?i)(销售|gmv|订单|revenue)', 'business'),
            (r'(?i)(用户|新增|注册)', 'user'),
            # 系统类
            (r'(?i)(服务器|宕机|重启)', 'system'),
            (r'(?i)(数据库|连接|查询)', 'database'),
        ]

    def extract_events(self, text: str) -> Set[str]:
        """
        从日志中提取关键事件

        Returns:
            事件集合（去重）
        """
        events = set()
        lines = text.split('\n')

        for line in lines:
            line = line.strip()
            if not line:
                continue

            # 按模式提取
            for pattern, event_type in self.event_patterns:
                import re
                matches = re.findall(pattern, line)
                if matches:
                    # 提取事件核心词（去噪声）
                    event = self._clean_event(line)
                    if event:
                        events.add(event)
                    break  # 一个事件只归一个类型

        return events

    def _clean_event(self, line: str) -> Optional[str]:
        """
        清洗事件：归一化核心，保留事件类型

        关键改进：
        - 去除时间戳/IP/端口
        - 归一化错误详情（timeout/connection refused → 都归为"连接失败"）
        - 保留事件类型
        """
        import re

        # 去除时间戳
        line = re.sub(r'\d{4}-\d{2}-\d{2}[T ]\d{2}:\d{2}:\d{2}[^\s]*', '', line)
        # 去除 IP
        line = re.sub(r'\d{1,3}(?:\.\d{1,3}){3}', '<IP>', line)
        # 去除端口
        line = re.sub(r':\d{4,5}', '', line)
        # 去除文件路径
        line = re.sub(r'/[\w/.-]+', '<PATH>', line)
        # 去除用户ID/订单ID等
        line = re.sub(r'\w+[_]?\d{5,}', '<ID>', line)

        # 归一化错误详情（按长度从长到短，防止嵌套匹配）
        # 格式: (pattern, replacement)
        replacements = [
            (r'(?i)connection\s*refused', '连接拒绝'),
            (r'(?i)connection\s*reset', '连接重置'),
            (r'(?i)connection\s*timeout', '连接超时'),
            (r'(?i)broken\s*pipe', '连接断开'),
            (r'(?i)database\s*connection', '数据库连接'),
            (r'(?i)slow\s*query', '查询慢'),
            (r'(?i)timeout', '超时'),
            (r'(?i)failed', '失败'),
            (r'(?i)(?:503|500|502|504|400|401|403|404)', 'HTTP错误'),
        ]
        for pattern, replacement in replacements:
            line = re.sub(pattern, replacement, line, flags=re.IGNORECASE)

        # 清理多余空格
        line = re.sub(r'\s+', ' ', line).strip()

        if len(line) > 10:
            return line[:80]
        return None

    def _core_event(self, event: str) -> str:
        """
        提取事件核心词（用于相似匹配）
        例如：
        - "数据库连接 失败: 超时" → "数据库连接"
        - "数据库连接 失败: 连接拒绝" → "数据库连接"
        """
        import re
        # 提取核心词（去掉具体错误详情）
        core = re.sub(r'\s*[:：].*$', '', event)  # 去掉冒号后的详情
        core = re.sub(r'(?i)<[^>]+>', '', core)   # 去掉归一化标签
        core = core.strip()
        return core

    def _is_similar_event(self, e1: str, e2: str) -> bool:
        """判断两个事件是否相似（同类事件）"""
        c1, c2 = self._core_event(e1), self._core_event(e2)
        if not c1 or not c2:
            return False
        # 核心词相同
        return c1 == c2

    def cross_validate(self, day1_events: Set[str], day2_events: Set[str]) -> Dict:
        """
        交叉验证（支持精确匹配 + 相似匹配）

        Returns:
            {
                "confirmed": [...],     # 两天都有（精确）→ 高置信度
                "partial": [...],      # 同类事件（相似）→ 中置信度
                "new_in_day2": [...],  # 只有第二天有 → 待观察
                "dropped_from_day1": [...]  # 只有第一天有 → 可能是噪音/临时事件
            }
        """
        intersection = day1_events & day2_events
        day2_only = day2_events - day1_events
        day1_only = day1_events - day2_events

        # 部分匹配：同类型但细节不同的事件
        partial = []
        for e1 in day1_only:
            for e2 in day2_only:
                if self._is_similar_event(e1, e2):
                    # 保留两个版本，但标记为partial match
                    if e1 not in partial:
                        partial.append(e1)
                    if e2 not in partial:
                        partial.append(e2)

        partial_set = set(partial)
        confirmed_exact = list(intersection)
        new_only = [e for e in day2_only if e not in partial_set]
        dropped_only = [e for e in day1_only if e not in partial_set]

        return {
            "confirmed": confirmed_exact,          # 精确匹配
            "partial": partial,                   # 相似匹配（同类型）
            "new_in_day2": new_only,            # 新出现
            "dropped_from_day1": dropped_only,  # 可能是噪音
        }

    def distill(self, day1_text: str, day2_text: str) -> Dict:
        """
        执行提纯

        Args:
            day1_text: 第一天日志
            day2_text: 第二天日志

        Returns:
            提纯结果 + 置信度评估
        """
        day1_events = self.extract_events(day1_text)
        day2_events = self.extract_events(day2_text)

        validation = self.cross_validate(day1_events, day2_events)

        # 生成提纯摘要（不同置信度）
        confirmed_summary = self._generate_summary(validation["confirmed"], label="确认", confidence=0.9)
        partial_summary = self._generate_summary(validation["partial"], label="相似", confidence=0.75)
        new_summary = self._generate_summary(validation["new_in_day2"], label="新", confidence=0.4)
        dropped_summary = self._generate_summary(validation["dropped_from_day1"], label="噪音", confidence=0.15)

        total_unique = len(day1_events | day2_events)
        confirmed_count = len(validation["confirmed"])
        partial_count = len(validation["partial"]) // 2  # 每个匹配占两个位置

        return {
            "day1_event_count": len(day1_events),
            "day2_event_count": len(day2_events),
            "confirmed_count": confirmed_count,
            "partial_count": partial_count,
            "new_in_day2_count": len(validation["new_in_day2"]),
            "dropped_count": len(validation["dropped_from_day1"]),
            "validation": validation,
            "summaries": {
                "confirmed": confirmed_summary,
                "partial": partial_summary,
                "new": new_summary,
                "dropped": dropped_summary,
            },
            "confidence": (confirmed_count + partial_count * 0.6) / max(total_unique, 1),
        }

    def _generate_summary(self, events: List[str], label: str = None, confidence: float = None) -> str:
        """
        生成摘要文本

        Args:
            events: 事件列表
            label: 标签（确认/相似/新/噪音）
            confidence: 置信度（用于自动判断标签）
        """
        if not events:
            return ""

        if label is None:
            if confidence is not None:
                if confidence > 0.7: label = "确认"
                elif confidence > 0.4: label = "新"
                else: label = "噪音"
            else:
                label = "未知"

        lines = [f"- [{label}] {e}" for e in events]
        return "\n".join(lines)

    def load_day_log(self, date: str) -> Optional[str]:
        """
        加载指定日期的日志文件

        Args:
            date: YYYY-MM-DD 格式
        """
        log_file = self.memory_dir / f"{date}.md"
        if log_file.exists():
            return log_file.read_text(encoding='utf-8', errors='ignore')

        # 也检查备份
        backup_file = self.backup_dir / f"{date}.md.gz"
        if backup_file.exists():
            with gzip.open(backup_file, 'rt', encoding='utf-8', errors='ignore') as f:
                return f.read()

        return None

    def should_delete_day(self, date: str) -> bool:
        """
        判断某天的日志是否应该删除

        规则：当前日期 >= 日期 + retention_days
        例如：retention_days=2，Day1=4月15日，4月17日起可删除
        """
        try:
            log_date = datetime.strptime(date, "%Y-%m-%d")
            delete_after = log_date + timedelta(days=self.retention_days)
            return datetime.now() >= delete_after
        except:
            return False

    def backup_and_delete(self, date: str) -> Dict:
        """
        备份并删除过期日志

        1. gzip 压缩备份
        2. 删除原文件
        """
        log_file = self.memory_dir / f"{date}.md"

        if not log_file.exists():
            return {"status": "skipped", "reason": "文件不存在"}

        try:
            # 压缩备份
            backup_file = self.backup_dir / f"{date}.md.gz"
            with gzip.open(backup_file, 'wt', encoding='utf-8') as f:
                f.write(log_file.read_text(encoding='utf-8', errors='ignore'))

            # 删除原文件
            log_file.unlink()

            return {
                "status": "success",
                "date": date,
                "backup_file": str(backup_file),
                "size_before": log_file.stat().st_size if log_file.exists() else 0,
            }

        except Exception as e:
            return {"status": "error", "reason": str(e)}

    def run_daily_purify(self, today: str = None) -> Dict:
        """
        执行每日提纯任务

        流程：
        1. 加载昨天的日志
        2. 加载今天的日志
        3. 交叉验证
        4. 生成提纯摘要
        5. 备份并删除过期的日志
        """
        today = today or datetime.now().strftime("%Y-%m-%d")
        yesterday = (datetime.strptime(today, "%Y-%m-%d") - timedelta(days=1)).strftime("%Y-%m-%d")
        day_before_yesterday = (datetime.strptime(today, "%Y-%m-%d") - timedelta(days=2)).strftime("%Y-%m-%d")

        report = {
            "date": today,
            "yesterday": yesterday,
            "validation": None,
            "backups": [],
            "errors": [],
        }

        # Step 1: 加载日志
        day1_text = self.load_day_log(yesterday)
        day2_text = self.load_day_log(today)

        if not day1_text:
            report["errors"].append(f"找不到昨天({yesterday})的日志")
        if not day2_text:
            report["errors"].append(f"找不到今天({today})的日志")

        if not day1_text or not day2_text:
            report["status"] = "incomplete"
            return report

        # Step 2: 交叉验证
        report["validation"] = self.distill(day1_text, day2_text)

        # Step 3: 检查过期日志（day_before_yesterday）
        if self.should_delete_day(day_before_yesterday):
            backup_result = self.backup_and_delete(day_before_yesterday)
            report["backups"].append(backup_result)

        # Step 4: 用户画像变化检测（从日志文本直接检测）
        # 合并Day1和Day2的日志，用新方法检测
        combined_text = f"{day1_text or ''}\n{day2_text or ''}"
        profile_changes = self.detect_profile_from_text(combined_text, min_confidence=0.6)
        if profile_changes:
            report["profile_changes"] = profile_changes
            self._apply_profile_changes(profile_changes[:3])  # 最多应用3条

        report["status"] = "completed"
        return report

    def _detect_profile_changes(self, validation: Dict) -> List[Dict]:
        """
        检测用户画像变化

        从验证结果中提取与用户偏好相关的变化
        """
        if not validation:
            return []

        changes = []

        # 用户画像相关的关键词模式
        profile_patterns = [
            # 沟通/工作习惯
            (r'(?i)(喜欢|偏好|习惯|经常|总是|从不)(.*)', 'behavior'),
            # 明确偏好声明
            (r'(?i)(我的|我想|我要|我不)(.*)', 'preference'),
            # 时间/节奏偏好
            (r'(?i)(早上|晚上|白天|凌晨|中午)(.*)', 'time_preference'),
            # 沟通风格
            (r'(?i)(直接|简洁|详细|简短|啰嗦)(.*)', 'communication_style'),
            # 重要日程/事件
            (r'(?i)(每天|每周|每月|要|必须|一定)(.*)', 'routine'),
        ]

        # 直接从原始日志文本检测（validation里的是清洗后的事件，可能太简略）
        # 检查confirmed和partial事件的原文
        for event in validation.get("confirmed", []) + validation.get("partial", []):
            for pattern, ptype in profile_patterns:
                import re
                match = re.search(pattern, event)
                if match:
                    changes.append({
                        "type": ptype,
                        "event": event,
                        "confidence": 0.9 if event in validation.get("confirmed", []) else 0.75,
                        "matched_pattern": pattern,
                    })
                    break

        return changes

    def detect_profile_from_text(self, text: str, min_confidence: float = 0.5) -> List[Dict]:
        """
        直接从文本中检测用户画像变化（不依赖交叉验证）

        用于每日提纯时直接扫描日志文本
        """
        changes = []
        import re

        # 用户画像关键模式
        profile_patterns = [
            # 偏好/习惯声明
            (r'[^。？！]*?(?:喜欢|偏好|习惯|经常|总是|从不)[^。？！]*[。？！]', 'behavior', 0.7),
            # 明确自我声明
            (r'[^。？！]*?(?:我的|我想|我要|我不)[^。？！]*[。？！]', 'preference', 0.8),
            # 时间规律
            (r'[^。？！]*?(?:每天|每周|每月|早上|晚上|白天)[^。？！]*[。？！]', 'time_preference', 0.6),
            # 沟通风格
            (r'[^。？！]*?(?:直接|简洁|详细|简短|废话)[^。？！]*[。？！]', 'communication_style', 0.7),
            # 重要任务/日程
            (r'[^。？！]*?(?:要|必须|一定|不能)[^。？！]*[。？！]', 'routine', 0.6),
            # 反馈/评价
            (r'[^。？！]*?(?:不错|可以|好|行|同意)[^。？！]*[。？！]', 'feedback', 0.5),
        ]

        for pattern, ptype, base_conf in profile_patterns:
            matches = re.finditer(pattern, text)
            for match in matches:
                sentence = match.group(0).strip()
                if len(sentence) > 5:  # 过滤太短的
                    changes.append({
                        "type": ptype,
                        "event": sentence,
                        "confidence": base_conf,
                        "position": match.start(),
                    })

        # 按置信度排序
        changes.sort(key=lambda x: x["confidence"], reverse=True)

        # 去重：相同事件只保留最高置信度的
        seen = set()
        deduped = []
        for c in changes:
            # 用事件前30字作为去重key
            key = c["event"][:30]
            if key not in seen:
                seen.add(key)
                deduped.append(c)

        return [c for c in deduped if c["confidence"] >= min_confidence]

    def _apply_profile_changes(self, changes: List[Dict]) -> Dict:
        """
        将检测到的用户画像变化应用到 USER.md

        Returns:
            更新结果
        """
        user_file = Path("/root/.openclaw/workspace/USER.md")
        if not user_file.exists():
            return {"status": "skipped", "reason": "USER.md不存在"}

        try:
            current_content = user_file.read_text(encoding='utf-8')

            # 构建更新摘要
            update_notes = []
            for change in changes:
                note = f"- [{change['type']}] {change['event'][:60]} (置信度:{change['confidence']:.0%})"
                update_notes.append(note)

            # 在文件末尾添加更新记录
            timestamp = datetime.now().strftime("%Y-%m-%d %H:%M")
            update_section = f"\n\n## 🔄 画像动态更新\n\n_自动检测于 {timestamp}_\n\n" + "\n".join(update_notes)

            # 检查是否已有更新章节，有则追加，无则新建
            if "## 🔄 画像动态更新" in current_content:
                # 找到最后一个更新章节位置，追加
                parts = current_content.split("## 🔄 画像动态更新")
                current_content = parts[0] + "## 🔄 画像动态更新" + parts[1].split("\n\n##")[0] + "\n" + update_notes[0] + update_section
            else:
                current_content += update_section

            # 写回
            user_file.write_text(current_content, encoding='utf-8')

            return {
                "status": "success",
                "changes_detected": len(changes),
                "updates_applied": len(update_notes),
            }

        except Exception as e:
            return {"status": "error", "reason": str(e)}


# ============ Consolidation Engine ============

class ConsolidationEngine:
    """
    记忆整理引擎

    功能：
    - 合并碎片化记忆
    - 提炼零散观察为规律
    - 清理过期记忆
    """

    def __init__(self, memory_manager):
        self.memory = memory_manager
        self.forgetting = ForgettingCurve()

    def consolidate(self) -> Dict:
        """
        执行整理

        Returns:
            {
                "merged": int,      # 合并数量
                "promoted": int,     # 升华为信念数量
                "forgotten": int,    # 遗忘数量
                "summaries": [...]   # 生成的知识摘要
            }
        """
        stats = {
            "merged": 0,
            "promoted": 0,
            "forgotten": 0,
            "summaries": []
        }

        # 1. 遗忘（Forgetting）
        forgotten = self._apply_forgetting()
        stats["forgotten"] = forgotten

        # 2. 合并碎片
        merged = self._merge_similar()
        stats["merged"] = merged

        # 3. 提炼规律（Observation → Belief）
        promoted = self._promote_to_belief()
        stats["promoted"] = promoted

        return stats

    def _apply_forgetting(self) -> int:
        """应用遗忘曲线"""
        all_items = self.memory.backend.list_all()
        forgotten_count = 0

        for item in all_items:
            item_dict = item.to_dict() if hasattr(item, 'to_dict') else item
            if self.forgetting.should_forget(item_dict):
                self.memory.backend.delete(item.id)
                forgotten_count += 1

        return forgotten_count

    def _merge_similar(self) -> int:
        """合并相似记忆"""
        all_items = self.memory.backend.list_all()
        merged = 0

        # 按类型分组
        by_type = defaultdict(list)
        for item in all_items:
            by_type[item.type].append(item)

        for mtype, items in by_type.items():
            if len(items) < 2:
                continue

            # 找出内容高度相似的
            i = 0
            while i < len(items):
                j = i + 1
                while j < len(items):
                    if self._is_similar(items[i], items[j], threshold=0.8):
                        # 合并：保留重要性高的，内容合并
                        winner = items[i] if items[i].importance >= items[j].importance else items[j]
                        loser = items[j] if items[i].importance >= items[j].importance else items[i]

                        merged_content = f"{winner.content}\n---\n{loser.content[:100]}"
                        self.memory.backend.update(winner.id, {
                            "content": merged_content,
                            "importance": max(winner.importance, loser.importance)
                        })
                        self.memory.backend.delete(loser.id)
                        merged += 1
                        items.remove(loser)
                    j += 1
                i += 1

        return merged

    def _is_similar(self, item1, item2, threshold: float = 0.7) -> bool:
        """判断两条记忆是否相似"""
        # 简单关键词重叠检测
        words1 = set(item1.content.lower())
        words2 = set(item2.content.lower())
        if not words1 or not words2:
            return False

        overlap = len(words1 & words2) / len(words1 | words2)
        return overlap >= threshold

    def _promote_to_belief(self) -> int:
        """
        将观察升华为信念

        条件：
        - 类型是 observation
        - 出现次数 >= 3
        - 跨多个记忆条目
        """
        all_items = self.memory.backend.list_all()

        # 统计高频词
        word_freq = defaultdict(int)
        observation_items = []

        for item in all_items:
            if item.type == "observation":
                observation_items.append(item)
                for word in item.content:
                    if word.isalnum() and len(word) > 1:
                        word_freq[word] += 1

        promoted = 0
        # 高频模式 → 升华为 belief
        high_freq = [(w, c) for w, c in word_freq.items() if c >= 3]

        for word, count in high_freq:
            # 找到包含这个词的观察记忆
            related = [m for m in observation_items if word in m.content.lower()]
            if len(related) >= 3:
                # 创建信念
                summary = f"频繁观察：{word}（出现{count}次）"
                belief_id = self.memory.add(
                    content=summary,
                    type="belief",
                    importance=0.6,
                    tags=["promoted_from_observation"]
                )
                # 删除原来的观察记忆
                for m in related[:3]:  # 只删除前3个
                    self.memory.backend.delete(m.id)
                promoted += 1

        return promoted


# ============ Knowledge Generator ============

class KnowledgeGenerator:
    """
    知识生成器

    功能：
    - 从记忆中生成结构化知识
    - 生成摘要
    - 生成规则
    """

    def __init__(self, memory_manager):
        self.memory = memory_manager

    def generate_daily_summary(self, date: str = None) -> str:
        """
        生成每日摘要
        """
        date = date or datetime.now().strftime("%Y-%m-%d")

        all_items = self.memory.backend.list_all()

        # 按类型统计
        by_type = defaultdict(list)
        for item in all_items:
            by_type[item.type].append(item)

        lines = [f"# 每日记忆摘要 - {date}\n"]

        for mtype, items in by_type.items():
            lines.append(f"\n## {mtype} ({len(items)}条)")

            # 按重要性排序
            sorted_items = sorted(items, key=lambda x: x.importance, reverse=True)

            for item in sorted_items[:5]:
                conf = "🟢" if item.composite_score > 0.7 else "🟡" if item.composite_score > 0.4 else "🔴"
                lines.append(f"- {conf} {item.content[:80]}")

        return "\n".join(lines)

    def generate_insights(self) -> List[str]:
        """
        生成洞察
        """
        all_items = self.memory.backend.list_all()
        insights = []

        # 按类型分析
        by_type = defaultdict(list)
        for item in all_items:
            by_type[item.type].append(item)

        # 偏好洞察
        prefs = by_type.get("preference", [])
        if len(prefs) >= 3:
            insights.append(f"发现 {len(prefs)} 条用户偏好记录")

        # 错误洞察
        errors = by_type.get("error", [])
        if len(errors) >= 2:
            insights.append(f"记录了 {len(errors)} 条错误/教训")

        # 高重要性记忆
        high_imp = [m for m in all_items if m.importance > 0.7]
        if high_imp:
            insights.append(f"有 {len(high_imp)} 条高重要性记忆需要关注")

        return insights

    def generate_rules(self) -> List[str]:
        """
        从记忆中生成规则
        """
        all_items = self.memory.backend.list_all()
        rules = []

        for item in all_items:
            # 从内容中提取规则性语句
            if any(kw in item.content for kw in ["必须", "应该", "不要", "记住"]):
                if item.type in ["preference", "behavior", "error"]:
                    rules.append(item.content)

        return rules[:10]


# ============ Memory Scheduler ============

class MemoryScheduler:
    """
    记忆调度器 - 主动记忆管理

    核心功能：
    1. 夜间 consolidation（02:00-04:00）
    2. 主动总结（生成长期知识）
    3. 主动删除（Forgetting Curve）
    4. 复习提醒（基于艾宾浩斯节点）
    5. 日志交叉验证提纯（Cross-Validation）

    调度策略：
    - 空闲时触发（CPU < 30%）
    - 定时触发（每小时检查一次）
    - 记忆量超阈值时触发
    """

    def __init__(self, memory_manager):
        self.memory = memory_manager
        self.consolidation = ConsolidationEngine(memory_manager)
        self.knowledge = KnowledgeGenerator(memory_manager)
        self.forgetting = ForgettingCurve()
        self.log_purifier = CrossValidationLogPurifier()

        self.last_consolidation: Optional[datetime] = None
        self.last_summary: Optional[datetime] = None
        self.last_log_purify: Optional[datetime] = None

        # 配置
        self.config = {
            "consolidation_interval_hours": 24,  # 每24小时整理一次
            "summary_interval_hours": 12,       # 每12小时总结一次
            "log_purify_interval_hours": 24,   # 每24小时提纯日志
            "forgetting_threshold": 0.2,          # 遗忘阈值
            "memory_limit_before_force": 1000,    # 强制整理阈值
            "night_hours_start": 2,              # 夜间窗口开始（2:00）
            "night_hours_end": 4,                # 夜间窗口结束（4:00）
        }

    def should_run(self) -> Dict:
        """
        判断是否应该运行
        """
        now = datetime.now()
        hour = now.hour

        # 检查是否在夜间窗口
        in_night_window = self.config["night_hours_start"] <= hour < self.config["night_hours_end"]

        # 检查是否到时间
        needs_consolidation = True
        needs_summary = True
        needs_log_purify = True

        if self.last_consolidation:
            hours_since = (now - self.last_consolidation).total_seconds() / 3600
            needs_consolidation = hours_since >= self.config["consolidation_interval_hours"]

        if self.last_summary:
            hours_since = (now - self.last_summary).total_seconds() / 3600
            needs_summary = hours_since >= self.config["summary_interval_hours"]

        if self.last_log_purify:
            hours_since = (now - self.last_log_purify).total_seconds() / 3600
            needs_log_purify = hours_since >= self.config["log_purify_interval_hours"]

        # 检查记忆量
        memory_count = len(self.memory.backend.list_all())
        memory_overflow = memory_count >= self.config["memory_limit_before_force"]

        return {
            "should_run": in_night_window or memory_overflow,
            "in_night_window": in_night_window,
            "needs_consolidation": needs_consolidation,
            "needs_summary": needs_summary,
            "needs_log_purify": needs_log_purify,
            "memory_overflow": memory_overflow,
            "memory_count": memory_count
        }

    def run(self, force: bool = False) -> Dict:
        """
        执行调度

        Returns:
            调度报告
        """
        status = self.should_run()

        if not force and not status["should_run"]:
            return {
                "status": "skipped",
                "reason": "not_due",
                "status": status
            }

        report = {
            "timestamp": datetime.now().isoformat(),
            "triggered_by": [],
            "consolidation": None,
            "knowledge": None,
            "log_purify": None,
            "forgetting": None,
            "next_review": None
        }

        # 1. Consolidation
        if status["needs_consolidation"] or force:
            self.consolidation.forgetting.min_strength = self.config["forgetting_threshold"]
            consolidation_result = self.consolidation.consolidate()
            report["consolidation"] = consolidation_result
            self.last_consolidation = datetime.now()
            report["triggered_by"].append("consolidation")

        # 2. 知识生成
        if status["needs_summary"] or force:
            knowledge_result = {
                "daily_summary": self.knowledge.generate_daily_summary(),
                "insights": self.knowledge.generate_insights(),
                "rules": self.knowledge.generate_rules()
            }
            report["knowledge"] = knowledge_result
            self.last_summary = datetime.now()
            report["triggered_by"].append("summary")

        # 3. 日志交叉验证提纯
        if status["needs_log_purify"] or force:
            try:
                log_purify_result = self.log_purifier.run_daily_purify()
                report["log_purify"] = log_purify_result
                self.last_log_purify = datetime.now()
                report["triggered_by"].append("log_purify")
            except Exception as e:
                report["log_purify"] = {"status": "error", "reason": str(e)}

        # 4. 复习提醒
        review_reminders = self.get_review_reminders()
        if review_reminders:
            report["next_review"] = review_reminders

        # 5. 溢出检测
        if status["memory_overflow"]:
            report["triggered_by"].append("overflow")

        report["status"] = "completed"
        return report

    def get_review_reminders(self) -> List[Dict]:
        """获取需要复习的记忆"""
        all_items = self.memory.backend.list_all()
        reminders = []

        for item in all_items:
            next_review = self.forgetting.get_next_review(item.to_dict())
            if next_review:
                reminders.append({
                    "id": item.id,
                    "content": item.content[:50],
                    "next_review": next_review.isoformat()
                })

        reminders.sort(key=lambda x: x["next_review"])
        return reminders[:10]

    def run_nightly(self) -> Dict:
        """
        专门在夜间运行（更激进）
        """
        # 夜间可以更激进地遗忘
        self.consolidation.forgetting.min_strength = 0.3  # 提高遗忘阈值
        return self.run(force=True)


def main():
    import argparse
    parser = argparse.ArgumentParser(description="Memory Scheduler - 主动记忆调度器")
    parser.add_argument("--status", "-s", action="store_true", help="显示调度状态")
    parser.add_argument("--run", "-r", action="store_true", help="执行调度")
    parser.add_argument("--nightly", "-n", action="store_true", help="夜间模式（激进）")
    parser.add_argument("--review", action="store_true", help="显示复习提醒")
    parser.add_argument("--purify", "-p", action="store_true", help="只运行日志提纯")
    args = parser.parse_args()

    # 简单的内存后端演示
    from scripts.memory_system import MemoryManager, FileMemory
    import os

    storage = os.environ.get("MEMORY_STORAGE", "/tmp/.memory_scheduler")
    backend = FileMemory(storage)
    manager = MemoryManager(backend)
    scheduler = MemoryScheduler(manager)

    if args.purify:
        result = scheduler.log_purifier.run_daily_purify()
        print(f"📊 日志提纯结果:")
        if result.get("validation"):
            v = result["validation"]
            print(f"  昨天事件: {v.get('day1_event_count', 0)}")
            print(f"  今天事件: {v.get('day2_event_count', 0)}")
            print(f"  确认事件: {v.get('confirmed_count', 0)}")
            print(f"  新事件: {v.get('new_in_day2_count', 0)}")
            print(f"  丢弃事件: {v.get('dropped_count', 0)}")
        print(f"  备份: {len(result.get('backups', []))}个")
        for b in result.get("backups", []):
            print(f"    {b}")
        print(f"  状态: {result['status']}")
        return

    if args.status:
        s = scheduler.should_run()
        print("📊 Memory Scheduler 状态")
        print(f"记忆数量: {s['memory_count']}")
        print(f"是否在夜间窗口: {'✅' if s['in_night_window'] else '❌'}")
        print(f"需要整理: {'✅' if s['needs_consolidation'] else '❌'}")
        print(f"需要总结: {'✅' if s['needs_summary'] else '❌'}")
        print(f"需要日志提纯: {'✅' if s['needs_log_purify'] else '❌'}")
        print(f"内存溢出: {'⚠️' if s['memory_overflow'] else '✅'}")
        print(f"应该运行: {'✅' if s['should_run'] else '❌'}")

    elif args.run:
        result = scheduler.run()
        print(f"✅ 调度完成")
        print(f"触发原因: {', '.join(result['triggered_by'])}")
        if result.get("consolidation"):
            c = result["consolidation"]
            print(f"整理: 合并{c['merged']}条, 升华{c['promoted']}条, 遗忘{c['forgotten']}条")
        if result.get("knowledge"):
            k = result["knowledge"]
            print(f"知识: {len(k['insights'])}条洞察, {len(k['rules'])}条规则")
        if result.get("log_purify"):
            lp = result["log_purify"]
            if lp.get("validation"):
                v = lp["validation"]
                print(f"日志提纯: 确认{v.get('confirmed_count',0)}条, 新增{v.get('new_in_day2_count',0)}条")

    elif args.nightly:
        result = scheduler.run_nightly()
        print(f"🌙 夜间调度完成")
        if result.get("consolidation"):
            c = result["consolidation"]
            print(f"遗忘: {c['forgotten']}条 (激进模式)")

    elif args.review:
        reminders = scheduler.get_review_reminders()
        print(f"📚 复习提醒 ({len(reminders)}条):")
        for r in reminders[:5]:
            print(f"  - {r['content']}... (复习时间: {r['next_review'][:16]})")


if __name__ == "__main__":
    main()
