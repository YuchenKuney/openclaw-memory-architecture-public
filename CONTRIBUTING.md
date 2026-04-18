# 🤝 贡献指南

感谢你关注 OpenClaw Memory Architecture！

## 如何贡献

### 报告问题（Bug Report）

- 使用 GitHub Issues 报告 Bug
- 描述清楚：复现步骤、预期行为、实际行为
- 提供环境信息（Python 版本、操作系统等）

### 功能建议（Feature Request）

- 先搜索是否已有类似建议
- 描述清楚使用场景和解决的问题
- 欢迎提交 PR 实现

### Pull Request

1. Fork 本仓库
2. 创建你的功能分支 (`git checkout -b feature/amazing-feature`)
3. 提交更改 (`git commit -m 'feat: add amazing feature'`)
4. 推送到分支 (`git push origin feature/amazing-feature`)
5. 提交 Pull Request

## 代码规范

- Python 代码遵循 PEP 8
- 提交信息使用中文，清晰描述改动
- 涉及脚本修改请附上使用说明

## 测试

提交前请确保脚本可以正常运行：

```bash
# 检查语法
python3 -m py_compile scripts/your_script.py

# 检查导入
python3 -c "import scripts.your_module"
```

## 许可证

提交 PR 即表示你同意你的代码遵循 MIT 许可证。
