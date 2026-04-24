# 🏗️ 版本A：多服务器 Skill 工厂架构

## 架构图

```
                    ┌─────────────────────┐
                    │   用户（飞书/其他）   │
                    └──────────┬──────────┘
                               │
                    ┌──────────▼──────────┐
                    │   主服务器 (Agent)     │  ← 主控制节点
                    │   10.0.0.1 (VPN)     │
                    └──────────┬──────────┘
                               │ WireGuard VPN
                    ┌──────────▼──────────┐
                    │   新加坡 (Skill工厂)  │  ← 技能制造节点
                    │   178.128.x.x       │
                    │   10.0.0.2 (VPN)    │
                    └─────────────────────┘
                               │
                    ┌──────────▼──────────┐
                    │   Git 同步通道       │  ← Skill 传输
                    │   (VPN 内网传输)     │
                    └─────────────────────┘
```

## 核心组件

| 组件 | 位置 | 职责 |
|------|------|------|
| `skill_factory.py` | 主服务器 | SSH到新加坡执行Skill制造 |
| `wireguard_setup.sh` | 两台服务器 | WireGuard VPN 一键配置 |
| `git_sync.sh` | 主服务器 | Git仓库初始化和同步 |
| `webhook_progress.py` | 主服务器 | 全流程飞书卡片推送 |

## IP规划（脱敏）

| 节点 | 公网 | VPN内网 | 说明 |
|------|------|--------|------|
| 主服务器 | `YOUR_MAIN_SERVER_IP` | `10.0.0.1` | 主控制节点 |
| 新加坡 | `YOUR_SG_SERVER_IP` | `10.0.0.2` | Skill制造节点 |

> ⚠️ **部署时请替换为实际IP，或使用环境变量**

## 部署步骤

### 1. 环境准备

两台服务器都需要安装：

```bash
# 两台都执行
apt-get update && apt-get install -y wireguard wireguard-tools git
```

### 2. 一键配置 VPN

```bash
# 在主服务器执行
bash wireguard_setup.sh
```

脚本会自动：
- 生成密钥对
- 配置主服务器为 `10.0.0.1`
- 配置新加坡为 `10.0.0.2`
- 设置开机自启
- 配置防火墙规则

### 3. 配置 Git 同步

```bash
# 主服务器：初始化 Skill 同步仓库
bash git_sync.sh init

# 新加坡：添加主服务器为远程仓库
bash git_sync.sh add-sg YOUR_MAIN_SERVER_IP
```

### 4. 配置 Webhook

```bash
# 设置飞书 Webhook（可选）
export FEISHU_WEBHOOK="YOUR_WEBHOOK_URL"
```

### 5. 测试

```bash
# 测试 VPN 连通性
ping 10.0.0.2

# 测试 Skill 制造
python3 scripts/skill_factory.py \
    "test_skill" \
    "测试触发条件" \
    "测试执行动作"
```

## 核心脚本详解

### skill_factory.py

**功能：** SSH到新加坡，自动创建Skill并同步回主服务器

**参数：**
```bash
python3 skill_factory.py <skill名称> <触发条件> <执行动作>
```

**示例：**
```bash
python3 skill_factory.py \
    "competitor_analyzer" \
    "分析竞争对手市场份额优劣势" \
    "1接收产品名 2抓取竞品数据 3对比分析 4生成矩阵 5输出建议"
```

**环境变量：**

| 变量 | 说明 | 默认值 |
|------|------|--------|
| `SG_SERVER_IP` | 新加坡公网IP | `178.128.52.85` |
| `SG_SSH_KEY` | SSH私钥路径 | `/root/.ssh/id_ed25519` |
| `SYNC_REPO` | Git同步仓库路径 | `/root/.openclaw/skill_sync.git` |
| `FEISHU_WEBHOOK` | 飞书Webhook | - |

### wireguard_setup.sh

**功能：** 一键配置 WireGuard VPN

**用法：**
```bash
bash wireguard_setup.sh <主服务器公网IP> <新加坡公网IP>
```

**示例：**
```bash
bash wireguard_setup.sh 46.250.233.112 178.128.52.85
```

## 安全配置

### 防火墙规则

```bash
# 主服务器：只允许新加坡 VPN 网段 SSH
ufw allow from 10.0.0.0/24 to any port 22 proto tcp

# 新加坡：同样只允许主服务器 VPN 网段
ufw allow from 10.0.0.0/24 to any port 22 proto tcp
```

### SSH Key 认证

```bash
# 主服务器生成密钥
ssh-keygen -t ed25519 -f /root/.ssh/id_ed25519 -N ""

# 将公钥添加到新加坡
ssh-copy-id -i /root/.ssh/id_ed25519.pub root@新加坡IP
```

### VPN 限制

WireGuard 配置中限定：
```
AllowedIPs = 10.0.0.2/32  # 只允许访问新加坡 VPN 地址
```

**这确保 VPN 不会被用作代理出口。**

## 工作流程

```
1. 用户给任务 → Agent判断 Skills 不足
         ↓
2. Agent 调用 skill_factory.py
         ↓ SSH
3. 新加坡创建 Skill 文件
         ↓ git push
4. 主服务器收到 Skill
         ↓
5. Agent 用新 Skill 执行任务
         ↓ Webhook
6. 用户收到结果通知
```

## 故障排查

### VPN 不通
```bash
# 检查 WireGuard 状态
wg show

# 检查端口
ss -tulpn | grep 51820

# 检查防火墙
iptables -L -n
```

### SSH 连接失败
```bash
# 测试 SSH
ssh -v -i /root/.ssh/id_ed25519 root@10.0.0.2

# 检查 known_hosts
ssh-keyscan -t ed25519 10.0.0.2 >> ~/.ssh/known_hosts
```

### Git 推送失败
```bash
# 检查远程仓库
git remote -v

# 测试 Git SSH
GIT_SSH_COMMAND="ssh -v" git push main main
```
