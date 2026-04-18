"""
验证Agent (Verifier)

职责：
1. 交叉验证结果
2. 检查是否符合用户提问
3. 质量评分
4. 不合格 → 打回重做（最多2次）
5. 2次都不行 → 询问用户

关键规则（坤哥指定）：
- 最多打回2次
- 2次都不行 → 发给用户，询问是否需要重新审计
- 记住用户的选择，动态调整
"""

from typing import List, Optional, Tuple
from dataclasses import dataclass, field
from common.message_types import (
    TaskResult, VerificationResult, PipelineContext, ListenerOutput
)
import re


@dataclass
class VerificationRule:
    """验证规则"""
    name: str
    weight: float  # 权重
    check_func: callable  # 检查函数


class QualityVerifier:
    """
    质量验证器

    多维度检查结果质量
    """

    def __init__(self):
        self.rules = [
            VerificationRule(
                name="相关性",
                weight=0.4,
                check_func=self._check_relevance
            ),
            VerificationRule(
                name="完整性",
                weight=0.3,
                check_func=self._check_completeness
            ),
            VerificationRule(
                name="准确性",
                weight=0.3,
                check_func=self._check_accuracy
            ),
        ]

    def verify(self,
               original_question: str,
               results: List[TaskResult],
               user_context: Optional[dict] = None) -> VerificationResult:
        """
        验证结果质量

        Args:
            original_question: 用户原始问题
            results: 执行结果列表
            user_context: 用户上下文（用于个性化验证）

        Returns:
            VerificationResult
        """
        if not results:
            return VerificationResult(
                passed=False,
                score=0,
                issues=["没有获取到任何结果"],
                summary="无法验证：结果为空"
            )

        # 合并所有结果
        combined = "\n".join([r.result for r in results])

        # 执行各项检查
        scores = {}
        issues = []

        for rule in self.rules:
            rule_score, rule_issues = rule.check_func(
                original_question, combined, results, user_context
            )
            scores[rule.name] = rule_score * rule.weight
            if rule_issues:
                issues.extend(rule_issues)

        # 计算总分 (0-10)
        total_score = sum(scores.values()) * 10

        # 判断是否通过
        passed = total_score >= 6.0 and len([i for i in issues if "严重" in i]) == 0

        return VerificationResult(
            passed=passed,
            score=round(total_score, 1),
            issues=issues,
            summary=self._generate_summary(total_score, issues)
        )

    def _check_relevance(self, question: str, result: str,
                         results: List[TaskResult],
                         user_context: Optional[dict]) -> Tuple[float, List[str]]:
        """检查相关性：结果是否回答了用户的问题"""
        issues = []

        # 提取问题关键词
        question_keywords = set(re.findall(r'[\w]+', question.lower()))
        question_keywords = {w for w in question_keywords if len(w) >= 2}

        # 提取结果关键词
        result_keywords = set(re.findall(r'[\w]+', result.lower()))
        result_keywords = {w for w in result_keywords if len(w) >= 2}

        # 计算重叠率
        if question_keywords:
            overlap = len(question_keywords & result_keywords)
            relevance = overlap / len(question_keywords)
        else:
            relevance = 1.0

        # 检查是否答非所问
        anti_keywords = ["无法", "不知道", "没有", "错误"]
        if any(k in result.lower() for k in anti_keywords):
            if relevance < 0.3:
                issues.append("⚠️ 严重：答非所问")

        score = min(1.0, relevance + 0.3)  # 基础分0.3
        return score, issues

    def _check_completeness(self, question: str, result: str,
                            results: List[TaskResult],
                            user_context: Optional[dict]) -> Tuple[float, List[str]]:
        """检查完整性：是否遗漏关键信息"""
        issues = []

        # 检查问题中的实体是否都在结果中
        entities_to_check = {
            "country": r"(马来西亚|印尼|泰国|越南|新加坡)",
            "platform": r"(Shopee|TikTok|Lazada)",
            "product": r"(染发膏|口红|面膜)",
            "date": r"(今天|昨天|本周|本月|近\d+天)",
        }

        missing = []
        for entity_type, pattern in entities_to_check.items():
            if re.search(pattern, question):
                if not re.search(pattern, result):
                    missing.append(entity_type)

        if missing:
            issues.append(f"⚠️ 缺失信息: {', '.join(missing)}")

        # 检查结果长度
        if len(result) < 50 and len(results) == 1:
            issues.append("⚠️ 结果内容过少")
            score = 0.5
        else:
            score = max(0.4, 1.0 - len(missing) * 0.2)

        return score, issues

    def _check_accuracy(self, question: str, result: str,
                        results: List[TaskResult],
                        user_context: Optional[dict]) -> Tuple[float, List[str]]:
        """检查准确性：数据/事实是否正确"""
        issues = []

        # 检查置信度
        avg_confidence = sum(r.confidence for r in results) / len(results)
        if avg_confidence < 0.6:
            issues.append(f"⚠️ 置信度较低: {avg_confidence:.0%}")

        # 检查是否有错误标记
        error_keywords = ["错误", "失败", "error", "failed"]
        if any(k in result.lower() for k in error_keywords):
            # 检查是否是目标错误（用户询问问题）还是执行错误
            if "错误" in question or "问题" in question:
                pass  # 用户在问错误，可以提及
            else:
                issues.append("⚠️ 结果中包含错误信息")

        score = avg_confidence if avg_confidence else 0.7
        return score, issues

    def _generate_summary(self, score: float, issues: List[str]) -> str:
        """生成摘要"""
        if score >= 8.0:
            return f"质量优秀 ({score:.1f}/10)"
        elif score >= 6.0:
            return f"质量合格 ({score:.1f}/10)"
        elif score >= 4.0:
            return f"需要改进 ({score:.1f}/10)"
        else:
            return f"质量不达标 ({score:.1f}/10)"


