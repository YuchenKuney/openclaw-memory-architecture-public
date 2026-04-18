"""
实时多Agent流水线 - 消息格式定义

所有Agent之间传递的消息格式统一。
"""

from dataclasses import dataclass, field
from typing import Dict, List, Optional, Any
from datetime import datetime
from enum import Enum
import uuid


class IntentType(Enum):
    """意图类型"""
    CHAT = "chat"           # 闲聊
    QUERY = "query"         # 查询
    ACTION = "action"       # 执行任务
    COMPLAINT = "complaint" # 投诉
    EMERGENCY = "emergency" # 紧急


class RoutingType(Enum):
    """路由类型"""
    DIRECT = "direct"       # 直接回复
    PARALLEL = "parallel"   # 并行分发
    SEQUENTIAL = "sequential" # 串行执行


class TaskStatus(Enum):
    """任务状态"""
    PENDING = "pending"
    RUNNING = "running"
    DONE = "done"
    FAILED = "failed"
    REVOKED = "revoked"


# ============ Listener → Orchestrator ============

@dataclass
class ListenerOutput:
    """监听Agent输出"""
    intent: IntentType
    entities: Dict[str, Any]  # 提取的实体
    should_pipeline: bool      # 是否需要流水线
    confidence: float          # 置信度 0-1
    routing: RoutingType      # 路由建议
    raw_message: str           # 原始消息
    message_id: str = field(default_factory=lambda: str(uuid.uuid4())[:8])
    timestamp: str = field(default_factory=lambda: datetime.now().isoformat())

    def to_dict(self) -> Dict:
        return {
            "type": "listener_output",
            "intent": self.intent.value,
            "entities": self.entities,
            "should_pipeline": self.should_pipeline,
            "confidence": self.confidence,
            "routing": self.routing.value,
            "raw_message": self.raw_message,
            "message_id": self.message_id,
            "timestamp": self.timestamp,
        }


# ============ Orchestrator → Worker ============

@dataclass
class Task:
    """任务描述"""
    task_id: str = field(default_factory=lambda: f"task_{str(uuid.uuid4())[:6]}")
    agent_type: str = ""      # worker/researcher/creator
    description: str = ""
    context: Dict = field(default_factory=dict)
    expected_output: Dict = field(default_factory=dict)
    depends_on: List[str] = field(default_factory=list)  # 依赖的任务ID
    priority: str = "normal"  # high/normal/low

    def to_dict(self) -> Dict:
        return {
            "type": "task",
            "task_id": self.task_id,
            "agent_type": self.agent_type,
            "description": self.description,
            "context": self.context,
            "expected_output": self.expected_output,
            "depends_on": self.depends_on,
            "priority": self.priority,
        }


@dataclass
class OrchestratorOutput:
    """编排器输出"""
    plan_id: str = field(default_factory=lambda: f"plan_{str(uuid.uuid4())[:6]}")
    tasks: List[Task] = field(default_factory=list)
    execution_mode: RoutingType = RoutingType.PARALLEL
    estimated_time_ms: int = 0

    def to_dict(self) -> Dict:
        return {
            "type": "orchestrator_output",
            "plan_id": self.plan_id,
            "tasks": [t.to_dict() for t in self.tasks],
            "execution_mode": self.execution_mode.value,
            "estimated_time_ms": self.estimated_time_ms,
        }


# ============ Worker → Verifier ============

@dataclass
class TaskResult:
    """任务执行结果"""
    task_id: str
    agent: str
    result: str
    evidence: List[str] = field(default_factory=list)
    confidence: float = 0.5
    execution_time_ms: int = 0
    model_used: str = ""
    error: Optional[str] = None

    def to_dict(self) -> Dict:
        return {
            "type": "task_result",
            "task_id": self.task_id,
            "agent": self.agent,
            "result": self.result,
            "evidence": self.evidence,
            "confidence": self.confidence,
            "execution_time_ms": self.execution_time_ms,
            "model_used": self.model_used,
            "error": self.error,
        }


# ============ Verifier → Orchestrator ============

@dataclass
class VerificationResult:
    """验证结果"""
    passed: bool
    score: float           # 1-10分
    issues: List[str] = field(default_factory=list)
    revised_answer: Optional[str] = None
    summary: str = ""
    retry_count: int = 0

    def to_dict(self) -> Dict:
        return {
            "type": "verification_result",
            "passed": self.passed,
            "score": self.score,
            "issues": self.issues,
            "revised_answer": self.revised_answer,
            "summary": self.summary,
            "retry_count": self.retry_count,
        }


# ============ Pipeline Context ============

@dataclass
class PipelineContext:
    """流水线上下文"""
    message_id: str
    original_message: str
    listener: Optional[ListenerOutput] = None
    orchestrator: Optional[OrchestratorOutput] = None
    task_results: List[TaskResult] = field(default_factory=list)
    verification: Optional[VerificationResult] = None
    final_answer: Optional[str] = None
    user_approval_requested: bool = False
    user_approved_retry: Optional[bool] = None  # None=未询问, True=同意, False=拒绝

    # 用户偏好（动态调整）
    user_preferences: Dict = field(default_factory=dict)

    created_at: str = field(default_factory=lambda: datetime.now().isoformat())

    def add_result(self, result: TaskResult):
        self.task_results.append(result)

    def get_combined_result(self) -> str:
        return "\n\n".join([r.result for r in self.task_results])
