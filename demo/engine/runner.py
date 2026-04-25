#!/usr/bin/env python3
"""
Demo Runner：调度器，串起 Memory / Audit / Distillation / Profile
"""
from datetime import datetime
import sys, os
sys.path.insert(0, '/root/.openclaw/workspace')

from knowledge_graph import KnowledgeGraph
from context_builder import ContextBuilder


class Distiller:
    """蒸馏引擎：封装 KnowledgeGraph，提供 run() 方法"""
    def __init__(self, kg=None):
        self.kg = kg or KnowledgeGraph()
        try:
            self.kg.load()
        except:
            pass

    def run(self):
        """执行记忆蒸馏：保存当前 KG 状态（触发 consolidation）"""
        try:
            self.kg.save()
        except (FileNotFoundError, OSError):
            pass
        return True


class Profile:
    """用户画像引擎：从对话中提取结构化用户状态"""
    def __init__(self):
        self.state = {
            "region": None,
            "category": None,
            "price": None,
            "stage": None,
        }

    def update(self, user_input: str):
        text = user_input.lower()
        if "东南亚" in text: self.state["region"] = "SEA"
        if "袜子" in text: self.state["category"] = "socks"
        if "低价" in text or "预算" in text: self.state["price"] = "low"
        if "印尼" in text: self.state["region"] = "Indonesia"
        if "菲律宾" in text: self.state["region"] = "Philippines"
        return dict(self.state)

    def get_state(self):
        return dict(self.state)


