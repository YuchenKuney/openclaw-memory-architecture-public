#!/usr/bin/env python3
"""
多Agent协作流水线测试 - 语言生成测试

模拟场景：
1. Router Agent: 拆分任务
2. Distiller Agent: 蒸馏日志
3. Worker Agent: 并行执行
4. Verifier Agent: 结果验收
5. Orchestrator Agent: 整合汇报
"""

import sys
sys.path.insert(0, 'scripts')

from memory_protocol import MemoryProtocol, MemoryBudget, HybridSimilarity

# ==================== 模拟测试语言 ====================

TEST_CASES = [
    {
        "input": "分析这季度东南亚Shopee各国家销售数据趋势",
        "expected_subtasks": 3,  # 印尼、马来、菲律宾
        "domain": "东南亚电商"
    },
    {
        "input": "坤哥的服务器最近运行状态怎么样",
        "expected_subtasks": 2,  # 服务器状态 + 历史对比
        "domain": "服务器运维"
    },
    {
        "input": "今天天气怎么样",
        "expected_subtasks": 1,  # 单任务，不需要多Agent
        "domain": "日常查询"
    },
    {
        "input": "坤哥偏好什么样的沟通风格",
        "expected_subtasks": 1,  # 记忆检索，单Agent
        "domain": "用户画像"
    },
    {
        "input": "检查三台东南亚服务器的日志，汇总异常情况",
        "expected_subtasks": 3,  # 三台服务器并行
        "domain": "服务器运维"
    }
]

# ==================== Router Agent 模拟 ====================

class RouterAgent:
    """任务拆分Agent"""
    def __init__(self):
        self.model = "deepseek"  # 小模型，便宜快

    def parse(self, query: str) -> dict:
        """意图识别 + 任务拆分"""
        query_lower = query.lower()

        # 判断是否需要多Agent
        multi_agent_keywords = [
            "分析", "检查", "对比", "汇总",
            "各国家", "各平台", "各服务器", "多个"
        ]
        need_multi = any(kw in query for kw in multi_agent_keywords)

        # 拆分任务
        subtasks = []

        if "shopee" in query_lower and ("各国" in query or "各国家" in query or "东南亚" in query):
            countries = ["印尼", "马来", "菲律宾", "泰国", "越南"]
            for country in countries:
                if country in query:
                    subtasks.append({
                        "agent": "worker",
                        "task": f"分析{country}Shopee销售数据",
                        "domain": "电商"
                    })

        elif "服务器" in query or "日志" in query:
            if "三台" in query or "三台" in query:
                servers = ["马来西亚染发膏", "印尼地坪漆", "印尼染发膏"]
                for server in servers:
                    subtasks.append({
                        "agent": "worker",
                        "task": f"检查{server}日志",
                        "domain": "运维"
                    })
            else:
                subtasks.append({
                    "agent": "worker",
                    "task": f"检查服务器状态: {query}",
                    "domain": "运维"
                })

        elif "天气" in query:
            subtasks.append({
                "agent": "worker",
                "task": f"查询天气: {query}",
                "domain": "日常"
            })

        elif "偏好" in query or "沟通" in query:
            subtasks.append({
                "agent": "worker",
                "task": f"检索坤哥偏好记忆",
                "domain": "用户画像"
            })

        else:
            subtasks.append({
                "agent": "worker",
                "task": f"处理: {query}",
                "domain": "通用"
            })

        return {
            "original_query": query,
            "need_multi_agent": need_multi and len(subtasks) > 1,
            "subtasks": subtasks,
            "model": self.model
        }


# ==================== Distiller Agent 模拟 ====================

class DistillerAgent:
    """日志蒸馏Agent"""
    def __init__(self):
        self.model = "qwen"  # 中文理解好

    def distill(self, raw_text: str, max_output: int = 500) -> str:
        """
        模拟蒸馏：10k tokens → 1k tokens

        真实逻辑应该是：
        - 提取关键事件（错误、异常、峰值）
        - 去除重复日志
        - 汇总统计信息
        """
        lines = raw_text.split('\n')
        key_events = []
        error_count = 0
        warning_count = 0

        for line in lines:
            line_lower = line.lower()
            if 'error' in line_lower or '失败' in line_lower or '异常' in line_lower:
                error_count += 1
                if len(key_events) < 5:  # 只保留前5个关键错误
                    key_events.append(f"[错误] {line.strip()[:100]}")
            elif 'warn' in line_lower or '警告' in line_lower:
                warning_count += 1
            elif '连接' in line_lower or '超时' in line_lower:
                if len(key_events) < 10:
                    key_events.append(f"[连接] {line.strip()[:100]}")

        summary = f"""日志蒸馏摘要:
- 总日志行数: {len(lines)}
- 错误事件: {error_count}次
- 警告事件: {warning_count}次
- 关键事件:
"""
        for event in key_events[:5]:
            summary += f"  {event}\n"

        return summary


