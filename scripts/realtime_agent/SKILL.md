# Realtime Agent Skill

## 用途
实时多Agent流水线 - 作为主Agent的前置过滤器

## 接口

### analyze_intent(message)
分析消息意图，返回意图分类和实体。

### should_use_pipeline(message)
判断是否应该触发完整流水线。

### process_message(message)
完整处理消息，返回结果。

## 消息类型
- `direct_reply`: 简单闲聊，直接回复
- `pipeline_answer`: 复杂任务，流水线处理
- `user_consult`: 需要询问用户

## 集成位置
`/root/.openclaw/workspace/scripts/realtime_agent/`
