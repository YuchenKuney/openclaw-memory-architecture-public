"""
用户画像管理器 v2 - 双层Profile架构

解决认知漂移（Profile Drift）问题：

1. Stable Profile（稳定层）
   - 长期成立的特征
   - 更新慢，高置信度
   - 很难被覆盖

2. Dynamic Profile（动态层）
   - 短期行为
   - 更新快，可被覆盖
   - 可波动

3. Anti-Bias 机制
   - 新记忆与画像冲突 → 降低置信度
   - 系统不会固执，能自我修正

4. Profile 作为权重因子
   - 不直接驱动删除
   - score += consistency_with_profile × 0.2
"""

from dataclasses import dataclass, field
from typing import Dict, List, Optional, Set
from datetime import datetime, timedelta
import json
import re
from pathlib import Path


@dataclass
class ProfileEntry:
    """画像条目"""
    key: str           # 如 "language_preference"
    value: str          # 如 "Go"
    source: str         # 来源句子
    confidence: float   # 0-1
    layer: str          # "stable" or "dynamic"
    first_seen: str     # 首次出现日期
    last_seen: str      # 最近出现日期
    appearances: int     # 出现次数
    stable_confirmed: bool = False  # 是否已确认进入stable层

    def to_dict(self) -> Dict:
        return {
            "key": self.key,
            "value": self.value,
            "source": self.source,
            "confidence": self.confidence,
            "layer": self.layer,
            "first_seen": self.first_seen,
            "last_seen": self.last_seen,
            "appearances": self.appearances,
            "stable_confirmed": self.stable_confirmed,
        }


@dataclass
class ProfileChange:
    """画像变化记录"""
    key: str
    old_value: str
    new_value: str
    confidence: float
    reason: str  # "high_confidence_multi_appear" / "low_confidence_single"
    timestamp: str


class ProfileStabilityChecker:
    """
    画像稳定性检查器

    防止单次随口说导致画像固化（Profile Drift）
    """

    # 进入stable层的最低要求
    STABLE_MIN_APPEARANCES = 2  # 至少连续2天出现
    STABLE_MIN_CONFIDENCE = 0.6  # 最低置信度

    # 进入dynamic层的要求
    DYNAMIC_MIN_CONFIDENCE = 0.5

    def __init__(self):
        self.pending_profiles: Dict[str, List[Dict]] = {}  # key -> [出现记录]

    def record_appearance(self, profile_key: str, value: str, confidence: float, date: str = None) -> Dict:
        """
        记录一次出现

        Returns:
            {
                "layer": "stable" / "dynamic" / "pending",
                "action": "promote" / "update" / "wait",
                "reason": str
            }
        """
        date = date or datetime.now().strftime("%Y-%m-%d")

        if profile_key not in self.pending_profiles:
            self.pending_profiles[profile_key] = []

        # 检查是否是同一值
        existing = [p for p in self.pending_profiles[profile_key] if p["value"] == value]

        if existing:
            # 更新已有记录
            existing[0]["appearances"] += 1
            existing[0]["last_seen"] = date
            existing[0]["confidence"] = max(existing[0]["confidence"], confidence)
        else:
            # 新值
            self.pending_profiles[profile_key].append({
                "value": value,
                "confidence": confidence,
                "first_seen": date,
                "last_seen": date,
                "appearances": 1,
            })

        # 检查是否满足stable条件
        return self._evaluate(profile_key, value)

    def _evaluate(self, profile_key: str, value: str) -> Dict:
        """评估应该进入哪个层"""
        records = [p for p in self.pending_profiles.get(profile_key, []) if p["value"] == value]

        if not records:
            return {"layer": "unknown", "action": "wait", "reason": "no_record"}

        record = records[0]

        # 检查stable条件
        if (record["appearances"] >= self.STABLE_MIN_APPEARANCES and
            record["confidence"] >= self.STABLE_MIN_CONFIDENCE):
            return {
                "layer": "stable",
                "action": "promote",
                "reason": f"连续{record['appearances']}天出现，置信度{record['confidence']:.0%}"
            }

        # 检查dynamic条件
        if record["confidence"] >= self.DYNAMIC_MIN_CONFIDENCE:
            return {
                "layer": "dynamic",
                "action": "update",
                "reason": f"单次出现，置信度{record['confidence']:.0%}"
            }

        return {
            "layer": "pending",
            "action": "wait",
            "reason": f"置信度不足({record['confidence']:.0%})，等待更多验证"
        }