class Verifier:
    """
    验证Agent主类

    关键逻辑：
    - 最多打回2次
    - 2次都不行 → 询问用户
    - 记住用户选择，动态调整
    """

    MAX_RETRIES = 2  # 坤哥指定：最多2次

    # 用户偏好存储（实际应持久化）
    _user_preferences = {}

    def __init__(self):
        self.quality_verifier = QualityVerifier()

    def verify(self,
               original_message: str,
               results: List[TaskResult],
               context: PipelineContext) -> Tuple[VerificationResult, bool]:
        """
        验证结果

        Args:
            original_message: 用户原始消息
            results: 执行结果
            context: 流水线上下文

        Returns:
            (验证结果, 是否需要询问用户)
        """
        # 检查用户偏好
        user_id = context.message_id  # 实际应该用真实user_id

        # 如果用户之前拒绝过重试，直接不再重试
        if self._user_preferences.get(user_id, {}).get("skip_retry"):
            return VerificationResult(
                passed=False,
                score=3.0,
                issues=["用户之前选择跳过重试"],
                summary="用户偏好：跳过重试"
            ), True  # 需要询问用户

        # 执行验证
        verification = self.quality_verifier.verify(
            original_message, results, context.user_preferences
        )

        # 如果通过
        if verification.passed:
            return verification, False

        # 如果不通过，检查重试次数
        current_retry = context.verification.retry_count if context.verification else 0

        if current_retry < self.MAX_RETRIES:
            # 可以重试
            return verification, False
        else:
            # 2次都不行，询问用户
            return verification, True

    def ask_user_for_retry(self, context: PipelineContext) -> str:
        """
        生成询问用户的消息

        Returns:
            询问消息
        """
        verification = context.verification
        issues = verification.issues if verification else []

        msg = f"我尝试了 {self.MAX_RETRIES} 次，但结果仍不完美：\n\n"
        msg += "发现的问题：\n"
        for issue in issues[:3]:
            msg += f"• {issue}\n"

        msg += f"\n当前得分：{verification.score:.1f}/10\n\n"
        msg += "是否需要我重新审计这个问题？还是您可以补充一些信息？"

        return msg

    def process_user_feedback(self,
                              context: PipelineContext,
                              approved: bool) -> None:
        """
        处理用户反馈

        Args:
            context: 流水线上下文
            approved: True=同意重试, False=拒绝
        """
        user_id = context.message_id  # 实际应该用真实user_id

        # 记录用户选择
        if "retry_history" not in self._user_preferences:
            self._user_preferences[user_id] = {"retry_history": []}

        self._user_preferences[user_id]["retry_history"].append({
            "approved": approved,
            "timestamp": context.created_at,
            "score": context.verification.score if context.verification else 0
        })

        # 如果用户连续2次拒绝，跳过重试
        history = self._user_preferences[user_id]["retry_history"]
        if len(history) >= 2 and not history[-1]["approved"] and not history[-2]["approved"]:
            self._user_preferences[user_id]["skip_retry"] = True

    @classmethod
    def reset_user_preference(cls, user_id: str) -> None:
        """重置用户偏好"""
        if user_id in cls._user_preferences:
            del cls._user_preferences[user_id]


# ============ 单元测试 ============

if __name__ == "__main__":
    from orchestrator.task_planner import Orchestrator
    from listener.intent_classifier import Listener
    from common.message_types import PipelineContext

    print("=" * 60)
    print("🧪 Verifier 测试")
    print("=" * 60)

    listener = Listener()
    orchestrator = Orchestrator()
    verifier = Verifier()

    # 测试1: 正常通过
    print("\n📌 Test 1: 正常通过")
    msg = "马来西亚Shopee染发膏销售怎么样？"
    listener_out = listener.listen(msg)
    plan = orchestrator.plan(listener_out)
    results = orchestrator.dispatch_tasks(plan)

    context = PipelineContext(
        message_id="test_001",
        original_message=msg
    )
    context.listener = listener_out
    context.orchestrator = plan

    verification, need_ask = verifier.verify(msg, results, context)
    print(f"  验证结果: {'✅ 通过' if verification.passed else '❌ 不通过'}")
    print(f"  得分: {verification.score}/10")
    print(f"  需要询问: {'是' if need_ask else '否'}")
    print(f"  问题: {verification.issues if verification.issues else '无'}")

    # 测试2: 模拟低质量结果
    print("\n📌 Test 2: 低质量结果（模拟）")
    bad_results = [
        TaskResult(
            task_id="bad_001",
            agent="researcher",
            result="不知道",
            confidence=0.2
        )
    ]

    context2 = PipelineContext(
        message_id="test_002",
        original_message="马来西亚Shopee染发膏销售怎么样？"
    )

    verification2, need_ask2 = verifier.verify(msg, bad_results, context2)
    print(f"  验证结果: {'✅ 通过' if verification2.passed else '❌ 不通过'}")
    print(f"  得分: {verification2.score}/10")
    print(f"  问题: {verification2.issues[:2]}")

    # 测试3: 询问消息生成
    print("\n📌 Test 3: 询问消息")
    ask_msg = verifier.ask_user_for_retry(context2)
    print(f"  消息预览: {ask_msg[:80]}...")

    # 测试4: 用户反馈
    print("\n📌 Test 4: 用户反馈")
    verifier.process_user_feedback(context2, approved=False)
    print(f"  用户选择已记录")

    print("\n✅ Verifier 测试完成")
