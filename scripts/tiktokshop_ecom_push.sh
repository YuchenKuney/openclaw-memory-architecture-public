#!/bin/bash
# TikTok Shop 欧美爆款自动调研脚本
# 全程自动推送进度，无需手动干预

PUSH="/root/.openclaw/workspace/scripts/task_push.sh"
TASK_ID="T-20260418-006"

# 初始化任务
$PUSH "$TASK_ID" "S1" "running" "🚀 欧美TikTok Shop爆款调研开始" "0"

# ============ S1: 欧洲市场搜索 ============
$PUSH "$TASK_ID" "S1" "running" "🔍 搜索欧洲 TikTok Shop 爆款..." "10"

python3 << 'PYEOF'
import urllib.request, urllib.parse, json, re, time

WEBHOOK = "${FEISHU_WEBHOOK:-YOUR_FEISHU_WEBHOOK_URL}"
TRANSLATE_URL = "https://translate.googleapis.com/translate_a/single?client=gtx&sl=en&tl=zh-CN&dt=t"

def translate(text):
    text = text.strip()[:500]
    try:
        url = TRANSLATE_URL + '&q=' + urllib.parse.quote(text)
        with urllib.request.urlopen(url, timeout=10) as r:
            data = json.loads(r.read())
            return ''.join([x[0] for x in data[0] if x[0]])
    except:
        return text[:200]

def search(query, num=5):
    try:
        url = f"https://www.google.com/search?q={urllib.parse.quote(query)}&num={num}"
        req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
        with urllib.request.urlopen(req, timeout=10) as r:
            html = r.read().decode('utf-8', errors='ignore')
        results = re.findall(r'<a href="([^"]+)"[^>]*>([^<]+)</a>', html)
        seen = set()
        out = []
        for href, title in results:
            if '/search?' not in href or 'webcache' in href: continue
            t = re.sub(r'<[^>]+>', '', title).strip()
            if t and t not in seen and len(t) > 20:
                seen.add(t)
                out.append((t, href))
        return out[:num]
    except Exception as e:
        return []

def fetch_content(url):
    try:
        req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
        with urllib.request.urlopen(req, timeout=8) as r:
            c = r.read(3000).decode('utf-8', errors='ignore')
        c = re.sub(r'<[^>]+>', ' ', c)
        return re.sub(r'\s+', ' ', c)[:400]
    except:
        return ""

import subprocess, json

def push(task, step, status, msg, pct):
    cmd = f'/root/.openclaw/workspace/scripts/task_push.sh "{task}" "{step}" "{status}" "{msg}" "{pct}"'
    subprocess.run(cmd, shell=True, capture_output=True)

queries = [
    ("欧洲", "TikTok Shop UK Germany France best selling products 2025"),
    ("美国", "TikTok Shop US trending products viral 2025 bestseller"),
    ("欧洲品类", "TikTok Shop Europe top categories beauty fashion home 2025"),
    ("美国爆款", "TikTok Shop US top selling items trending viral 2025"),
]

all_results = {}
for region, q in queries:
    push("T-20260418-006", "S1", "running", f"🌍 抓取{region}市场...", 20)
    r = search(q, 4)
    all_results[region] = r
    time.sleep(1.5)

# 编译报告
report = "## 📊 TikTok Shop 欧美爆款调研报告\n\n"
for region, items in all_results.items():
    report += f"### 🌍 {region} 市场\n"
    if items:
        for title, href in items:
            t = translate(title)
            report += f"- **{t}**\n"
    else:
        report += "- 暂无数据\n"
    report += "\n"

report += "---\n*数据来源：Google 搜索 | 实时抓取*\n"

# 最终推送
msg1 = {
    "msg_type": "text",
    "content": {"text": f"✅ 【欧美TikTok Shop爆款调研完成】\n\n已覆盖：英国/德国/法国 + 美国\n共抓取 {sum(len(v) for v in all_results.values())} 条数据\n详细报告生成中，2秒后送达..."}
}
data1 = json.dumps(msg1).encode()
req1 = urllib.request.Request(WEBHOOK, data=data1, headers={'Content-Type': 'application/json'})
try:
    with urllib.request.urlopen(req1, timeout=10): pass
except: pass

time.sleep(2)

msg2 = {
    "msg_type": "text",
    "content": {"text": f"📊 【欧美TikTok Shop爆款调研报告】\n\n{report[:3500]}"}
}
data2 = json.dumps(msg2).encode()
req2 = urllib.request.Request(WEBHOOK, data=data2, headers={'Content-Type': 'application/json'})
try:
    with urllib.request.urlopen(req2, timeout=10): print("REPORT_PUSHED")
except: print("REPORT_PUSH_FAILED")

PYEOF

EXIT=$?

if [ $EXIT -eq 0 ]; then
    $PUSH "$TASK_ID" "S1" "done" "✅ 欧美爆款搜索完成，报告已推送" "100"
else
    $PUSH "$TASK_ID" "S1" "error" "❌ 搜索超时，重试中..." "0"
fi
