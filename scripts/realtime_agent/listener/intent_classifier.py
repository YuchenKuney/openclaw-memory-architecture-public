"""
监听Agent (Listener)

职责：
1. 接收用户消息
2. 意图快速分类
3. 提取关键实体
4. 判断是否需要触发流水线

特点：轻量、极速 (<100ms)
"""

import re
from typing import Dict, Tuple
from common.message_types import (
    ListenerOutput, IntentType, RoutingType
)


class IntentClassifier:
    """
    意图分类器

    规则 + 轻量模式匹配，快速判断意图
    不需要调用大模型，纯规则实现
    """

    # 紧急关键词
    EMERGENCY_KEYWORDS = [
        "紧急", "快", "立刻", "马上", "急", "critical",
        "宕机", "挂了", "崩溃", "down"
    ]

    # 投诉关键词
    COMPLAINT_KEYWORDS = [
        "投诉", "差评", "不满意", "垃圾", "烂", "骗子",
        "退款", "退货", "赔偿"
    ]

    # 执行类关键词
    ACTION_KEYWORDS = [
        "帮我", "做", "执行", "运行", "创建", "删除",
        "修改", "更新", "发送", "通知"
    ]

    # 查询类关键词
    QUERY_KEYWORDS = [
        "怎么样", "如何", "多少", "什么", "有没有",
        "查询", "看看", "检查", "分析", "统计",
        "最近", "数据", "销售", "订单"
    ]

    # 闲聊类关键词
    CHAT_KEYWORDS = [
        "你好", "hi", "hello", "嗨", "在吗",
        "谢谢", "辛苦了", "哈哈", "笑死"
    ]

    # 实体提取模式
    ENTITY_PATTERNS = {
        "order_id": r"订单[号]?[:：]?\s*([A-Z0-9]{6,})",
        "product": r"(染发膏|口红|面膜|衣服|鞋子|手机)",
        "country": r"(马来西亚|印尼|泰国|越南|新加坡|菲律宾)",
        "platform": r"(Shopee|TikTok Shop|Lazada)",
        "date_range": r"(今天|昨天|本周|上周|本月|近\d+天|近一个月)",
        "money": r"(\d+[\.,]?\d*)\s*(元|美元|USD|RMB|马币|印尼盾)",
    }

    def __init__(self, pipeline_threshold: float = 0.6):
        """
        Args:
            pipeline_threshold: 置信度低于此值不触发流水线
        """
        self.pipeline_threshold = pipeline_threshold

    def classify(self, message: str) -> ListenerOutput:
        """
        意图分类

        Args:
            message: 用户原始消息

        Returns:
            ListenerOutput
        """
        message = message.strip()
        original = message  # 保存原始用于调试

        # 1. 意图分类
        intent, intent_confidence = self._classify_intent(message)

        # 2. 实体提取
        entities = self._extract_entities(message)

        # 3. 路由判断
        should_pipeline, routing = self._should_pipeline(intent, message, entities)

        # 4. 综合置信度
        confidence = min(intent_confidence, 0.95)

        return ListenerOutput(
            intent=intent,
            entities=entities,
            should_pipeline=should_pipeline,
            confidence=confidence,
            routing=routing,
            raw_message=original,
        )

    def _classify_intent(self, message: str) -> Tuple[IntentType, float]:
        """意图分类 + 置信度"""
        msg_lower = message.lower()

        # 检查紧急
        if any(kw in msg_lower for kw in self.EMERGENCY_KEYWORDS):
            return IntentType.EMERGENCY, 0.95

        # 检查投诉
        if any(kw in msg_lower for kw in self.COMPLAINT_KEYWORDS):
            return IntentType.COMPLAINT, 0.85

        # 检查执行类
        action_count = sum(1 for kw in self.ACTION_KEYWORDS if kw in msg_lower)
        query_count = sum(1 for kw in self.QUERY_KEYWORDS if kw in msg_lower)
        chat_count = sum(1 for kw in self.CHAT_KEYWORDS if kw in msg_lower)

        # 综合判断（优先QUERY，因为"帮我分析"本质是分析需求）
        # 关键："帮我"后面跟分析/查询类动词 → QUERY
        help_keywords = ["帮我", "帮我查", "帮我看看"]
        is_help_query = any(kw in msg_lower for kw in help_keywords) and query_count >= 1

        if is_help_query:
            return IntentType.QUERY, 0.85
        elif query_count >= 2:
            return IntentType.QUERY, 0.85
        elif chat_count >= 1 and query_count == 0 and action_count == 0:
            return IntentType.CHAT, 0.9
        elif action_count >= 2:
            return IntentType.ACTION, 0.8
        elif action_count >= 1 and query_count == 0:
            return IntentType.ACTION, 0.65
        elif query_count >= 1:
            return IntentType.QUERY, 0.7
        elif action_count >= 1:
            return IntentType.ACTION, 0.65

        # 默认闲聊
        return IntentType.CHAT, 0.5

    def _extract_entities(self, message: str) -> Dict:
        """提取实体"""
        entities = {}

        for entity_name, pattern in self.ENTITY_PATTERNS.items():
            match = re.search(pattern, message)
            if match:
                entities[entity_name] = match.group(1) if match.groups() else match.group(0)

        return entities

    def _should_pipeline(self, intent: IntentType, message: str,
                         entities: Dict) -> Tuple[bool, RoutingType]:
        """
        判断是否需要流水线
        """
        # 紧急情况直接处理
        if intent == IntentType.EMERGENCY:
            return True, RoutingType.SEQUENTIAL

        # 闲聊直接回复
        if intent == IntentType.CHAT:
            return False, RoutingType.DIRECT

        # 投诉需要处理
        if intent == IntentType.COMPLAINT:
            return True, RoutingType.SEQUENTIAL

        # 有明确实体的查询 → 流水线
        if intent == IntentType.QUERY and len(entities) >= 1:
            return True, RoutingType.PARALLEL

        # 执行类 → 流水线
        if intent == IntentType.ACTION:
            return True, RoutingType.SEQUENTIAL

        # 模糊消息 → 尝试流水线
        if intent == IntentType.QUERY:
            return True, RoutingType.PARALLEL

        return False, RoutingType.DIRECT


