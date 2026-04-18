"""
实时多Agent流水线 - 主编排器

整合 Listener + Orchestrator + Verifier
实现完整流程
"""

from common.message_types import (
    ListenerOutput, OrchestratorOutput, TaskResult,
    VerificationResult, PipelineContext
)
from listener.intent_classifier import Listener, SimpleReplyGenerator
from orchestrator.task_planner import Orchestrator
from verifier.quality_gate import Verifier


class RealtimePipeline:
    """
    实时多Agent流水线主类

    流程：
    1. Listener 接收消息 → 意图分类
    2. Orchestrator 任务拆解 → 分发执行
    3. Verifier 验证结果
    4. 不通过 → 重试（最多2次）
    5. 2次不行 → 询问用户
    6. 通过 → 回复用户
    """

    def __init__(self):
        self.listener = Listener()
        self.orchestrator = Orchestrator()
        self.verifier = Verifier()
        self.reply_generator = SimpleReplyGenerator()

        # 流水线统计
        self.stats = {
            "total": 0,
            "direct_reply": 0,
            "pipeline_used": 0,
            "passed_first": 0,
            "retried": 0,
            "user_consulted": 0,
        }

    def process(self, message: str, user_id: str = "default") -> dict:
        """
        处理用户消息

        Args:
            message: 用户消息
            user_id: 用户ID

        Returns:
            {
                "type": "direct_reply" | "pipeline_answer" | "user_consult",
                "content": str,
                "context": PipelineContext
            }
        """
        self.stats["total"] += 1

        # Step 1: Listener 接收并分析
        listener_output = self.listener.listen(message)

        # 检查是否直接回复
        should_direct, simple_reply = self.listener.should_respond_immediately(listener_output)

        if should_direct and simple_reply:
            self.stats["direct_reply"] += 1
            return {
                "type": "direct_reply",
                "content": simple_reply,
                "context": None
            }

        # Step 2: 创建上下文
        context = PipelineContext(
            message_id=f"{user_id}_{self.stats['total']}",
            original_message=message,
            listener=listener_output
        )

        # Step 3: Orchestrator 任务规划
        plan = self.orchestrator.plan(listener_output)
        context.orchestrator = plan

        # Step 4: 分发任务并执行
        results = self.orchestrator.dispatch_tasks(plan)
        for r in results:
            context.add_result(r)

        # Step 5: Verifier 验证
        verification = None
        retry_count = 0

        while retry_count <= Verifier.MAX_RETRIES:
            verification, need_ask = self.verifier.verify(
                message, results, context
            )

            if verification.passed:
                break

            if need_ask or retry_count >= Verifier.MAX_RETRIES:
                break

            # 需要重试
            retry_count += 1
            context.verification = verification
            self.stats["retried"] += 1

            # 重新执行任务（模拟，实际会重新调用Agent）
            results = self.orchestrator.dispatch_tasks(plan)

        context.verification = verification

        # Step 6: 判断返回类型
        if not verification.passed and retry_count >= Verifier.MAX_RETRIES:
            # 2次都不行，询问用户
            self.stats["user_consulted"] += 1
            ask_message = self.verifier.ask_user_for_retry(context)

            return {
                "type": "user_consult",
                "content": ask_message,
                "context": context
            }

        # 通过，整合结果
        self.stats["passed_first"] += 1
        self.stats["pipeline_used"] += 1

        final_answer = self.orchestrator.integrate_results(results)

        # 添加验证摘要
        if verification.issues:
            final_answer += f"\n\n【质量提示】\n验证得分: {verification.score}/10\n"
            for issue in verification.issues[:2]:
                final_answer += f"• {issue}\n"

        context.final_answer = final_answer

        return {
            "type": "pipeline_answer",
            "content": final_answer,
            "context": context
        }

    def handle_user_feedback(self, context: PipelineContext, approved: bool) -> dict:
        """
        处理用户反馈

        Args:
            context: 流水线上下文
            approved: 用户是否同意重试

        Returns:
            新的处理结果
        """
        # 记录用户选择
        self.verifier.process_user_feedback(context, approved)

        if approved:
            # 用户同意重试，重新执行
            return self.process(context.original_message,
                              user_id=context.message_id.split("_")[0])
        else:
            # 用户拒绝，返回当前最好结果
            return {
                "type": "user_declined",
                "content": context.get_combined_result() or "抱歉，无法提供满意答案",
                "context": context
            }

    def get_stats(self) -> dict:
        """获取流水线统计"""
        return {
            **self.stats,
            "pass_rate": f"{self.stats['passed_first'] / max(self.stats['pipeline_used'], 1) * 100:.1f}%"
        }


# ============ CLI 测试 ============

def main():
    import sys

    pipeline = RealtimePipeline()

    if len(sys.argv) > 1:
        # 命令行模式
        message = " ".join(sys.argv[1:])
        print(f"\n📤 输入: {message}")

        result = pipeline.process(message)
        print(f"\n📥 回复类型: {result['type']}")
        print(f"\n📝 内容:\n{result['content']}")

        if result['context']:
            print(f"\n📊 统计: {pipeline.get_stats()}")
    else:
        # 交互模式
        print("=" * 60)
        print("🧪 实时多Agent流水线 - 交互测试")
        print("=" * 60)
        print("输入消息测试，输入 'quit' 退出\n")

        while True:
            try:
                msg = input("\n👤 你: ").strip()
                if not msg:
                    continue
                if msg.lower() in ["quit", "exit", "退出"]:
                    break

                print(f"\n📤 输入: {msg}")

                result = pipeline.process(msg)

                print(f"📥 类型: {result['type']}")
                print(f"\n📝 回复:\n{result['content'][:300]}")
                if len(result['content']) > 300:
                    print("... (截断)")

                print(f"\n📊 统计: {pipeline.get_stats()}")

            except KeyboardInterrupt:
                break

        print("\n\n✅ 测试完成")


if __name__ == "__main__":
    main()