class AntiBiasEngine:
    """
    反偏见引擎

    当新记忆与画像冲突时，降低画像置信度
    """

    def __init__(self):
        self.debias_factor = 0.7  # 冲突时置信度衰减因子

    def check_conflict(self, new_memory: str, profile: Dict) -> float:
        """
        检查新记忆与画像的冲突程度

        Returns:
            0.0-1.0 的冲突系数
            1.0 = 完全冲突
            0.0 = 完全一致
        """
        if not profile:
            return 0.0

        # 提取新记忆中的关键偏好
        new_prefs = self._extract_preferences(new_memory)

        if not new_prefs:
            return 0.0

        # 与stable层比对
        conflicts = 0
        total = 0

        for key, entries in profile.get("stable", {}).items():
            if isinstance(entries, list):
                for entry in entries:
                    if isinstance(entry, dict) and "value" in entry:
                        total += 1
                        if self._is_conflicting(entry["value"], new_prefs):
                            conflicts += 1

        if total == 0:
            return 0.0

        return conflicts / total

    def _extract_preferences(self, text: str) -> Set[str]:
        """从文本中提取偏好关键词"""
        prefs = set()

        # 技术偏好
        tech_patterns = [
            r'(?:喜欢|偏好|用|写|开发)(?:于)?\s*(Python|Java|Go|Rust|JS|TS|Node|C\+\+|Ruby)',
            r'(?:不喜欢|不用|讨厌)\s*(Python|Java|Go|Rust|JS|TS|Node|C\+\+|Ruby)',
        ]
        for pattern in tech_patterns:
            matches = re.findall(pattern, text, re.IGNORECASE)
            prefs.update([m.lower() for m in matches])

        return prefs

    def _is_conflicting(self, profile_value: str, new_prefs: Set[str]) -> bool:
        """判断是否冲突"""
        pv = profile_value.lower()
        for pref in new_prefs:
            # 简单判断：完全不同的词认为是可能冲突
            if pv != pref and len(pv) > 2 and len(pref) > 2:
                return True
        return False

    def apply_debias(self, confidence: float, conflict_level: float) -> float:
        """
        应用反偏见

        冲突程度越高，置信度衰减越多
        """
        if conflict_level > 0.5:
            return confidence * (self.debias_factor ** (conflict_level * 2))
        return confidence


