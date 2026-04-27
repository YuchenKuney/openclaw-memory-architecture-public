# MEMORY.md - 坤哥长期记忆

> 上次更新：2026-04-24（每日日志蒸馏）

---

## 👤 坤哥基本信息

- **称呼**：坤哥
- **时区**：Europe/Berlin（GMT+2）
- **比赛**：May 15, 2026 截止（重要节点）
- **语言**：中文优先，英文也行

---

## 🎯 当前项目与优先级

### 比赛备赛（最高优先）
- **截止**：2026年5月15日
- **核心展示**：AI自进化技能工厂 + 反黑箱透明化 + Web4.0安全铁律
- **材料**：`/root/.openclaw/workspace/坤哥备赛资料.zip`（22KB，9文档）
- **GitHub**：github.com/YuchenKuney/openclaw-memory-architecture-public（已开源，v12）

### Skill Factory（已完成）
- **GitHub**：github.com/YuchenKuney/skill-factory（独立仓库）
- **主仓集成**：v12_skill_factory/ 目录已推送到 openclaw-memory-architecture-public
- **版本A**：多服务器 + WireGuard VPN（主服务器 ↔ 新加坡）
- **版本B**：单机自动判断+创造（推荐）
- **下一步**：Orchestrator 自动触发 skill_factory.py（当Skills不足时）

### 新加坡 OpenClaw（QQ Bot，调试中）
- IP：178.128.52.85，QQ Bot 运行中
- **问题**：QQ Bot 回复 401（可能是新加坡IP访问minimax受限）
- **状态**：坤哥放弃飞书配置，换用QQ；新加坡只留QQ
- **待验证**：坤哥QQ（1511382094）是否收到回复

---

## 🧠 坤哥的工作风格

### 决策模式
- **快速决策**：方案出来后立即执行，不纠结
- **喜欢自动化**：重复的事情一定要自动化
- **结果导向**：不管黑猫白猫，能抓到老鼠就是好猫
- **反黑箱铁律**：每步必须透明汇报，不接受静默执行

### 偏好
- **Webhook推送**：所有进度走飞书卡片，不走主会话回复
- **快速模式**：最快路径，不走弯路
- **Git管理**：代码变化一定要commit+push
- **脱敏意识**：IP/Token/Key类敏感信息必须脱敏后才上传

### 雷区
- ❌ 不要在主会话发大量进度消息（用Webhook）
- ❌ 不要在公共仓暴露真实IP/Token
- ❌ 不要"正在处理..."这种废话，要说具体在做什么

---

## 🔑 持有API Keys（仅供参考，不记录完整值）

| 来源 | 用途 | 状态 |
|------|------|------|
| DeepSeek `sk-cd70...` | 备用模型 | 已有 |
| NVIDIA API #1 `nvapi-l32X...` | 主力模型 | 已有 |
| NVIDIA API #2 `nvapi-3Ft7...` | 备用模型 | 坤哥新给 |
| MiniMax | 系统级 | 在用 |

---

## 📁 重要路径

| 路径 | 说明 |
|------|------|
| `/root/.openclaw/workspace/` | 主工作目录 |
| `/root/.openclaw/workspace/memory/` | 日记层 |
| `/root/.openclaw/workspace/坤哥备赛资料.zip` | 比赛材料 |
| `/root/.openclaw/workspace/skill-factory-repo/` | Skill Factory独立仓 |
| `/root/.openclaw/workspace/clawkeeper/` | 安全审计模块 |
| `/root/.openclaw/workspace/scripts/skill_factory.py` | Skill工厂脚本 |
| `/root/.openclaw/workspace/scripts/feishu_progress.py` | 飞书推送脚本 |

---

## 📝 近期重要决策（2026-04）

### 2026-04-24
- ✅ Skill Factory v12 完整实现并推送 GitHub
- ✅ README 全面修订，版本号修复（v1-v12）
- ✅ 新加坡 OpenClaw 切换为 QQ Bot（飞书放弃）
- ✅ 新加坡 VPN + Git 同步通道打通

### 2026-04-23
- ✅ GitHub AI Agent 调研完成（hermes-agent 重点关注）
- ✅ session_refiner.py 本地实现（hermes-agent 思想借鉴）
- ✅ 喂鱼 cron 修复完成（3个job重建）
- ✅ 6个Bug修复 + 脱敏处理

---

## 🔧 技术栈

- **OpenClaw**：2026.4.21，主服务器 + 新加坡
- **模型**：minimax/MiniMax-M2.7（主力），DeepSeek备用
- **VPN**：WireGuard（10.0.0.1 ↔ 10.0.0.2）
- **语言**：Python 3，Shell
- **Git**：主服务器 bare repo 做同步 hub

---

## 📌 待做事项

### 比赛前必须完成
- [ ] Orchestrator 集成 skill_factory.py 自动触发
- [ ] 完整演示：用户给任务 → AI自动制造Skill → 执行
- [ ] 比赛材料最终检查

### 日常维护
- [ ] 新加坡QQ Bot问题修复（401认证）
- [ ] session_refiner 集成到主session作为post-hook
- [ ] 18:30 cron 记忆蒸馏加入 sessions 处理

---

## 🎓 学到的教训

1. **VPN SSH问题**：WireGuard VPN 对 SSH 不稳定（TCP over WireGuard 有问题），但 Git push（UDP-based）正常工作 → 用公网IP做SSH，VPN只用来git sync
2. **飞书配置冲突**：两台服务器不能接入同一个飞书应用，会冲突 → 新加坡用QQ
3. **Webhook 推送原则**：超过2步的任务，每步完成立即推飞书卡片，不走主会话
