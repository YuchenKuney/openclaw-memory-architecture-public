# Rule System - 规则管理系统

> 自动从日志中提取、分类、管理规则

## 核心概念

### 规则结构
```yaml
id: rule_xxx
text: "邮件必须先读正文再汇报"
category: error        # preference | behavior | error
source: "2026-04-14"   # 来源日期
confidence: 0.95       # 置信度 0-1
usage_count: 5         # 使用次数
last_used: "2026-04-16"
status: active         # active | deprecated
```

### 规则分类
| 分类 | 说明 | 示例 |
|------|------|------|
| preference | 用户偏好 | "坤哥喜欢简洁回复" |
| behavior | 行为规则 | "每天早上9点发日报" |
| error | 错误教训 | "邮件必须先读正文" |

### 置信度计算
```
confidence = (成功次数 × 0.6) + (来源权威性 × 0.3) + (时效性 × 0.1)

- 成功次数: 使用规则5次都成功 = 1.0
- 来源权威性: 坤哥明确说 = 1.0, 自己推断 = 0.5
- 时效性: 7天内 = 1.0, 30天内 = 0.7, 更久 = 0.4
```

### 淘汰机制
- 置信度 < 0.3 → 标记deprecated
- 90天未使用 → 归档
- 被坤哥明确否定 → 立即淘汰

### 合并机制
同类规则 → 合并为更通用的表述

## 文件结构
```
rules/
├── index.md          # 规则总索引
├── preference.md     # 用户偏好规则
├── behavior.md      # 行为规则
├── error.md         # 错误教训规则
└── archive/         # 淘汰规则归档
```

## 流程
```
日志 → 提炼 → 提取规则 → 分类 → 计算置信度 → 入库
                                                      ↓
规则被使用 → 验证成功 → 置信度↑ → 或 置信度↓ → 淘汰
```

## 使用
```bash
python3 rule_manager.py --extract    # 从日志提取规则
python3 rule_manager.py --check     # 检查规则状态
python3 rule_manager.py --merge     # 合并同类规则
python3 rule_manager.py --cleanup   # 清理低置信度规则
```

---

_设计: 2026-04-16_