class ProfileManager:
    """
    用户画像管理器

    双层架构 + Anti-Bias + 权重因子
    """

    def __init__(self, profile_file: str = "/root/.openclaw/workspace/USER.md"):
        self.profile_file = Path(profile_file)
        self.stability = ProfileStabilityChecker()
        self.antibias = AntiBiasEngine()

        # 内存中的画像
        self.profile: Dict[str, Dict] = {
            "stable": {},
            "dynamic": {},
            "meta": {
                "version": "2.0",
                "last_updated": datetime.now().isoformat(),
                "drift_detected": 0,
            }
        }

        # 画像变化历史
        self.change_history: List[ProfileChange] = []

    def update_from_memory(self, memory_text: str) -> Dict:
        """
        从记忆/日志中更新画像

        Args:
            memory_text: 日志文本

        Returns:
            更新报告
        """
        report = {
            "changes": [],
            "stable_promotions": [],
            "antibias_applied": [],
            "new_entries": [],
        }

        # 1. 提取偏好
        preferences = self._extract_preferences(memory_text)

        # 2. 检查稳定性
        for pref_key, pref_value, confidence, source in preferences:
            eval_result = self.stability.record_appearance(pref_key, pref_value, confidence)

            if eval_result["action"] == "promote":
                # 进入stable层
                self._promote_to_stable(pref_key, pref_value, source, confidence)
                report["stable_promotions"].append({
                    "key": pref_key,
                    "value": pref_value,
                    "reason": eval_result["reason"]
                })

            elif eval_result["action"] == "update":
                # 更新dynamic层
                self._update_dynamic(pref_key, pref_value, source, confidence)
                report["new_entries"].append({
                    "key": pref_key,
                    "value": pref_value,
                    "layer": "dynamic"
                })

        # 3. Anti-bias 检查
        conflict_level = self.antibias.check_conflict(memory_text, self.profile)
        if conflict_level > 0.3:
            # 降低stable层置信度
            self._apply_antibias(conflict_level)
            report["antibias_applied"].append({
                "conflict_level": conflict_level,
                "action": "reduced_stable_confidence"
            })
            self.profile["meta"]["drift_detected"] += 1

        # 更新meta
        self.profile["meta"]["last_updated"] = datetime.now().isoformat()

        return report

    def _extract_preferences(self, text: str) -> List:
        """
        从文本中提取偏好

        Returns:
            [(key, value, confidence, source), ...]
        """
        preferences = []
        import re

        # 偏好模式
        patterns = [
            # 技术偏好
            (r'([^。，！？\n]{0,30}?(?:喜欢|偏好|用|写|开发|搞)[^。，！？\n]{0,30}?(Python|Java|Go|Rust|JS|TS|Node|C\+\+|Ruby|C#)[^。，！？\n]{0,20})',
             'tech_stack', 0.7),
            # 工作习惯
            (r'([^。，！？\n]{0,20}?(?:经常|习惯|总是)[^。，！？\n]{0,30})',
             'work_habit', 0.6),
            # 明确偏好声明
            (r'([^。，！？\n]{0,10}?(?:我的|我想|我要|我不)[^。，！？\n]{0,40})',
             'explicit_preference', 0.8),
            # 时间偏好
            (r'([^。，！？\n]{0,15}?(?:早上|晚上|白天|凌晨|中午)[^。，！？\n]{0,30})',
             'time_preference', 0.6),
            # 沟通风格
            (r'([^。，！？\n]{0,10}?(?:直接|简洁|详细|简短|废话)[^。，！？\n]{0,20})',
             'communication_style', 0.7),
        ]

        for pattern, pref_type, base_conf in patterns:
            matches = re.finditer(pattern, text)
            for match in matches:
                sentence = match.group(0).strip()
                if len(sentence) > 5:
                    # 提取具体值
                    value = self._extract_value_from_sentence(sentence, pref_type)
                    if value:
                        preferences.append((pref_type, value, base_conf, sentence))

        return preferences

    def _extract_value_from_sentence(self, sentence: str, pref_type: str) -> Optional[str]:
        """从句子中提取偏好值"""
        import re

        if pref_type == 'tech_stack':
            # 提取技术名称
            match = re.search(r'(Python|Java|Go|Rust|JS|TS|Node|C\+\+|Ruby|C#)', sentence)
            return match.group(1) if match else None

        elif pref_type == 'work_habit':
            match = re.search(r'(?:经常|习惯|总是)\s*([^\s，。！？]{2,20})', sentence)
            return match.group(1) if match else sentence[:20]

        elif pref_type == 'explicit_preference':
            return sentence[:30]

        elif pref_type == 'time_preference':
            match = re.search(r'(早上|晚上|白天|凌晨|中午)', sentence)
            return match.group(1) if match else None

        elif pref_type == 'communication_style':
            match = re.search(r'(直接|简洁|详细|简短|废话)', sentence)
            return match.group(1) if match else None

        return sentence[:20]

    def _promote_to_stable(self, key: str, value: str, source: str, confidence: float):
        """提升到stable层"""
        if key not in self.profile["stable"]:
            self.profile["stable"][key] = []

        # 检查是否已有该值
        existing = [e for e in self.profile["stable"][key] if e["value"] == value]
        if existing:
            existing[0]["confidence"] = confidence
            existing[0]["appearances"] += 1
            existing[0]["stable_confirmed"] = True
        else:
            self.profile["stable"][key].append({
                "value": value,
                "source": source,
                "confidence": confidence,
                "first_seen": datetime.now().isoformat(),
                "last_seen": datetime.now().isoformat(),
                "appearances": 1,
                "stable_confirmed": True,
            })

    def _update_dynamic(self, key: str, value: str, source: str, confidence: float):
        """更新dynamic层"""
        if key not in self.profile["dynamic"]:
            self.profile["dynamic"][key] = []

        # dynamic层直接覆盖
        self.profile["dynamic"][key] = [{
            "value": value,
            "source": source,
            "confidence": confidence,
            "timestamp": datetime.now().isoformat(),
        }]

    def _apply_antibias(self, conflict_level: float):
        """应用反偏见"""
        for key, entries in self.profile["stable"].items():
            if isinstance(entries, list):
                for entry in entries:
                    if isinstance(entry, dict):
                        # 降低置信度
                        entry["confidence"] = entry.get("confidence", 0.5) * 0.7
                        entry["last_seen"] = datetime.now().isoformat()

    def calculate_profile_weight(self, query: str) -> float:
        """
        计算画像一致性权重

        作为权重因子返回 0.0 - 1.0
        用于 score += consistency_with_profile * 0.2
        """
        if not query:
            return 0.5  # 无信息时返回中性

        # 检查query与stable层的匹配度
        matches = 0
        total = 0
        confidence_sum = 0.0

        for key, entries in self.profile["stable"].items():
            if isinstance(entries, list):
                for entry in entries:
                    if isinstance(entry, dict):
                        total += 1
                        conf = entry.get("confidence", 0.5)
                        confidence_sum += conf
                        if entry.get("value", "") in query:
                            matches += 1

        if total == 0:
            return 0.5  # 无stable记录时返回中性

        # 匹配度
        consistency = matches / total

        # 结合置信度
        avg_confidence = confidence_sum / total

        return 0.3 + (consistency * avg_confidence * 0.7)

    def save(self):
        """保存画像到文件"""
        if not self.profile_file.exists():
            return

        try:
            content = self.profile_file.read_text(encoding='utf-8')

            # 查找并更新画像部分
            marker = "## 🔄 画像动态更新"
            if marker in content:
                # 追加新的变化
                parts = content.split(marker)
                new_section = f"\n\n_updated: {datetime.now().isoformat()}_"
                new_section += f"\n{json.dumps(self.profile, ensure_ascii=False, indent=2)}"
                content = parts[0] + marker + new_section
            else:
                content += f"\n\n{json.dumps(self.profile, ensure_ascii=False, indent=2)}"

            self.profile_file.write_text(content, encoding='utf-8')
        except Exception as e:
            print(f"保存画像失败: {e}")

    def load(self):
        """从文件加载画像"""
        if not self.profile_file.exists():
            return

        try:
            content = self.profile_file.read_text(encoding='utf-8')
            # 尝试从文件中提取画像JSON
            import json
            # 简单查找JSON块
            start = content.rfind('{')
            end = content.rfind('}') + 1
            if start >= 0 and end > start:
                json_str = content[start:end]
                loaded = json.loads(json_str)
                if "stable" in loaded or "dynamic" in loaded:
                    self.profile = loaded
        except:
            pass


