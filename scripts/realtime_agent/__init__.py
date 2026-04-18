"""
实时多Agent流水线 - OpenClaw集成接口

提供标准化调用接口，供主Agent使用
"""

import sys
from pathlib import Path

# 确保可以导入子模块
sys.path.insert(0, str(Path(__file__).parent))

from pipeline import RealtimePipeline
from common.message_types import ListenerOutput, IntentType

# 全局pipeline实例（复用）
_pipeline = None


def get_pipeline() -> RealtimePipeline:
    """获取pipeline实例（单例）"""
    global _pipeline
    if _pipeline is None:
        _pipeline = RealtimePipeline()
    return _pipeline


def analyze_intent(message: str) -> dict:
    """
    分析消息意图（轻量级调用）

    Args:
        message: 用户消息

    Returns:
        {
            "intent": str,  # chat/query/action/complaint/emergency
            "confidence": float,
            "should_pipeline": bool,
            "entities": dict,
            "routing": str  # direct/parallel/sequential
        }
    """
    pipeline = get_pipeline()
    listener = pipeline.listener
    output = listener.listen(message)

    return {
        "intent": output.intent.value,
        "confidence": output.confidence,
        "should_pipeline": output.should_pipeline,
        "entities": output.entities,
        "routing": output.routing.value,
        "raw_message": output.raw_message
    }


def should_use_pipeline(message: str) -> tuple:
    """
    判断是否应该使用流水线

    Returns:
        (should_pipeline: bool, intent_info: dict)
    """
    info = analyze_intent(message)

    # 简单规则
    should = info["should_pipeline"]

    # 但如果置信度很低，不触发
    if info["confidence"] < 0.5:
        should = False

    return should, info


def process_message(message: str) -> dict:
    """
    处理消息（完整流水线）

    Args:
        message: 用户消息

    Returns:
        {
            "type": str,  # direct_reply / pipeline_answer / user_consult
            "content": str,
            "intent": dict,
            "stats": dict
        }
    """
    pipeline = get_pipeline()
    result = pipeline.process(message)

    return {
        "type": result["type"],
        "content": result["content"],
        "intent": analyze_intent(message),
        "stats": pipeline.get_stats()
    }


def handle_feedback(context: dict, approved: bool) -> dict:
    """
    处理用户反馈

    Args:
        context: pipeline返回的context
        approved: 用户是否同意重试

    Returns:
        新的处理结果
    """
    from common.message_types import PipelineContext

    pipeline = get_pipeline()

    # 重建context对象
    ctx = PipelineContext(
        message_id=context.get("message_id", "unknown"),
        original_message=context.get("original_message", ""),
    )

    return pipeline.handle_user_feedback(ctx, approved)


# ============ 快速测试 ============

if __name__ == "__main__":
    test_messages = [
        "你好",
        "马来西亚Shopee染发膏销售怎么样？",
        "帮我查一下订单123456",
    ]

    print("=" * 50)
    print("🧪 Realtime Agent 快速测试")
    print("=" * 50)

    for msg in test_messages:
        should, info = should_use_pipeline(msg)
        print(f"\n📝 {msg}")
        print(f"   意图: {info['intent']} ({info['confidence']:.0%})")
        print(f"   流水线: {'✅' if should else '❌'}")
        print(f"   路由: {info['routing']}")
        if info['entities']:
            print(f"   实体: {info['entities']}")

    print("\n" + "=" * 50)
