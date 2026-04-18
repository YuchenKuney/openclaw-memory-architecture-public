"""
编排Agent (Orchestrator)

职责：
1. 接收 Listener 的分析结果
2. 任务拆解
3. 分发给执行Agent
4. 收集结果
5. 提交验证Agent

特点：编排者，不做具体执行
"""

from typing import Dict, List, Optional
from common.message_types import (
    ListenerOutput, OrchestratorOutput, Task, TaskResult,
    VerificationResult, PipelineContext, RoutingType, IntentType
)
import time


class TaskDecomposer:
    """
    任务分解器

    将用户问题拆解成原子任务
    """

    # 任务模板
    TASK_TEMPLATES = {
        "sales_query": {
            "agent": "researcher",
            "description": "查询销售数据",
            "includes": ["销售额", "订单量", "趋势"]
        },
        "order_query": {
            "agent": "researcher",
            "description": "查询订单状态",
            "includes": ["订单号", "状态", "时间"]
        },
        "server_check": {
            "agent": "worker",
            "description": "检查服务器状态",
            "includes": ["运行状态", "错误日志", "性能指标"]
        },
        "content_create": {
            "agent": "creator",
            "description": "创建内容",
            "includes": ["文案", "视觉素材"]
        },
        "data_analysis": {
            "agent": "researcher",
            "description": "分析数据",
            "includes": ["数据概览", "趋势分析", "建议"]
        },
        "file_operation": {
            "agent": "worker",
            "description": "文件操作",
            "includes": ["操作结果"]
        }
    }

    def decompose(self, listener_output: ListenerOutput) -> List[Task]:
        """
        任务分解

        Args:
            listener_output: Listener的分析结果

        Returns:
            任务列表
        """
        tasks = []
        intent = listener_output.intent
        entities = listener_output.entities

        # 根据意图类型分解任务
        if intent == IntentType.QUERY:
            tasks = self._decompose_query(entities)
        elif intent == IntentType.ACTION:
            tasks = self._decompose_action(entities)
        elif intent == IntentType.COMPLAINT:
            tasks = self._decompose_complaint(entities)
        elif intent == IntentType.EMERGENCY:
            tasks = self._decompose_emergency(entities)

        return tasks

    def _decompose_query(self, entities: Dict) -> List[Task]:
        """分解查询类任务"""
        tasks = []

        # 销售查询
        if any(k in entities for k in ["country", "product", "platform"]):
            tasks.append(Task(
                agent_type="researcher",
                description=f"查询销售数据: {entities}",
                context={"query_type": "sales", **entities},
                expected_output={"format": "data_summary"}
            ))

        # 订单查询
        if "order_id" in entities:
            tasks.append(Task(
                agent_type="researcher",
                description=f"查询订单 {entities.get('order_id')} 状态",
                context={"query_type": "order", "order_id": entities.get("order_id")},
                expected_output={"format": "order_status"}
            ))

        # 服务器检查
        if any(k in str(entities) for k in ["server", "服务器"]):
            tasks.append(Task(
                agent_type="worker",
                description="检查服务器状态",
                context={"check_type": "server_health"},
                expected_output={"format": "server_status"}
            ))

        # 默认数据分析
        if not tasks:
            tasks.append(Task(
                agent_type="researcher",
                description="执行数据分析",
                context={"query_type": "general", **entities},
                expected_output={"format": "analysis"}
            ))

        return tasks

    def _decompose_action(self, entities: Dict) -> List[Task]:
        """分解执行类任务"""
        return [Task(
            agent_type="worker",
            description=f"执行任务: {entities}",
            context=entities,
            expected_output={"format": "operation_result"}
        )]

    def _decompose_complaint(self, entities: Dict) -> List[Task]:
        """分解投诉类任务"""
        return [
            Task(
                agent_type="researcher",
                description="调查投诉原因",
                context={"task_type": "investigate", **entities},
                expected_output={"format": "investigation"}
            ),
            Task(
                agent_type="creator",
                description="生成处理方案",
                context={"task_type": "solution"},
                expected_output={"format": "solution"}
            )
        ]

    def _decompose_emergency(self, entities: Dict) -> List[Task]:
        """分解紧急任务"""
        return [
            Task(
                agent_type="worker",
                description="立即检查系统状态",
                context={"priority": "high", **entities},
                expected_output={"format": "emergency_status"}
            )
        ]


