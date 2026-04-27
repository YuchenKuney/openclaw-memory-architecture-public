# Clawkeeper 核心机制详解

## 定位
AI Agent 的安全护盾，监控 workspace 文件变化，实时风险评估，主动通知用户

## 核心架构
```
AI 操作文件 → inotify 监控 → 风险检测 → 拦截/暂停/通知
```

## 风险等级

| 等级 | 操作 | 处理方式 |
|------|------|---------|
| 🔴 CRITICAL | 删除核心文件（AGENTS/SOUL/MEMORY） | **立即备份+放行** |
| 🚨 HIGH | 修改核心文件、删除核心目录 | **立即拦截** |
| ⚠️ MEDIUM | push 到公共仓、修改 .gitignore | **暂停+审核** |
| 📝 LOW | 创建/修改非核心文件 | 记录日志 |
| ✅ SAFE | 普通操作 | 放行 |

## 核心文件

| 文件 | 职责 |
|------|------|
| `watcher.py` | inotify 实时监控文件变化 |
| `detector.py` | 正则+LLM语义双层风险检测 |
| `notifier.py` | 飞书卡片通知 |
| `auditor.py` | 审计日志生成 |
| `interceptor.py` | 拦截器（已废弃，功能并入detector） |

## 双层检测架构

### 第一层：正则规则（高速）
```python
RULES = {
    ("AGENTS.md", "DELETE"): RiskLevel.CRITICAL,
    ("~/.gitcredentials", "READ"): RiskLevel.HIGH,
    ("authorized_keys", "MODIFY"): RiskLevel.HIGH,
}
```

### 第二层：LLM 语义判断（兜底）
- 对 MEDIUM/LOW 风险操作进行深度语义分析
- 识别正则无法检测的隐蔽攻击（社会工程、指令注入、token泄露）
- 攻击类型：token_leak / instruction_injection / social_engineering / data_exfiltration

## 4条绝对铁律

1. **铁律一**：核心文件删除 → 自动备份后才放行
2. **铁律二**：Token读取 → 立即告警
3. **铁律三**：公共仓push → 暂停+审核
4. **铁律四**：cron-events目录 → 正常行为，降级处理

## 与Web4的关系

| 层面 | 监控系统 | 监控对象 |
|------|---------|---------|
| 网络层 | IronRuler | URL访问、Cookie注入 |
| 文件层 | Clawkeeper | workspace文件变化 |

两者互相补强，不是替代关系