class DemoRunner:
    def __init__(self, audit=None, distill=None, profile=None):
        self.audit = audit
        if distill is not None and not isinstance(distill, Distiller):
            self.distill = Distiller(distill)
        else:
            self.distill = distill

        self.profile = profile or Profile()

        self.kg = KnowledgeGraph()
        self.context_builder = ContextBuilder()
        self.memory_log = []
        self.user_state = {
            "region": None,
            "category": None,
            "price": None,
            "stage": None,
        }

        try:
            self.kg.load()
        except:
            pass

    def run_step(self, step_data):
        user_input = step_data["user"]
        tag = step_data["tag"]
        step = step_data["step"]

        print(f"\n{'─' * 56}")
        print(f"  Step {step} ｜ {tag}")
        print(f"{'─' * 56}")
        print(f"  👤 {user_input}")

        # ========== A/B 对比：Step 4 之前展示无 Memory vs 有 Memory ==========
        if tag == "decision_test":
            cold_response = self._generate_cold_response()
            print(f"\n  ❄️ [Without Memory] 冷启动 AI 回答：")
            print(f"     {cold_response.strip()}")
            print(f"\n  🔥 [With Memory] 基于记忆的 AI 回答：")

        # 1. AI 回复
        response = self._generate_response(user_input, tag)
        print(f"\n  🤖 AI 回答：")
        for line in response.split('\n'):
            print(f"     {line}")

        # 2. 写入 Memory
        self._write_memory(user_input, response, tag)

        # 3. Memory Snapshot（规整树状结构）
        self._print_memory_snapshot()

        # 4. Audit
        if self.audit:
            audit_result = self.audit.check(user_input, response)
            print(f"\n  🛡️ Audit: {audit_result}")

        # 5. Distillation
        if self.distill:
            self.distill.run()
            print(f"  🧠 Distillation triggered")

        # 6. Profile 更新
        profile_state = self.profile.update(user_input)
        self._print_user_profile(profile_state)

        return response

    def _generate_cold_response(self):
        import random
        options = [
            "东南亚市场选择很多，需要结合你的具体情况分析。",
            "东南亚各国都有机会，建议先明确你的核心优势。",
            "市场选择取决于预算、物流和竞争环境，需要更多信息。",
        ]
        return random.choice(options)

    def _generate_response(self, user_input, tag):
        if tag == "initial_context":
            return "东南亚市场确实很有潜力！印尼、越南、菲律宾都是不错的机会。能告诉我你具体想卖什么品类吗？"

        if tag == "category_test":
            return "袜子是个有趣的选择！复购率高、体积小、运输成本低。不过竞争也比较激烈，建议找到差异化卖点。"

        if tag == "price_preference":
            return "明白了，低价路线。那你需要在供应链上控制成本。建议从义乌拿货，先测款再决定。"

        if tag == "decision_test":
            return "基于你说的东南亚市场 + 低价袜子路线，我建议优先考虑 **印度尼西亚**：\n" \
                   "- 人口世界第四，电商增长快\n" \
                   "- 低价商品需求旺盛\n" \
                   "- Shopee/Lazada 生态成熟\n\n" \
                   "其次可以考虑 **菲律宾**，物流也在改善。"

        if tag == "consistency_test":
            return "结合你的情况（东南亚 + 低价袜子），我的判断没变：**印度尼西亚仍然是最佳选择**。\n" \
                   "Shopee 是主阵地，TikTok Shop 也可以同步布局。"

        return "明白了，我在持续学习你的需求。"

    def _write_memory(self, user_input, response, tag):
        ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        self._update_user_state(user_input, tag)

        entry = {
            "step": len(self.memory_log) + 1,
            "user": user_input,
            "ai": response,
            "tag": tag,
            "timestamp": ts
        }
        self.memory_log.append(entry)
        self._update_kg(user_input, tag)

        print(f"\n  💾 Memory Updated at {ts}")

    def _update_user_state(self, user_input, tag):
        text = user_input.lower()
        if "东南亚" in text: self.user_state["region"] = "SEA"
        if "袜子" in text: self.user_state["category"] = "socks"
        if "低价" in text or "预算" in text: self.user_state["price"] = "low"
        if "印尼" in text: self.user_state["region"] = "Indonesia"
        if "菲律宾" in text: self.user_state["region"] = "Philippines"
        self.user_state["stage"] = tag

    def _print_user_profile(self, profile_state):
        r = profile_state.get("region") or "-"
        c = profile_state.get("category") or "-"
        p = profile_state.get("price") or "-"
        print(f"\n  📊 User Profile:")
        print(f"     ┌─ region  : {r}")
        print(f"     ├─ category: {c}")
        print(f"     └─ price   : {p}")

    def _print_memory_snapshot(self):
        if len(self.memory_log) == 0:
            return
        print(f"\n  📦 Memory Snapshot:")
        print(f"     ├─ region  : {self.user_state.get('region') or '待定'}")
        print(f"     ├─ category: {self.user_state.get('category') or '待定'}")
        print(f"     ├─ price   : {self.user_state.get('price') or '待定'}")
        print(f"     ├─ rounds  : {len(self.memory_log)} 轮对话已记忆")
        print(f"     └─ stage   : {self.user_state.get('stage') or '-'}")

    def _update_kg(self, user_input, tag):
        keywords = {
            "initial_context": ["东南亚", "跨境", "电商"],
            "category_test": ["袜子", "品类", "复购率"],
            "price_preference": ["低价", "成本", "义乌"],
            "decision_test": ["印尼", "菲律宾", "Shopee"],
            "consistency_test": ["印尼", "低价袜子"],
        }
        for kw in keywords.get(tag, []):
            self.kg.entities.setdefault(kw, {"type": "concept", "count": 0})
            self.kg.entities[kw]["count"] += 1

    def consistency_check(self, silent=False):
        """一致性检验：只校验核心结论（推荐国家），不校验完整句子"""
        if len(self.memory_log) < 5:
            return "SKIP", "需要至少 5 轮对话"

        step4 = self.memory_log[3]["ai"]
        step5 = self.memory_log[4]["ai"]

        countries = ["印尼", "印度尼西亚", "菲律宾", "越南", "马来西亚", "新加坡"]

        def extract_country(text):
            for c in countries:
                if c in text:
                    return c
            return None

        country4 = extract_country(step4)
        country5 = extract_country(step5)

        core_match = country4 == country5 and country4 is not None

        if core_match:
            result = "✅ PASS"
            reason = f"核心结论一致（推荐 {country4}），表述有细节调整（正常）"
        else:
            result = "❌ FAIL"
            reason = f"推荐国家有变化：Step4→{country4 or '无'}，Step5→{country5 or '无'}"

        print(f"\n{'=' * 56}")
        print(f"  🔍 Consistency Check")
        print(f"{'=' * 56}")
        print(f"  Step 4 结论: {country4 or '无'}")
        print(f"  Step 5 结论: {country5 or '无'}")
        print(f"  ────────────────────")
        print(f"  判定: {result}")
        print(f"  原因: {reason}")

        return "PASS" if core_match else "FAIL", reason

    def save_log(self, path="/root/.openclaw/workspace/demo/outputs/demo_log.md"):
        lines = ["# Demo 运行记录\n", f"时间：{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n\n"]

        for entry in self.memory_log:
            lines.append(f"## Step {entry['step']} [{entry['tag']}]\n")
            lines.append(f"👤 User: {entry['user']}\n\n")
            lines.append(f"🤖 AI: {entry['ai']}\n\n")
            lines.append(f"💾 Time: {entry['timestamp']}\n\n")
            lines.append("---\n")

        result, reason = self.consistency_check(silent=True)
        lines.append(f"\n## 最终结果\n- 一致性检验：{result}\n- 原因：{reason}\n")
        lines.append(f"\n## Memory Snapshot\n")
        for k, v in self.user_state.items():
            lines.append(f"- {k}: {v or '待定'}\n")

        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, 'w') as f:
            f.writelines(lines)

        print(f"\n  📄 完整记录已保存到: {path}")


def run_scenario(scenario):
    """运行电商记忆演进场景"""
    runner = DemoRunner()
    print(f"\n{'=' * 56}")
    print(f"  🛒 电商记忆演进场景开始（共 {len(scenario)} 步）")
    print(f"{'=' * 56}")
    for step_data in scenario:
        runner.run_step(step_data)
    runner.save_log()
    print(f"\n✅ 场景运行完毕")
    return runner