# ==================== Worker Agent 模拟 ====================

class WorkerAgent:
    """并行任务执行Agent"""
    def __init__(self):
        self.model = "minimax"

    def execute(self, task: dict, context: str = "") -> dict:
        """执行子任务"""
        return {
            "task": task["task"],
            "domain": task["domain"],
            "result": f"[{task['domain']}] 处理完成: {task['task']}",
            "tokens_used": 500,  # 模拟
            "status": "success"
        }


# ==================== Verifier Agent 模拟 ====================

class VerifierAgent:
    """结果验收Agent"""
    def __init__(self):
        self.model = "minimax"
        self.threshold = 0.6

    def verify(self, results: list) -> dict:
        """检查结果一致性和质量"""
        if not results:
            return {"pass": False, "reason": "无结果"}

        # 检查是否有冲突
        conflicts = []
        for i, r1 in enumerate(results):
            for r2 in results[i+1:]:
                # 简单冲突检测：同一domain的结果应该一致
                if r1.get("domain") == r2.get("domain"):
                    if r1.get("result", "")[:50] != r2.get("result", "")[:50]:
                        # 不同结果，可能是冲突
                        pass

        return {
            "pass": True,
            "result_count": len(results),
            "conflicts": conflicts,
            "confidence": 0.85
        }


# ==================== Orchestrator Agent 模拟 ====================

class OrchestratorAgent:
    """整合汇报Agent"""
    def __init__(self):
        self.model = "gpt-4o"  # 主模型

    def orchestrate(self, query: str, results: list, verifier_result: dict) -> str:
        """整合 + 二次验收"""
        output = f"""# 分析报告: {query}

## 执行摘要
- 处理子任务: {len(results)}个
- 验收结果: {"通过" if verifier_result['pass'] else '需复查'}
- 置信度: {verifier_result.get('confidence', 0):.0%}

## 详细结果
"""
        for r in results:
            output += f"""
### {r['domain']} - {r['task']}
{r['result']}
- 消耗: {r.get('tokens_used', 0)} tokens
"""

        if verifier_result.get('conflicts'):
            output += """
## ⚠️ 注意事项
检测到结果存在潜在冲突，请核实:
"""
            for c in verifier_result['conflicts']:
                output += f"- {c}\n"

        return output


# ==================== Full Pipeline ====================