# ============ 单元测试 ============

if __name__ == "__main__":
    print("=" * 60)
    print("🧪 ProfileManager v2 测试")
    print("=" * 60)

    pm = ProfileManager()

    # Test 1: 单次随口说
    print("\n📌 Test 1: 单次随口说 → 应该是dynamic")
    report = pm.update_from_memory("坤哥说试试Go")
    print(f"  操作: {report['new_entries']}")
    print(f"  预期: 进入dynamic，不会固化")

    # Test 2: 连续出现
    print("\n📌 Test 2: 连续2天出现 → 应该是stable")
    pm.update_from_memory("坤哥用Go写后端")
    report = pm.update_from_memory("坤哥最近在用Go做项目")
    print(f"  稳定层晋升: {report['stable_promotions']}")
    print(f"  预期: 置信度足够时晋升stable")

    # Test 3: Anti-bias
    print("\n📌 Test 3: 与stable冲突 → 降低置信度")
    pm.profile["stable"] = {"tech_stack": [{"value": "Python", "confidence": 0.9}]}
    pm.profile["meta"] = {"drift_detected": 0}
    report = pm.update_from_memory("坤哥改用Java写项目了")
    conflict = pm.antibias.check_conflict("坤哥改用Java写项目了", pm.profile)
    print(f"  冲突检测: {conflict:.0%}")
    print(f"  反偏见应用: {report.get('antibias_applied', [])}")

    # Test 4: 权重因子
    print("\n📌 Test 4: 权重因子计算")
    pm.profile["stable"] = {"tech_stack": [{"value": "Go", "confidence": 0.8}]}
    weight = pm.calculate_profile_weight("坤哥用Go写后端")
    print(f"  一致性权重: {weight:.2f}")
    print(f"  预期: 高匹配时权重高(>0.5)")

    print("\n" + "=" * 60)
    print("✅ ProfileManager v2 测试完成")
    print("=" * 60)
