#!/usr/bin/env python3
"""
Demo Runner：调度器，串起 Memory / Audit / Distillation / Profile
"""
from datetime import datetime
import sys, os
sys.path.insert(0, '/root/.openclaw/workspace')

from memory_watchdog import MemoryWatchdog
from knowledge_graph import KnowledgeGraph
from context_builder import ContextBuilder


class DemoRunner:
    def __init__(self, audit=None, distill=None, profile=None):
        self.audit = audit
        self.distill = distill
        self.profile = profile

        # Memory 系统初始化
        self.kg = KnowledgeGraph()
        self.context_builder = ContextBuilder()
        self.memory_log = []

        # 加载已有记忆
        try:
            self.kg.load()
        except:
            pass

    def run_step(self, step_data):
        user_input = step_data["user"]
        tag = step_data["tag"]
        step = step_data["step"]

        print(f"\n👤 User: {user_input}")

        # 1. 调用 AI（模拟，真实环境接入 NVIDIA NIM）
        response = self._generate_response(user_input, tag)
        print(f"🤖 AI: {response}")

        # 2. 写入 Memory（多层记忆）
        self._write_memory(user_input, response, tag)

        # 3. Audit（Clawkeeper 安全审计）
        if self.audit:
            audit_result = self.audit.check(user_input, response)
            print(f"🛡️ Audit: {audit_result}")

        # 4. Distillation（蒸馏）
        if self.distill:
            distilled = self.distill.run()
            print(f"🧠 Distillation triggered")

        # 5. Profile 更新
        if self.profile:
            profile_state = self.profile.update(user_input)
            print(f"📊 Profile: {profile_state}")

        return response

    def _generate_response(self, user_input, tag):
        """生成 AI 回复（demo 用内置逻辑，比赛时替换为真实 AI）"""
        # 从 memory 上下文构建回答
        context = self.context_builder.build_context()
        history = "\n".join([f"User: {m['user']}\nAI: {m['ai']}" for m in self.memory_log[-3:]])

        # 简单规则引擎（模拟 AI 逐步变聪明）
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
        """写入多层记忆"""
        ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        entry = {
            "step": len(self.memory_log) + 1,
            "user": user_input,
            "ai": response,
            "tag": tag,
            "timestamp": ts
        }
        self.memory_log.append(entry)

        # 写入 kg 实体
        self._update_kg(user_input, tag)

        print(f"💾 Memory Updated at {ts}")

    def _update_kg(self, user_input, tag):
        """更新知识图谱"""
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

    def consistency_check(self):
        """一致性检验"""
        if len(self.memory_log) < 5:
            return "SKIP", "需要至少 5 轮对话"

        first_answer = self.memory_log[3]["ai"]  # Step 4
        second_answer = self.memory_log[4]["ai"]  # Step 5

        # 检查是否推荐印尼
        consistent = "印尼" in first_answer and "印尼" in second_answer
        reason = f"Step 4 vs Step 5 均推荐印尼" if consistent else f"答案有变化需检查"

        print(f"\n🔍 Consistency Check:")
        print(f"  Step 4: {first_answer[:60]}...")
        print(f"  Step 5: {second_answer[:60]}...")
        print(f"  Result: {'✅ PASS' if consistent else '❌ FAIL'}")
        print(f"  Reason: {reason}")

        return "PASS" if consistent else "FAIL", reason

    def save_log(self, path="/root/.openclaw/workspace/demo/outputs/demo_log.md"):
        """保存 demo 运行结果"""
        lines = ["# Demo 运行记录\n", f"时间：{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n\n"]

        for entry in self.memory_log:
            lines.append(f"## Step {entry['step']} [{entry['tag']}]\n")
            lines.append(f"👤 User: {entry['user']}\n\n")
            lines.append(f"🤖 AI: {entry['ai']}\n\n")
            lines.append(f"💾 Time: {entry['timestamp']}\n\n")
            lines.append("---\n")

        result, reason = self.consistency_check()
        lines.append(f"\n## 最终结果\n- 一致性检验：{result}\n- 原因：{reason}\n")

        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, 'w') as f:
            f.writelines(lines)

        print(f"\n📄 完整记录已保存到: {path}")