class MultiAgentPipeline:
    """完整多Agent流水线"""

    def __init__(self):
        self.router = RouterAgent()
        self.distiller = DistillerAgent()
        self.worker = WorkerAgent()
        self.verifier = VerifierAgent()
        self.orchestrator = OrchestratorAgent()

        # Token统计
        self.total_tokens = 0
        self.cost_saved = 0

    def run(self, query: str, raw_logs: str = None) -> dict:
        """
        完整流程:
        1. Router: 拆分任务
        2. Distiller: 蒸馏日志（可选）
        3. Workers: 并行执行
        4. Verifier: 验收
        5. Orchestrator: 整合
        """
        print(f"\n{'='*60}")
        print(f"🚀 多Agent流水线启动")
        print(f"{'='*60}")
        print(f"输入: {query}")

        # Step 1: Router
        print(f"\n📋 Step 1: Router Agent (模型: {self.router.model})")
        plan = self.router.parse(query)
        print(f"  需要多Agent: {'是' if plan['need_multi_agent'] else '否'}")
        print(f"  子任务数: {len(plan['subtasks'])}")
        for i, t in enumerate(plan['subtasks'], 1):
            print(f"    {i}. [{t['domain']}] {t['task']}")
        self.total_tokens += 100  # Router消耗

        # Step 2: Distiller（可选）
        distilled_context = ""
        if raw_logs and len(raw_logs) > 1000:
            print(f"\n🔄 Step 2: Distiller Agent (模型: {self.distiller.model})")
            print(f"  原始日志: {len(raw_logs)} chars")
            distilled_context = self.distiller.distill(raw_logs)
            print(f"  蒸馏后: {len(dististilled_context)} chars")
            print(f"  压缩比: {len(raw_logs)/len(distilled_context):.1f}x")
            self.total_tokens += 200
            self.cost_saved += (len(raw_logs) - len(distilled_context)) * 0.001

        # Step 3: Workers 并行
        print(f"\n⚡ Step 3: Worker Agents ({len(plan['subtasks'])}个并行, 模型: {self.worker.model})")
        worker_results = []
        for t in plan['subtasks']:
            result = self.worker.execute(t, distilled_context)
            worker_results.append(result)
            print(f"  ✅ [{result['domain']}] {result['result'][:50]}...")
            self.total_tokens += result.get('tokens_used', 500)

        # Step 4: Verifier
        print(f"\n🔍 Step 4: Verifier Agent (模型: {self.verifier.model})")
        verifier_result = self.verifier.verify(worker_results)
        print(f"  验收结果: {'通过 ✅' if verifier_result['pass'] else '需复查 ❌'}")
        print(f"  结果数: {verifier_result['result_count']}")
        print(f"  置信度: {verifier_result.get('confidence', 0):.0%}")
        self.total_tokens += 150

        # Step 5: Orchestrator
        print(f"\n📝 Step 5: Orchestrator Agent (模型: {self.orchestrator.model})")
        final_output = self.orchestrator.orchestrate(query, worker_results, verifier_result)
        print(f"  报告长度: {len(final_output)} chars")
        self.total_tokens += 300

        print(f"\n{'='*60}")
        print(f"📊 Token统计")
        print(f"{'='*60}")
        print(f"  总消耗: {self.total_tokens} tokens")
        print(f"  节省Tokens(蒸馏): ~{int(self.cost_saved)}")
        print(f"  预估费用: ${self.total_tokens * 0.00001:.4f}")

        return {
            "query": query,
            "plan": plan,
            "results": worker_results,
            "verification": verifier_result,
            "output": final_output,
            "tokens": self.total_tokens,
            "cost_saved": self.cost_saved
        }


# ==================== 测试执行 ====================

def main():
    print("="*60)
    print("🧪 多Agent协作流水线测试")
    print("="*60)

    pipeline = MultiAgentPipeline()

    # 测试1: 多Agent任务
    print("\n" + "="*60)
    print("🧪 测试1: 东南亚电商分析")
    print("="*60)
    result1 = pipeline.run(
        "分析这季度东南亚Shopee各国家销售数据趋势",
        raw_logs=None
    )
    print(f"\n📋 最终报告预览:\n{result1['output'][:300]}...")

    # 测试2: 带日志的任务
    print("\n" + "="*60)
    print("🧪 测试2: 服务器日志分析（含蒸馏）")
    print("="*60)

    # 模拟日志
    mock_logs = """
2026-04-17 10:00:01 INFO Server started on port 8080
2026-04-17 10:05:23 ERROR Database connection failed: timeout
2026-04-17 10:05:24 ERROR Connection pool exhausted
2026-04-17 10:10:00 WARN Slow query detected: SELECT * FROM orders
2026-04-17 10:15:30 ERROR API request failed: 503 Service Unavailable
2026-04-17 10:20:00 INFO Health check passed
2026-04-17 10:25:15 ERROR Connection timeout to 154.64.253.249
2026-04-17 10:30:00 WARN Memory usage at 85%
2026-04-17 10:35:22 ERROR Failed to process webhook: invalid signature
2026-04-17 10:40:00 INFO Backup completed successfully
""" * 50  # 放大模拟

    result2 = pipeline.run(
        "检查三台东南亚服务器的日志，汇总异常情况",
        raw_logs=mock_logs
    )
    print(f"\n📋 最终报告:\n{result2['output']}")

    # 测试3: 单Agent任务（应该跳过多Agent）
    print("\n" + "="*60)
    print("🧪 测试3: 简单查询（应单Agent）")
    print("="*60)
    result3 = pipeline.run("坤哥偏好什么样的沟通风格")
    print(f"  需要多Agent: {result3['plan']['need_multi_agent']}")
    print(f"  子任务数: {len(result3['plan']['subtasks'])}")

    print("\n" + "="*60)
    print("✅ 多Agent流水线测试完成")
    print("="*60)


if __name__ == "__main__":
    main()
