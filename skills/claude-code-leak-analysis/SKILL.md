# Claude Code 源码泄露分析

## 事件背景
- **泄露时间**: 2026年3月31日
- **泄露原因**: Anthropic在Claude Code npm更新中意外打包了.map sourcemap文件
- **泄露规模**: 60万行代码
- **社区反应**: 24小时内出现开源重建项目claw-code，获10万+ GitHub stars

## 关键发现

### 1. KAIROS - 隐藏的自主代理模式
Claude Code源码中隐藏了一个名为**KAIROS**的24/7自主代理模式：
- 每隔几秒接收心跳提示："有什么值得现在做的事吗？"
- 评估当前情况，决定是否主动行动
- **这与OpenClaw的HEARTBEAT机制高度相似！**

### 2. claw-code 开源项目
- **特点**: 干净室Python重写，DMCA-proof
- **功能**: 多代理编排、工具调用、终端原生AI开发
- **支持**: 模型无关（支持Claude、GPT等）
- **地址**: https://claw-code.io/

### 3. 架构模式参考
- **PROACTIVE模式**: 主动式代理，自动修复错误、响应消息、更新任务
- **工具系统**: 43个内置工具
- **多代理编排**: 子代理协调机制
- **安全护栏**: 内容过滤和验证

## 对OpenClaw的启示
1. HEARTBEAT机制与KAIROS类似，可以进一步优化主动行动逻辑
2. 可以借鉴claw-code的工具调用架构
3. 多代理协作模式值得研究

## 相关链接
- claw-code: https://github.com/instructkr/claw-code
- ClawCode官网: https://claw-code.io/
- 详细分析: https://www.clawdecode.net/