class Listener:
    """
    监听Agent主类

    对外接口：
    - listen(message) -> ListenerOutput
    """

    def __init__(self):
        self.classifier = IntentClassifier()
        self.reply_gen = SimpleReplyGenerator()

    def listen(self, message: str) -> ListenerOutput:
        """
        处理用户消息

        Args:
            message: 用户消息

        Returns:
            ListenerOutput
        """
        return self.classifier.classify(message)

    def should_respond_immediately(self, output: ListenerOutput) -> Tuple[bool, str]:
        """
        判断是否直接回复

        Returns:
            (是否直接回复, 回复内容)
        """
        if not output.should_pipeline:
            # 直接回复
            if output.intent == IntentType.CHAT:
                return True, self.reply_gen.generate(output.raw_message)
            elif output.confidence < 0.6:
                return True, "抱歉，我没太理解，能再说一遍吗？"

        return False, ""


# ============ 简单回复生成 ============

class SimpleReplyGenerator:
    """简单回复生成器"""

    GREETINGS = ["你好", "hi", "hello", "嗨", "在的"]
    THANKS = ["谢谢", "感谢", "谢了"]

    @staticmethod
    def generate(message: str) -> str:
        """根据消息生成简单回复"""
        msg_lower = message.lower().strip()

        if any(g in msg_lower for g in ["你好", "hi", "hello", "嗨"]):
            return "你好！有什么可以帮你的？"
        if any(t in msg_lower for t in ["谢谢", "感谢"]):
            return "不客气！😊"
        if "在吗" in msg_lower or "在嘛" in msg_lower:
            return "在的！说吧～"

        return ""  # 需要流水线处理


# ============ 单元测试 ============

if __name__ == "__main__":
    listener = Listener()

    test_cases = [
        "马来西亚Shopee染发膏最近销售怎么样？",
        "你好",
        "帮我查一下昨天的订单",
        "服务器挂了！紧急",
        "太差了，要投诉",
        "谢谢",
    ]

    print("=" * 60)
    print("🧪 Listener 测试")
    print("=" * 60)

    for msg in test_cases:
        output = listener.listen(msg)
        should_direct, reply = listener.should_respond_immediately(output)

        print(f"\n输入: {msg}")
        print(f"  意图: {output.intent.value}")
        print(f"  置信度: {output.confidence:.0%}")
        print(f"  实体: {output.entities if output.entities else '无'}")
        print(f"  流水线: {'✅' if output.should_pipeline else '❌'}")
        print(f"  路由: {output.routing.value}")
        if should_direct:
            print(f"  直接回复: {reply}")

    print("\n✅ Listener 测试完成")
