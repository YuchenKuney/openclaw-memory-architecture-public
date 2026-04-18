# Channel Map - 渠道映射（公开版）

> ⚠️ 本文件已清理敏感信息，仅供参考

_Updated: 2026-04-15_

---

## 渠道类型

| 类型 | 说明 |
|------|------|
| 飞书群 | 用于团队通知 |
| 私信 | 用于私聊 |
| Webhook | 用于消息推送 |

---

## 配置模板

### 飞书群
```json
{
  "chat_id": "oc_XXXXXXXXXXXXXXXX",
  "用途": "群用途描述"
}
```

### 飞书 Webhook
```json
{
  "webhook": "https://open.feishu.cn/open-apis/bot/v2/hook/XXXXXXXX-XXXX-XXXX-XXXX-XXXXXXXXXXXX",
  "用途": "webhook用途描述"
}
```

---

## 时区说明

- 任务执行时间：北京时间 (UTC+8)
- Heartbeat检测：UTC时间

---

## 最佳实践

1. **敏感信息不要写入公开仓库**
2. **使用环境变量存储token**
3. **定期轮换webhook**
4. **限制群权限**

---

_注意：本文件为模板，敏感信息已替换为占位符_
