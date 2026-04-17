# HEARTBEAT.md

## 每日定时提醒（主动推送，不要等坤哥问）

### ⏰ 早上 9:00（UTC 01:00）提醒
- 检查今天有没有重要事项（续费提醒、服务器状态等）
- 坤哥记忆力不好，主动提醒，不要等他自己想起来

### ⏰ 早上 9:00 发送电商早报
- 使用 web_search 搜索以下内容（每次搜索英文关键词）：
  1. "Shopee Southeast Asia e-commerce today"（3条）
  2. "TikTok Shop Southeast Asia e-commerce today"（3条）
  3. "Southeast Asia ecommerce [月份] [年份]"（2条）
- 将搜索结果整理成日报，格式如下：
```
📰 东南亚电商早报 [日期]

━━━━━━━━━━━━━━━━━
🇮🇩 🇲🇾 🇹🇭 🇵🇭 🇻🇳
━━━━━━━━━━━━━━━━━

【🛒 Shopee 最新动态】
• [新闻标题]
  [摘要翻译]

【🎵 TikTok Shop 最新动态】
• [新闻标题]
  [摘要翻译]

【📊 今日关键数据】
• [关键数据点]
• [关键数据点]
```
- 发送到飞书电商早报群
- Webhook: https://open.feishu.cn/open-apis/bot/v2/hook/a31d11a6-1794-4bdd-ba03-ae2dcfaea4ab
- 日报发送成功后再进行喂鱼提醒

### ⏰ 早上 9:30 提醒（Heartbeat触发）
- 提醒坤哥喂鱼（热带鱼，每天早上要喂）

### ⏰ 下午 15:50 提醒（Heartbeat触发）
- 提醒坤哥喂鱼（热带鱼，每天两次：早上9:00 + 下午15:50）
- 注意：Heartbeat时间戳是UTC，换算北京时间为 UTC+8

### ⏰ 晚上 18:30（UTC 10:30）记忆同步
- 执行 /root/.openclaw/workspace/scripts/sync_memory.sh
- 同步记忆到 openclaw-memory 私人仓库
- 发送备份完成通知到服务器汇报群
- Webhook: https://open.feishu.cn/open-apis/bot/v2/hook/18752a31-9cc7-47f5-9a41-d50261934f6e

### ⏰ 其他时间 Heartbeat
- 检查 HEARTBEAT.md 本文件，有则执行，没有则回复 HEARTBEAT_OK
- 两次 Heartbeat 间隔至少 30 分钟才响应

## 当前待跟进
- 喂鱼提醒：坤哥的热带鱼每天两次（9:00 + 15:50），别再饿死了 🐟
