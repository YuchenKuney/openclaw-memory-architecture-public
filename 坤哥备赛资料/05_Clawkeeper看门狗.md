# 🛡️ Clawkeeper V8 - AI 行为监控与安全审计

> AI Agent 的安全门卫，监控删除/修改核心文件行为，动态调整通知频率

## 核心功能

```
AI 操作 → inotify 监控 → 风险检测 → 拦截/暂停/通知 → 用户审核
```

| 功能 | 说明 |
|------|------|
| 文件监控 | inotify 实时监控核心文件变化 |
| 风险分级 | CRITICAL/HIGH/MEDIUM/LOW 四级风险 |
| 动态通知 | 可调整通知频率（CRITICAL~OFF） |
| 人工审核 | 中高风险操作暂停，等待坤哥回复 |
| 审计日志 | 记录所有操作，支持周期性报告 |

## 风险等级

| 等级 | 操作 | 处理方式 |
|------|------|---------|
| 🔴 CRITICAL | 删除核心文件（AGENTS/SOUL/MEMORY） | **立即拦截** |
| 🚨 HIGH | 修改核心文件、删除核心目录 | **立即拦截** |
| ⚠️ MEDIUM | push 到公共仓、修改 .gitignore | **暂停+审核** |
| 📝 LOW | 创建/修改非核心文件 | 记录日志 |
| ✅ SAFE | 普通操作 | 放行 |

## 文件结构

```
clawkeeper/
├── watcher.py       # inotify 文件监控
├── detector.py     # 风险检测引擎
├── interceptor.py  # 拦截器
├── notifier.py     # 飞书通知
├── auditor.py      # 审计报告
├── config.py       # 配置管理
├── audit.log       # 审计日志
├── scripts/
│   └── install.sh  # 安装脚本
└── README.md       # 本文件
```

## 快速开始

### 安装

```bash
cd /root/.openclaw/workspace/clawkeeper
bash scripts/install.sh
```

### 启动监控

```bash
cd /root/.openclaw/workspace/clawkeeper
python3 -m clawkeeper.watcher
# 或后台运行
nohup python3 -m clawkeeper.watcher > logs/watcher.log 2>&1 &
```

### 动态调整通知频率

```python
from config import ClawkeeperConfig

config = ClawkeeperConfig()

# 调整通知等级
config.set_notification_level("HIGH")   # 仅高风险及以上通知
config.set_notification_level("OFF")    # 完全关闭通知
config.set_notification_level("LOW")   # 所有事件通知
```

## 通知示例

### 🔴 极高风险拦截
```
🛡️ Clawkeeper 🔴 极高风险拦截

文件: /workspace/AGENTS.md
操作: DELETE
风险等级: CRITICAL

处理方式: 操作已被拦截！AI 已暂停执行，等待坤哥处理。
回复「允许」放行 / 「拒绝」回退
```

### ⚠️ 中风险待审核
```
🛡️ Clawkeeper ⚠️ 中风险待审核

文件: /workspace/.gitignore
操作: MODIFY
风险等级: MEDIUM

处理方式: 操作已暂停，等待审核。
回复「允许」继续 / 「拒绝」取消
```

## 审核指令

| 回复 | 效果 |
|------|------|
| `允许` | 放行操作，AI 继续执行 |
| `拒绝` | 取消操作，尝试回退 |

## 审计报告

```bash
# 生成24小时报告
python3 -m clawkeeper.auditor

# 输出示例
🛡️ Clawkeeper 审计报告（过去24小时）
==================================================
总事件数: 12
  🔴 拦截: 2
  ⚠️ 暂停: 3
  ✅ 放行: 7

按风险等级:
  CRITICAL: 1
  HIGH: 1
  MEDIUM: 3
  LOW: 7
==================================================
```

## 注意事项

1. **通知频率可动态调整**，无需重启监控
2. **inotify 需要 Linux 内核支持**，Windows/macOS 使用轮询模式
3. **拦截操作后**，AI 会暂停直到坤哥回复「允许」或「拒绝」
4. **公共仓 push 操作**默认暂停，需坤哥审核后放行

## 版本历史

| 版本 | 更新 |
|------|------|
| v8 | 初始版本，inotify 监控 + 风险分级 + 飞书通知 |
