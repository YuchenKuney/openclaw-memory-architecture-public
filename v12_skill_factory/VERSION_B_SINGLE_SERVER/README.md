# 🖥️ 版本B：单机版 Skill 判断与创造

> 无需多台服务器，单个 AI Agent 即可自主判断缺什么技能并自动创建。

## 核心思路

```
用户给任务
    ↓
skill_judge.py 自动分析
    ↓
现有 Skills 能覆盖？ → ✅ 直接执行
    ↓ 不能
自动创建新 Skill
    ↓
Git 提交（可选）
    ↓
Skill 就绪，继续执行
```

## 快速开始

```bash
# 克隆本仓库
git clone <本仓库地址>
cd skill-factory/VERSION_B_SINGLE_SERVER

# 一键部署
bash setup.sh

# 测试
python3 scripts/skill_judge.py "帮我分析英国电商市场"
```

## 核心脚本

### skill_judge.py

**功能：**
1. 接收任务描述
2. 自动识别任务类型（市场调研/竞品分析/代码审计/内容创作/通用）
3. 判断现有 Skills 是否已覆盖
4. 安全检查（拦截金融/社交通讯类任务）
5. 自动生成 Skill 文件
6. Git 提交（可选）
7. Webhook 推送进度

**用法：**
```bash
python3 scripts/skill_judge.py "任务描述"

# 指定 Skill 名称
python3 scripts/skill_judge.py "任务描述" --skill-name custom_skill_name
```

**环境变量：**

| 变量 | 说明 | 默认值 |
|------|------|--------|
| `WORKSPACE` | Skills 目录 | `/root/.openclaw/workspace/skills` |
| `FEISHU_WEBHOOK` | 飞书 Webhook | - |
| `DRY_RUN` | 仅判断不创建 | `0` |

**示例：**
```bash
# 分析英国电商市场（自动匹配市场调研类）
python3 scripts/skill_judge.py "帮我做英国TikTok市场调研"

# 竞品分析（自动匹配竞品分析类）
python3 scripts/skill_judge.py "分析Shopee和Lazada的竞争格局"

# 通用任务（自动生成通用 Skill）
python3 scripts/skill_judge.py "帮我写一封商务邮件"
```

## 自动匹配规则

| 任务关键词 | 匹配类型 | 自动创建 Skill |
|-----------|---------|--------------|
| 市场/调研/选品/竞品 | market_research | `market_researcher` |
| 竞品/竞争对手/差异化 | competitor_analysis | `competitor_analyzer` |
| 数据分析/统计/报表 | data_analysis | `data_analyst` |
| 代码审计/安全检查 | code_review | `code_auditor` |
| 写文章/内容创作/文案 | content_writer | `content_writer` |
| 其他 | general | 自动生成通用名称 |

## 安全约束

**禁止创建以下类型的 Skill：**

- ❌ 金融/支付类（PayPal/Stripe/银行/加密货币）
- ❌ 社交通讯类（Facebook/Instagram/WhatsApp/Telegram）
- ❌ 邮件/私人通讯类（Gmail/Outlook/Slack）
- ❌ 密钥/凭证类（SSH/API Key/Git Token）
- ❌ 政府/医疗/法律敏感类

**安全机制：**
1. **关键词拦截**：自动检测禁止关键词
2. **环境变量注入**：敏感配置不硬编码
3. **只读 Skill**：Skill 定义文件不含执行权限

## Webhook 集成

```bash
export FEISHU_WEBHOOK="https://open.feishu.cn/open-apis/bot/v2/hook/xxx"

# 推送效果：
# Step 1: 🔍 判断 Skill 需求
# Step 2: 🚀 创建 Skill
# Step 3: ✅ 完成
```

## Git 集成（可选）

如果 workspace 有 git 仓库，创建的 Skill 会自动 commit：

```bash
cd /root/.openclaw/workspace
git init  # 如果还没有初始化
python3 scripts/skill_judge.py "新任务"
# 自动 git add + commit
```

## 故障排查

### 导入模块失败
```bash
pip install requests
```

### Webhook 推送失败
检查网络和 Webhook 地址是否可访问。

### Skill 目录不存在
```bash
mkdir -p /root/.openclaw/workspace/skills
```
