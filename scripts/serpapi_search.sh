#!/bin/bash
# SerpAPI 电商调研脚本（带主动推送）
# 使用方式: SERPAPI_KEY=your_key bash scripts/serpapi_search.sh
#
# 依赖:
#   - SerpAPI API Key: https://serpapi.com/manage-api-key
#   - task_push.sh (同目录)
#
# 注意: 
#   - API Key 建议通过环境变量传入，不要硬编码到文件
#   - Google 搜索无需 API Key 但有频率限制
#   - SerpAPI 支持完整网页结构化数据，优先使用 SerpAPI
#   - 若 SerpAPI 报 Invalid API key，说明 key 无效或已过期

API_KEY="${SERPAPI_KEY:-your_api_key_here}"
PUSH="$(dirname "$0")/task_push.sh"
TASK_ID="${TASK_ID:-T-$(date +%Y%m%d-%H%M%S)}"

if [ "$API_KEY" = "your_api_key_here" ]; then
    echo "请设置 SERPAPI_KEY 环境变量: export SERPAPI_KEY=your_key"
    exit 1
fi

$PUSH "$TASK_ID" "S1" "running" "🚀 SerpAPI 调研开始" "0"

python3 << PYEOF
import urllib.request, urllib.parse, json, time, os

API_KEY = os.environ.get("SERPAPI_KEY", "your_api_key_here")
WEBHOOK = "$(grep '^WEBHOOK=' "$(dirname "$0")/task_push.sh" | cut -d'"' -f2)"

def push(msg, pct=0):
    data = json.dumps({"msg_type":"text","content":{"text":msg}}).encode()
    req = urllib.request.Request(WEBHOOK, data=data, headers={'Content-Type':'application/json'})
    try: urllib.request.urlopen(req, timeout=10)
    except: pass

def serpapi_search(query, num=8):
    q = urllib.parse.quote(query)
    url = f"https://serpapi.com/search.json?q={q}&api_key={API_KEY}&num={num}"
    req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
    with urllib.request.urlopen(req, timeout=15) as r:
        return json.loads(r.read())

queries = [
    ("欧洲 TikTok Shop 爆款", "TikTok Shop UK Germany France trending products 2025"),
    ("美国 TikTok Shop 爆款", "TikTok Shop US best selling products trending 2025"),
    ("欧美美妆畅销", "TikTok Shop beauty cosmetics bestseller Europe USA 2025"),
    ("TikTok Shop 家居爆款", "TikTok Shop home products trending viral USA UK 2025"),
]

results = []
pct_base = 0
for name, q in queries:
    push("🔍 抓取" + name + "...", pct_base)
    try:
        data = serpapi_search(q, 8)
        items = data.get("organic_results", [])
        results.append({"category": name, "items": items[:6]})
        push("✅ " + name + " 完成，获取" + str(len(items[:6])) + "条", pct_base + 25)
    except Exception as e:
        err = str(e)
        if "Invalid API key" in err:
            push("❌ SerpAPI Key 无效，请检查或更换 API Key", pct_base + 25)
        elif "your_api_key_here" in err:
            push("❌ 请先设置 SERPAPI_KEY 环境变量", pct_base + 25)
        else:
            push("❌ " + name + " 失败: " + err[:60], pct_base + 25)
        results.append({"category": name, "items": []})
    pct_base += 25
    time.sleep(1.5)

# 编译报告
report = "## TikTok Shop 欧美爆款调研报告\n\n"
for r in results:
    report += "### " + r['category'] + "\n"
    if r['items']:
        for item in r['items']:
            title = item.get('title','')
            snippet = item.get('snippet','')[:120]
            report += "- **" + title + "**\n  " + snippet + "\n"
    else:
        report += "- 暂无数据\n"
    report += "\n"

report += "---\n*数据来源：SerpAPI Google搜索*\n"

full_msg = "📊 【TikTok Shop 欧美爆款报告】\n\n" + report[:3200]
msg = {"msg_type":"text","content":{"text": full_msg}}
data = json.dumps(msg).encode()
req = urllib.request.Request(WEBHOOK, data=data, headers={'Content-Type':'application/json'})
try:
    with urllib.request.urlopen(req, timeout=10): print("REPORT_PUSHED")
except Exception as e:
    print("PUSH_FAIL: " + str(e))

PYEOF

$PUSH "$TASK_ID" "S1" "done" "✅ 调研完成" "100"
