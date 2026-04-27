#!/bin/bash
# skill_factory.sh - 自动化skill制造流水线
# 用法: ./skill_factory.sh "skill名称" "触发条件" "执行动作描述"

SKILL_NAME="$1"
TRIGGER="$2"
ACTIONS="$3"

SG_EMAIL="singapore-skill-factory@openclaw"
SG_NAME="Singapore Skill Factory"

if [ -z "$SKILL_NAME" ]; then
    echo "用法: $0 \"skill名称\" \"触发条件\" \"执行动作\""
    exit 1
fi

echo "[SkillFactory] 🚀 开始制造 skill: $SKILL_NAME"

ssh -o StrictHostKeyChecking=no -i /root/.ssh/id_ed25519 root@178.128.52.85 "
set -e
WORKSPACE=/root/.openclaw/workspace
SKILL_DIR=\$WORKSPACE/skills/$SKILL_NAME
mkdir -p \$SKILL_DIR

cat > \$SKILL_DIR/SKILL.md << 'SKILLEOF'
# $SKILL_NAME

自动生成的skill | $(date)

## 触发条件
$TRIGGER

## 执行动作
$ACTIONS

## 安全约束
- 不造金融/支付/银行类skill
- 不造社交通讯类skill
- 只造数据处理/分析/自动化类skill
SKILLEOF

cd \$WORKSPACE
git config --global user.email '$SG_EMAIL'
git config --global user.name '$SG_NAME'
git add skills/$SKILL_NAME/
git commit -m 'feat(skills): add $SKILL_NAME skill (auto-generated)'
GIT_SSH_COMMAND='ssh -o StrictHostKeyChecking=no -i /root/.ssh/id_ed25519' git push main main

echo '[SkillFactory] ✅ $SKILL_NAME 已推送'
"

echo "[SkillFactory] ✅ 同步完成"
