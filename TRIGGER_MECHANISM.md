## 🔴 PRIMARY 信号（模型体感）— 核心触发

> 来自坤哥的洞察：retrieval_miss_rate ↑ 和 response_latency ↑ 
> 比 token 计数更真实——这是模型自己"体感"到的变慢

| 信号 | 阈值 | 说明 |
|------|------|------|
| **retrieval_miss_rate** | > 30% | 检索结果为空或质量太低，模型"找不到想要的" |
| **response_latency_ratio** | > 1.5x | 当前延迟 / 基准延迟，模型推理变慢 |

## 🟡 SECONDARY 信号（容量预警）

| 信号 | 阈值 | 说明 |
|------|------|------|
| **context_pressure** | > 70% | 上下文使用占比（辅助确认，不单独触发） |

## ⚖️ 裁决逻辑

```
if PRIMARY 触发:
    if SECONDARY 确认:  → EVICT_CONFIRMED（双重确认，换出6条）
    else:               → EVICT_PRIMARY（相信体感，换出4条）
elif SECONDARY 触发:
    → MONITOR（监控，不换出）
else:
    → OK（正常）
```

---

_核心洞察来自坤哥：模型体感信号 > token 数字_
