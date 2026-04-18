# 调研脚本说明

## task_push.sh

任务进度主动推送脚本。调用方式：

```bash
./task_push.sh "T-001" "S1" "done" "描述内容" "50"
```

参数：
1. 任务ID
2. 步骤ID
3. 状态（running/done/error/pending）
4. 描述信息
5. 进度百分比（可选）

## serpapi_search.sh

SerpAPI 电商调研脚本，支持主动推送进度。

### 前置要求

1. 注册 SerpAPI：https://serpapi.com/
2. 获取 API Key
3. 设置环境变量：

```bash
export SERPAPI_KEY=your_api_key_here
```

### 使用方式

```bash
# 方式1：环境变量
export SERPAPI_KEY=your_api_key_here
bash scripts/serpapi_search.sh

# 方式2：一行
SERPAPI_KEY=your_key bash scripts/serpapi_search.sh
```

### 支持的搜索方向

- 欧洲 TikTok Shop 爆款（英国/德国/法国）
- 美国 TikTok Shop 爆款
- 欧美美妆畅销品类
- 家居/厨房爆款

### API 说明

| API | 费用 | 反爬 | 数据质量 |
|-----|------|------|---------|
| SerpAPI | 付费（免费额度有限）| 无 | 高 |
| Google 直接爬 | 免费 | 强 | 低 |

**SerpAPI 优势**：
- 返回完整网页结构化数据（标题/摘要/链接）
- 无频率限制和验证码
- 支持 Google/Bing/DuckDuckGo 等多个搜索引擎

**常见错误**：
- `Invalid API key`：API Key 无效或已过期，请到 SerpAPI 管理后台检查
- `your_api_key_here`：未设置 SERPAPI_KEY 环境变量

### 扩展调研方向

修改脚本中的 `queries` 数组即可：

```python
queries = [
    ("东南亚 Shopee 爆款", "Shopee Philippines top selling products 2025"),
    ("TikTok 热门美妆", "TikTok beauty trending products viral 2025"),
]
```
