# 🔒 Web4.0 AI Agent 沙箱铁律（硬编码）

> 本文件是 Web4.0 沙箱浏览器的"绝对禁令"，全部硬编码在 `web4_cookie_injector.py` 的 `IronRuler` 类中，**不可被 Cooking 配置覆盖**，任何时候都必须遵守。

---

## 铁律一：身份铁律（Identity Rule）

**原则**：AI 只模拟普通用户浏览公开内容，禁止任何账号操作。

```python
# 绝对禁止的域名（账号后台 / 个人数据）
IDENTITY_BLOCKED_PATHS = {
    "accounts.google.com": [全部路径],
    "pay.google.com": ["*"],
    "wallet.google.com": ["*"],
    "payments.google.com": ["*"],
    "mail.google.com": ["*"],
    "inbox.google.com": ["*"],
    "drive.google.com": ["*"],
    "photos.google.com": ["*"],
    "calendar.google.com": ["*"],
    "studio.youtube.com": ["*"],
    "youtube.com/playlist": ["*"],  # 私有播放列表
}
```

**检查逻辑**：`IronRuler.is_account_operation(url)` — 遇到以上域名/路径直接拒绝。

---

## 铁律二：访问边界铁律（Access Boundary Rule）

**原则**：只允许浏览公开可访问的域名和内容。

```python
# 允许的公开域名白名单（硬编码）
ACCESS_ALLOWED_DOMAINS = {
    # Google 公开页面
    "google.com", ".google.com", "www.google.com",
    "google.co.jp", "www.google.co.jp",
    # YouTube 公开页面
    "youtube.com", ".youtube.com", "www.youtube.com", "youtu.be",
    # Shopee 公开页面（东南亚各站）
    "shopee.com", ".shopee.com", "www.shopee.com",
    "shopee.co.id", ".shopee.co.id",
    "shopee.sg", ".shopee.sg",
    "shopee.ph", ".shopee.ph",
    "shopee.vn", ".shopee.vn",
    "shopee.my", ".shopee.my",
    "shopee.th", ".shopee.th",
    # TikTok 公开页面
    "tiktok.com", ".tiktok.com", "www.tiktok.com",
    # 搜索引擎（搜索结果跳转）
    "bing.com", ".bing.com", "www.bing.com",
    "duckduckgo.com", ".duckduckgo.com",
    # IP 定位工具
    "ip2location.com", ".ip2location.com",
}

# 禁止的路径模式（硬编码）
ACCESS_BLOCKED_PATTERNS = {
    "/seller/", "/vendor/", "/partner/", "/affiliate/",
    "/admin/", "/dashboard/", "/crm/", "/backend/",
    "/login/", "/signin/", "/auth/", "/oauth/",
    "/account/", "/profile/settings",
}
```

**额外约束**：只允许 `GET` 请求，所有 `POST`/`PUT`/`DELETE` 请求一律拒绝。

---

## 铁律三：行为风控铁律（Behavioral Control Rule）

**原则**：模拟真实用户的浏览行为，防止恶意高频爬取。

```python
# 单域名最少间隔（秒）
_min_interval = 3.0

# 单次会话最多请求次数
_max_requests = 50

# 随机停留时间（模拟真实用户）
_min_scroll_wait = 0.5   # 秒
_max_scroll_wait = 2.0   # 秒
```

**检查逻辑**：
- 每次请求前检查 `IronRuler.can_request(url)` — 返回 `(是否允许, 原因)`
- 间隔不足3秒 → 等待补足
- 超过50次 → 会话强制停止

---

## 铁律四：数据清除铁律（Data Wipe Rule）

**原则**：会话结束后，强制清除所有可能残留的用户数据。

```python
def close():
    # 1. 清除所有 Cookie
    context.clear_cookies()
    # 2. 清除所有权限状态
    context.clear_permissions()
    # 3. 关闭 Context
    context.close()
    # 4. 关闭 Browser
    browser.close()
    # 5. 停止 Playwright
    playwright.stop()
```

**会话结束时（`RuledBrowserSession.close()` 或 `__exit__`）自动触发，任何情况下不可跳过。**

---

## 🚨 绝对禁令总结

| # | 铁律 | 违规后果 |
|---|------|---------|
| 1 | 身份铁律 | URL 直接拒绝，返回 `🚫 账号后台操作被禁止` |
| 2 | 访问边界铁律 | 不在白名单的域名/路径全部拒绝，只允许 GET |
| 3 | 行为风控铁律 | 超过频率/次数限制 → 请求被阻止，会话强制停止 |
| 4 | 数据清除铁律 | close() 时强制清空，断电/异常也保证下次新会话干净 |

---

## 📜 合规声明

本项目 AI Agent 沙箱浏览器仅用于：
- ✅ 公开网页研究（Shopee/TikTok/YouTube 公开页面）
- ✅ 搜索引擎结果跳转
- ✅ 市场调研数据采集

**严禁用于**：
- ❌ 登录他人账号或模拟登录态
- ❌ 爬取银行/支付/政府/邮箱等私密页面
- ❌ 任何未经授权的数据爬取行为

**铁律已写死代码，不可被 cooking 配置覆盖。违者后果自负。**