class Orchestrator:
    """
    编排Agent主类

    职责：
    1. 接收 Listener 输出
    2. 任务拆解
    3. 分发任务（这里模拟，实际会调用具体Agent）
    4. 收集结果
    5. 提交验证
    """

    def __init__(self):
        self.decomposer = TaskDecomposer()

    def plan(self, listener_output: ListenerOutput) -> OrchestratorOutput:
        """
        任务规划

        Args:
            listener_output: Listener的分析结果

        Returns:
            OrchestratorOutput: 包含任务列表
        """
        tasks = self.decomposer.decompose(listener_output)

        # 确定执行模式
        if len(tasks) <= 1:
            mode = RoutingType.SEQUENTIAL
        elif len(tasks) == 2:
            mode = RoutingType.PARALLEL
        else:
            mode = RoutingType.PARALLEL

        # 估算时间
        estimated_time = len(tasks) * 2000  # 每个任务约2秒

        return OrchestratorOutput(
            tasks=tasks,
            execution_mode=mode,
            estimated_time_ms=estimated_time
        )

    def dispatch_tasks(self, plan: OrchestratorOutput) -> List[TaskResult]:
        """
        分发任务并收集结果

        这里模拟实际执行过程
        实际实现中会调用具体的Agent

        Returns:
            任务结果列表
        """
        results = []

        for task in plan.tasks:
            # 模拟执行
            result = self._execute_task(task)
            results.append(result)

        return results

    def _execute_task(self, task: Task) -> TaskResult:
        """
        执行单个任务（真实调用MiniMax大模型）
        """
        import time, json, urllib.request, urllib.error
        start = time.time()

        # MiniMax API配置
        API_KEY = "sk-cp-QRI7FFwxiGyHSR7S_7LTpkEjbtClAtAdWpHvBg3Iun-6BcLkxGU16vvvQuIjFVms4tCbNy3TnkMSw3z73j7ApkWMji3c7g_1d-YHCTSnEZNFSfeDqmT7TKk"
        API_URL = "https://api.minimaxi.com/anthropic/v1/messages"

        # 构建prompt
        if task.agent_type == "researcher":
            system_prompt = """你是一个专业的电商数据分析研究员。
根据用户的问题，执行深度研究并给出有价值的分析。

⚠️ 重要：你需要基于你的知识直接给出分析结果，不要询问用户更多信息。
如果你对某些具体数据不确定，可以基于行业通用趋势给出一个大致的分析，并在结论中说明数据来源和不确定性。

要求：
1. 直接给出分析结果，不要询问更多信息
2. 提供具体的数据和趋势分析
3. 如有具体产品/市场数据，请给出详情
4. 分析要有逻辑性，结论要有数据支撑"""
            user_prompt = f"问题：{task.description}\n\n请直接给出分析结果，不需要询问更多问题。"
            if task.context:
                user_prompt += f"\n\n背景信息：{json.dumps(task.context, ensure_ascii=False)}"

        elif task.agent_type == "worker":
            system_prompt = """你是一个专业的系统运维工程师。
根据用户的需求，执行具体的系统操作或分析。

要求：
1. 提供具体的操作步骤或分析结果
2. 如有系统状态数据，请给出详情
3. 操作结果要明确，结论要可靠"""
            user_prompt = f"任务：{task.description}\n\n请执行："

        elif task.agent_type == "creator":
            system_prompt = """你是一个专业的内容创作者。
根据用户的需求，生成高质量的内容。

要求：
1. 内容要符合品牌调性
2. 语言要地道、有吸引力
3. 结构要清晰"""
            user_prompt = f"需求：{task.description}\n\n请创作内容："

        else:
            system_prompt = "你是一个AI助手，请回答用户的问题。"
            user_prompt = f"{task.description}"

        try:
            headers = {
                "Authorization": f"Bearer {API_KEY}",
                "Content-Type": "application/json",
                "anthropic-version": "2023-06-01"
            }

            payload = {
                "model": "MiniMax-M2.7",
                "max_tokens": 2048,
                "system": system_prompt,
                "messages": [{"role": "user", "content": user_prompt}]
            }

            req = urllib.request.Request(
                API_URL,
                data=json.dumps(payload).encode(),
                headers=headers,
                method="POST"
            )

            with urllib.request.urlopen(req, timeout=60) as response:
                result_data = json.loads(response.read().decode())
                # 提取text类型的content
                content_blocks = result_data.get("content", [])
                result_text = ""
                for block in content_blocks:
                    if block.get("type") == "text":
                        result_text = block.get("text", "")
                        break
                    elif block.get("type") == "thinking":
                        # 跳过thinking，保留text
                        continue

            elapsed_ms = int((time.time() - start) * 1000)

            return TaskResult(
                task_id=task.task_id,
                agent=task.agent_type,
                result=result_text,
                confidence=0.85,
                execution_time_ms=elapsed_ms,
                model_used="MiniMax-M2.7"
            )

        except urllib.error.HTTPError as e:
            error_body = e.read().decode() if e.fp else str(e)
            elapsed_ms = int((time.time() - start) * 1000)
            return TaskResult(
                task_id=task.task_id,
                agent=task.agent_type,
                result=f"API调用失败：{e.code} - {error_body[:500]}",
                confidence=0.3,
                execution_time_ms=elapsed_ms,
                model_used="MiniMax-M2.7",
                error=str(e)
            )
        except Exception as e:
            elapsed_ms = int((time.time() - start) * 1000)
            return TaskResult(
                task_id=task.task_id,
                agent=task.agent_type,
                result=f"执行失败：{str(e)}",
                confidence=0.2,
                execution_time_ms=elapsed_ms,
                model_used="MiniMax-M2.7",
                error=str(e)
            )

    def integrate_results(self, results: List[TaskResult]) -> str:
        """
        整合多个任务结果
        """
        if not results:
            return "未获取到任何结果"

        lines = ["【综合分析结果】\n"]
        for r in results:
            lines.append(f"## {r.agent.upper()} 执行结果")
            lines.append(r.result)
            lines.append(f"置信度: {r.confidence:.0%}")
            lines.append("")

        return "\n".join(lines)


# ============ 单元测试 ============

if __name__ == "__main__":
    from listener.intent_classifier import Listener

    print("=" * 60)
    print("🧪 Orchestrator 测试")
    print("=" * 60)

    listener = Listener()
    orchestrator = Orchestrator()

    test_messages = [
        "马来西亚Shopee染发膏最近销售怎么样？",
        "帮我查一下订单123456789",
        "服务器好像有问题",
    ]

    for msg in test_messages:
        print(f"\n📝 输入: {msg}")

        # 1. Listener分析
        listener_out = listener.listen(msg)
        print(f"  意图: {listener_out.intent.value}")
        print(f"  实体: {listener_out.entities}")

        # 2. 任务规划
        if listener_out.should_pipeline:
            plan = orchestrator.plan(listener_out)
            print(f"  任务数: {len(plan.tasks)}")
            print(f"  执行模式: {plan.execution_mode.value}")

            # 3. 分发执行
            results = orchestrator.dispatch_tasks(plan)
            print(f"  执行结果: {len(results)}个任务完成")

            # 4. 整合
            integrated = orchestrator.integrate_results(results)
            print(f"  整合预览: {integrated[:80]}...")

    print("\n✅ Orchestrator 测试完成")
