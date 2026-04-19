#!/bin/bash
# pre-push-check.sh - 推送到公共仓库前的自动脱敏检查
# 使用方法：在 .git/hooks/pre-push 中调用，或手动运行

set -e

WORKSPACE="/root/.openclaw/workspace"
PUBLIC_REPOS="pub_arch public public_repo origin_orig"

echo "=== 推送前脱敏检查 ==="

# 检查是否是推送到公共仓库
PUSH_TO_PUBLIC=0
while IFS= read -r remote; do
    for pub in $PUBLIC_REPOS; do
        if echo "$remote" | grep -q "$pub"; then
            PUSH_TO_PUBLIC=1
            break 2
        fi
    done
done < <(git remote -v)

if [[ $PUSH_TO_PUBLIC -eq 0 ]]; then
    echo "→ 非公共仓库推送，跳过脱敏检查"
    exit 0
fi

echo "→ 推送到公共仓库，执行脱敏检查..."

# 需要脱敏的敏感信息模式
PATTERNS=(
    "ghp_[A-Za-z0-9]\{36\}"        # GitHub PAT
    "sk-[A-Za-z0-9]\{20,\}"          # OpenAI/Dify API Key
    "AIza[A-Za-z0-9_-]\{35\}"        # Google API Key
    "AKIA[A-Z0-9]\{16\}"             # AWS Access Key
    "ou_[0-9a-f]\{32\}"              # 飞书 User ID
    "oc_[0-9a-f]\{32\}"              # 飞书 Chat ID
    "LnhA[A-Za-z0-9_-]\{30,\}"       # 飞书 App Secret
    "[0-9a-f]\{32\}\.com"            # 可能的密钥格式
)

ISSUES=0

for pattern in "${PATTERNS[@]}"; do
    # 检查 git staging area（即将提交的内容）
    if git diff --cached -U0 | grep -qE "$pattern"; then
        echo "❌ 敏感信息命中: $pattern (已 staged)"
        ISSUES=$((ISSUES + 1))
    fi
done

# 检查即将推送的 commits
if git log --oneline origin/main..HEAD | head -20; then
    for pattern in "${PATTERNS[@]}"; do
        if git log origin/main..HEAD -p | grep -qE "$pattern"; then
            echo "❌ 敏感信息命中: $pattern (在本次推送的 commits 中)"
            ISSUES=$((ISSUES + 1))
        fi
    done
fi

# 脱敏白名单检查
WHITELIST_CHECK=$(git diff --cached --name-only)
for file in $WHITELIST_CHECK; do
    # config.yaml 应该已经在 .gitignore 中
    if [[ "$file" == *"config.yaml" ]]; then
        echo "⚠️  config.yaml 即将推送（应为 .gitignore 排除）"
        ISSUES=$((ISSUES + 1))
    fi
done

if [[ $ISSUES -gt 0 ]]; then
    echo ""
    echo "❌ 脱敏检查失败！发现 $ISSUES 个问题"
    echo "请修复后再推送，或使用 --no-verify 强制推送（不推荐）"
    exit 1
fi

echo "✅ 脱敏检查通过"
exit 0
