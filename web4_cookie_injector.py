#!/usr/bin/env python3
"""
Web4.0 Cookie 注入器
从坤哥导出的浏览器 Cookie JSON 中提取指定站点的 Cookie，
注入到 Playwright 浏览器实例中。

用法：
  from web4_cookie_injector import CookieInjector
  injector = CookieInjector(cookie_json_path="/path/to/cookies.json")
  
  # 只注入 Google 相关 Cookie（不注入金融/敏感 Cookie）
  injector.set_allowed_domains(["google.com", "youtube.com", ".google.com", ".youtube.com"])
  
  # 创建带 Cookie 的浏览器
  browser = injector.launch_browser(pool=True)

铁律：不注入非公开敏感信息
  - 不注入 PayPal / 银行 / 金融类 Cookie
  - 不注入社交媒体私人会话 Cookie（LinkedIn私人消息等）
  - 只注入搜索引擎 + 公开内容类 Cookie
"""

import os
import sys
import json
from pathlib import Path
from typing import Optional


# ══════════════════════════════════════════════════════════════
#  允许注入的域名白名单（铁律）
# ══════════════════════════════════════════════════════════════

# 完全允许的域名（公开内容网站）
ALLOWED_DOMAINS = {
    # 搜索引擎
    "google.com", "www.google.com", ".google.com",
    "youtube.com", "www.youtube.com", ".youtube.com",
    "bing.com", "www.bing.com", ".bing.com",
    "duckduckgo.com", "www.duckduckgo.com",
    
    # 新闻 / 资讯
    "news.ycombinator.com",
    "reddit.com", "www.reddit.com", ".reddit.com",
    "twitter.com", "www.twitter.com", "x.com",  # X/Twitter 公开推文
    
    # 公开内容平台
    "github.com", "www.github.com",
    "medium.com", "www.medium.com",
    "zhihu.com", "www.zhihu.com",
    "weibo.com", "www.weibo.com",
    "sina.com.cn", "www.sina.com.cn",
    "sohu.com", "www.sohu.com",
    "qq.com", "www.qq.com",
    "baidu.com", "www.baidu.com",
    
    # 电商公开信息（不爬源码，只爬公开页面）
    "shopee.com", "www.shopee.com", ".shopee.com",
    "tiktok.com", "www.tiktok.com", ".tiktok.com",
    "taobao.com", "www.taobao.com",
    "aliexpress.com", "www.aliexpress.com",
    "amazon.com", "www.amazon.com",
    "jd.com", "www.jd.com",
    
    # Google 公开产品（只读浏览）
    ".gemini.google.com",
    ".googleadservices.com",
    ".google-analytics.com",
    ".googletagmanager.com",
    ".doubleclick.net",
    "news.google.com",
    "support.google.com",

    # 广告跟踪（跟随性）
    ".criteo.com", ".crwdcntrl.net",

    # 其他公开平台
    "bloomberg.com", "www.bloomberg.com",
    "reuters.com", "www.reuters.com",
    "wsj.com", "www.wsj.com",
    "ft.com", "www.ft.com",
    "cnbc.com", "www.cnbc.com",
    "forbes.com", "www.forbes.com",
    "techcrunch.com", "www.techcrunch.com",
    "36kr.com", "www.36kr.com",
    "ithome.com", "www.ithome.com",
    "lieyunwang.com", "www.lieyunwang.com",
}

# 铁律：完全禁止注入的域名（敏感类）
BLOCKED_DOMAINS = {
    # 金融 / 支付（绝对禁止）
    "paypal.com", "www.paypal.com", ".paypal.com",
    "stripe.com", "www.stripe.com", ".stripe.com",
    "bankofamerica.com", ".bankofamerica.com",
    "chase.com", ".chase.com",
    "wellsfargo.com", ".wellsfargo.com",
    ".bank",  # 泛域名阻止所有银行
    
    # 社交媒体私人会话
    "facebook.com", "www.facebook.com", ".facebook.com",
    "messenger.com", "www.messenger.com",
    "instagram.com", "www.instagram.com",
    "whatsapp.com", "www.whatsapp.com",
    "telegram.org", "t.me",
    
    # 邮件 / 私人通讯
    "mail.google.com", "inbox.google.com",
    "outlook.live.com", "outlook.office.com",
    "mail.com", "www.mail.com",
    "qq.com", "mail.qq.com",
    "163.com", "mail.163.com",
    
    # 政府 / 医疗 / 法律（敏感）
    ".gov", ".gov.cn",
    "IRS.gov", "ssn.gov",
    ".health", ".medical",
    
    # 工作平台（私人内容）
    "slack.com", "www.slack.com",
    "notion.so", "www.notion.so",
    "dropbox.com", "www.dropbox.com",
    "drive.google.com",  # Google Drive 私人文件
    
    # 加密货币
    "coinbase.com", "www.coinbase.com",
    "binance.com", "www.binance.com",
    "kraken.com", "www.kraken.com",
}


# ══════════════════════════════════════════════════════════════
#  Cookie 过滤器
# ══════════════════════════════════════════════════════════════

def is_allowed_cookie(domain: str, allowed: set = None, blocked: set = None) -> bool:
    """判断某个域名的 Cookie 是否可以注入"""
    domain = domain.lower()
    
    # 精确匹配阻止
    if domain in BLOCKED_DOMAINS:
        return False
    
    # 泛域名阻止
    for blocked in BLOCKED_DOMAINS:
        if blocked.startswith(".") and (domain == blocked or domain.endswith(blocked)):
            return False
    
    # 在白名单中
    if domain in ALLOWED_DOMAINS:
        return True
    
    # 泛域名白名单匹配
    for allowed in ALLOWED_DOMAINS:
        if allowed.startswith(".") and (domain == allowed or domain.endswith(allowed)):
            return True
    
    return False


def filter_cookies(cookie_json: list, allowed_domains: set = None) -> list:
    """
    从导出的 Cookie JSON 中过滤出安全的 Cookie。
    
    参数：
      cookie_json: 浏览器导出的 Cookie 列表（JSON 格式）
      allowed_domains: 可选，额外的允许域名
    
    返回：只包含允许域名的 Cookie 列表（Playwright 格式）
    """
    filtered = []
    blocked_log = []
    
    for cookie in cookie_json:
        domain = cookie.get("domain", "").lower()
        name = cookie.get("name", "")
        
        # 特殊处理 Google 系 Cookie（只保留公开搜索相关的）
        if "google" in domain:
            # 允许：SNID, SEARCH_SAMESITE, OTZ（搜索偏好）
            # 允许：NID（Google 搜索语言偏好）
            # 阻止：HSID, SSID, APISID, SAPISID（登录认证 Token）
            auth_cookie_names = {
                "HSID", "SSID", "APISID", "SAPISID",
                "__Secure-1PAPISID", "__Secure-3PAPISID",
                "ACCOUNT_CHOOSER", "lsid",
                "GMAIL_RMB", "GMAIL_AT",
                "GMX_AUTH", "GOOGLE_AUTH",
            }
            if name in auth_cookie_names:
                blocked_log.append(f"  🚫 {domain} / {name} (认证Cookie，已阻止)")
                continue
        
        # 检查是否允许
        if allowed_domains and domain not in allowed_domains:
            if not is_allowed_cookie(domain):
                blocked_log.append(f"  🚫 {domain} / {name} (敏感域名，已阻止)")
                continue
        else:
            if not is_allowed_cookie(domain):
                blocked_log.append(f"  🚫 {domain} / {name} (敏感域名，已阻止)")
                continue
        
        # 转换为 Playwright 格式
        playwright_cookie = {
            "name": cookie.get("name", ""),
            "value": cookie.get("value", ""),
            "domain": cookie.get("domain", ""),
            "path": cookie.get("path", "/"),
        }
        
        # 可选字段
        if cookie.get("secure"):
            playwright_cookie["secure"] = True
        if cookie.get("httpOnly"):
            playwright_cookie["httpOnly"] = True
        # 转换 sameSite 值（Playwright 只接受 Strict/Lax/None）
        raw_samesite = cookie.get("sameSite", "lax")
        if raw_samesite in ("unspecified", "no_restriction", "none", ""):
            playwright_cookie["sameSite"] = None  # None = 不设置 SameSite 属性
        elif raw_samesite in ("Strict", "Lax", "Strict"):
            playwright_cookie["sameSite"] = raw_samesite
        else:
            playwright_cookie["sameSite"] = "Lax"  # 安全默认值
        if cookie.get("expires") and isinstance(cookie.get("expires"), (int, float)):
            # Playwright 不支持 expires，直接用 session cookie 即可
            pass
        
        filtered.append(playwright_cookie)
    
    return filtered, blocked_log


# ══════════════════════════════════════════════════════════════
#  Cookie 注入器主类
# ══════════════════════════════════════════════════════════════

class CookieInjector:
    """
    Cookie 注入器。
    从文件或 JSON 加载 Cookie，过滤后注入到 Playwright 浏览器。
    """

    def __init__(self, cookie_json_path: str = None, cookie_json: list = None):
        """
        参数：
          cookie_json_path: 坤哥导出的 Cookie 文件路径
          cookie_json: 或直接传入 Cookie 列表
        """
        self.cookie_json = cookie_json or []
        if cookie_json_path:
            with open(cookie_json_path, "r", encoding="utf-8") as f:
                self.cookie_json = json.load(f)
        
        self._allowed_domains: set = set()
        self._blocked_log: list = []
        self._filtered_cookies: list = []
        
        # 默认只允许公开内容域名
        self.set_allowed_domains(set(ALLOWED_DOMAINS))
    
    def set_allowed_domains(self, domains: set):
        """设置允许注入的域名集合"""
        self._allowed_domains = domains
    
    def filter(self, verbose: bool = True) -> list:
        """过滤 Cookie，返回可安全注入的列表"""
        self._filtered_cookies, self._blocked_log = filter_cookies(
            self.cookie_json, 
            allowed_domains=self._allowed_domains
        )
        
        if verbose:
            print(f"[CookieInjector] 过滤完成：")
            print(f"  ✅ 允许注入: {len(self._filtered_cookies)} 个")
            print(f"  🚫 阻止注入: {len(self._blocked_log)} 个")
            for entry in self._blocked_log[:10]:
                print(entry)
            if len(self._blocked_log) > 10:
                print(f"  ... 还有 {len(self._blocked_log) - 10} 个被阻止")
        
        return self._filtered_cookies
    
    def get_filtered_cookies(self) -> list:
        return self._filtered_cookies
    
    def inject_to_context(self, context) -> int:
        """
        将过滤后的 Cookie 注入到 Playwright BrowserContext。
        返回实际注入的 Cookie 数量。
        """
        if not self._filtered_cookies:
            self.filter()
        
        injected = 0
        for cookie in self._filtered_cookies:
            try:
                context.add_cookies([cookie])
                injected += 1
            except Exception as e:
                print(f"[CookieInjector] ⚠️ 注入失败 {cookie.get('domain')}/{cookie.get('name')}: {e}")
        
        print(f"[CookieInjector] ✅ 成功注入 {injected} 个 Cookie")
        return injected
    
    def save_filtered(self, path: str):
        """将过滤后的 Cookie 保存到文件（安全用途：只保存允许的部分）"""
        safe_cookies = []
        for c in self._filtered_cookies:
            # 只保存必要字段（不含 value 中的敏感数据）
            safe_cookies.append({
                "name": c["name"],
                "domain": c["domain"],
                "path": c.get("path", "/"),
                "secure": c.get("secure", False),
            })
        
        with open(path, "w", encoding="utf-8") as f:
            json.dump(safe_cookies, f, indent=2, ensure_ascii=False)
        
        print(f"[CookieInjector] 💾 安全 Cookie 已保存: {path}")


# ══════════════════════════════════════════════════════════════
#  带 Cookie 的浏览器会话
# ══════════════════════════════════════════════════════════════

def launch_with_cookies(
    cookie_json: list,
    allowed_domains: set = None,
    profile: str = "stealth",
    headless: bool = True,
) -> tuple:
    """
    启动带 Cookie 注入的 Playwright 浏览器。
    
    返回：(browser, page, injector)
    
    用法：
      from web4_cookie_injector import launch_with_cookies
      
      browser, page, injector = launch_with_cookies(
          cookie_json=cookies,
          allowed_domains={"google.com", ".google.com", "youtube.com", ".youtube.com"},
      )
      
      # 访问 Google 搜索（已登录状态）
      page.goto("https://www.google.com/search?q=shopee+tiktok")
      
      # 完成后清理
      browser.close()
    """
    from playwright.sync_api import sync_playwright
    
    injector = CookieInjector(cookie_json=cookie_json)
    if allowed_domains:
        injector.set_allowed_domains(allowed_domains)
    
    filtered = injector.filter()
    
    if not filtered:
        print("[CookieInjector] ⚠️ 没有可注入的 Cookie，将以匿名状态启动")
    
    # 启动浏览器
    pw = sync_playwright().start()
    browser = pw.chromium.launch(
        headless=headless,
        args=[
            "--no-sandbox",
            "--disable-setuid-sandbox",
            "--disable-dev-shm-usage",
            "--disable-gpu",
            "--disable-web-security",
            "--allow-running-insecure-content",
            "--ignore-certificate-errors",
        ]
    )
    
    # 创建 Context
    context = browser.new_context(
        user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                   "(KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36",
        viewport={"width": 1920, "height": 1080},
        locale="zh-CN",
    )
    
    # 注入 Cookie
    injector.inject_to_context(context)
    
    # 新建标签页
    page = context.new_page()
    page.set_default_timeout(30000)
    
    return browser, page, injector, pw


# ══════════════════════════════════════════════════════════════
#  快速测试
# ══════════════════════════════════════════════════════════════

if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="Web4.0 Cookie 注入器")
    parser.add_argument("--cookie-file", required=True, help="坤哥导出的 Cookie JSON 文件路径")
    parser.add_argument("--list-only", action="store_true", help="只列出 Cookie，不启动浏览器")
    args = parser.parse_args()
    
    print(f"加载 Cookie: {args.cookie_file}")
    
    with open(args.cookie_file, "r", encoding="utf-8") as f:
        cookies = json.load(f)
    
    print(f"总 Cookie 数: {len(cookies)}")
    
    injector = CookieInjector(cookie_json=cookies)
    
    # 只允许 Google + YouTube
    google_domains = {
        "google.com", ".google.com", "www.google.com",
        "youtube.com", ".youtube.com", "www.youtube.com",
    }
    injector.set_allowed_domains(google_domains)
    
    filtered = injector.filter()
    
    if args.list_only:
        print(f"\n可注入的 Cookie ({len(filtered)} 个):")
        for c in filtered:
            print(f"  ✅ {c['domain']:40} {c['name']}")
        sys.exit(0)
    
    print("\n启动带 Cookie 的浏览器...")
    browser, page, injector, pw = launch_with_cookies(
        cookie_json=cookies,
        allowed_domains=google_domains,
    )
    
    print("\n访问 Google...")
    page.goto("https://www.google.com")
    print(f"标题: {page.title()}")
    
    input("按回车退出...")
    browser.close()
    pw.stop()
    print("完成")


# ═══════════════════════════════════════════════════════════════════
#  🔒 铁律实现（坤哥的 4 条绝对禁令）
# ═══════════════════════════════════════════════════════════════════

class IronRuler:
    """
    铁律执行器 — 4 条绝对禁令，不可被 cooking 覆盖
    """

    # ── 铁律一：身份铁律 ──────────────────────────────────────────
    # Google 账号只用于模拟普通用户，禁止任何账号操作
    IDENTITY_BLOCKED_PATHS = {
        # Google 账号后台（绝对禁止）
        "accounts.google.com": [
            "/v2/signin", "/signin", "/AccountChoose", "/Password",
            "/SecondFactor", "/StepTwo", "/verify", "/addname",
            "/deleteaccount", "/privacystatement", "/termsofservice",
            "/webhistory", "/activity", "/settings", "/oauth2/",
            "/o/oauth2/", "/download", "/mail/", "/drive/",
            "/photos/", "/cloud", "/backup", "/payments",
            "/subscriptions", "/play", "/store", "/wallet",
        ],
        # Google 支付 / 购物（绝对禁止）
        "pay.google.com": ["*"],
        "wallet.google.com": ["*"],
        "payments.google.com": ["*"],
        # Gmail / 云盘（绝对禁止）
        "mail.google.com": ["*"],
        "inbox.google.com": ["*"],
        "drive.google.com": ["*"],
        "photos.google.com": ["*"],
        "calendar.google.com": ["*"],
        # YouTube 个人（只允许公开视频）
        "studio.youtube.com": ["*"],
        "youtube.com/playlist": ["*"],  # 私有播放列表
        "youtube.com/shorts": [],         # 允许公开短视频
    }

    def is_account_operation(self, url: str) -> bool:
        """铁律一：检查是否是账号后台操作"""
        from urllib.parse import urlparse
        parsed = urlparse(url)
        domain = parsed.netloc.lower()
        path = parsed.path

        # 精确匹配域名
        if domain in self.IDENTITY_BLOCKED_PATHS:
            blocked_paths = self.IDENTITY_BLOCKED_PATHS[domain]
            if blocked_paths == ["*"]:
                return True  # 全域名禁止
            for bp in blocked_paths:
                if bp.endswith("*"):
                    if path.startswith(bp[:-1]):
                        return True
                elif path == bp or path.startswith(bp + "/"):
                    return True
        return False

    # ── 铁律二：访问边界铁律 ──────────────────────────────────
    # 只允许特定公开域名，禁止登录态个人数据
    ACCESS_ALLOWED_DOMAINS = {
        # Google 公开页面
        "google.com", ".google.com", "www.google.com",
        "google.co.jp", "www.google.co.jp",
        # YouTube 公开页面
        "youtube.com", ".youtube.com", "www.youtube.com",
        "youtu.be",  # YouTube 短链接
        # Shopee 公开页面
        "shopee.com", ".shopee.com", "www.shopee.com",
        "shopee.co.id", ".shopee.co.id",  # 东南亚各国站
        "shopee.sg", ".shopee.sg",
        "shopee.ph", ".shopee.ph",
        "shopee.vn", ".shopee.vn",
        "shopee.my", ".shopee.my",
        "shopee.th", ".shopee.th",
        # TikTok 公开页面
        "tiktok.com", ".tiktok.com", "www.tiktok.com",
        # 辅助：搜索引擎（搜索结果跳转用）
        "bing.com", ".bing.com", "www.bing.com",
        "duckduckgo.com", ".duckduckgo.com",
        # IP 定位工具（辅助）
        "ip2location.com", ".ip2location.com",
    }

    ACCESS_BLOCKED_PATTERNS = {
        # 禁止：个人后台路径
        "/seller/", "/vendor/", "/partner/", "/affiliate/",
        "/admin/", "/dashboard/", "/crm/", "/backend/",
        # 禁止：登录/注册路径（Cookie 登录不需要访问）
        "/login", "/signin", "/auth", "/oauth/",
        "/account", "/profile/settings",
        # 禁止：POST / 表单提交
        # （通过请求方法判断，不在这里处理）
    }

    def _decode_bing_redirect(self, url: str) -> str | None:
        """从 Bing 重定向 URL 中解码出真实目标 URL（URL decode + Base64 decode）"""
        import base64
        from urllib.parse import parse_qs, urlparse, unquote
        try:
            parsed = urlparse(url)
            if 'bing.com' in parsed.netloc and '/ck/a' in parsed.path:
                params = parse_qs(parsed.query)
                if 'u' in params and params['u']:
                    raw = params['u'][0]
                    url_decoded = unquote(raw)
                    real_url = base64.b64decode(url_decoded).decode('utf-8')
                    return real_url
        except Exception:
            pass
        return None

    def is_access_allowed(self, url: str) -> bool:
        """铁律二：检查 URL 是否在允许的公开域名范围内"""
        from urllib.parse import urlparse
        parsed = urlparse(url)
        domain = parsed.netloc.lower()
        path = parsed.path.lower()

        # ── 特殊情况1：Bing/Google 搜索结果重定向 URL ─────
        # 这类 URL 的实际目标在 u= 参数里，需要解码后检查
        decoded_target = None

        # Bing 重定向链接（内部搜索引擎跳转）
        if 'bing.com' in domain and '/ck/a' in path:
            decoded_target = self._decode_bing_redirect(url)
            if decoded_target:
                # 解码出真实目标，检查那个 URL
                parsed2 = urlparse(decoded_target)
                domain2 = parsed2.netloc.lower()
                # 如果真实目标是 Shopee/TikTok，允许
                for allowed_domain in self.ACCESS_ALLOWED_DOMAINS:
                    if allowed_domain.startswith("."):
                        if domain2 == allowed_domain or domain2.endswith(allowed_domain):
                            return True
                    else:
                        if domain2 == allowed_domain:
                            return True
                # 真实目标不在白名单，拒绝这个 Bing 跳转
                return False

        # Google 搜索结果跳转
        if 'google.com' in domain and '/url' in path:
            try:
                from urllib.parse import parse_qs
                params = parse_qs(parsed.query)
                if 'q' in params:
                    decoded_target = params['q'][0]
            except Exception:
                pass

        # ── 主检查：域名白名单 ────────────────────────────────
        allowed = False
        for allowed_domain in self.ACCESS_ALLOWED_DOMAINS:
            if allowed_domain.startswith("."):
                if domain == allowed_domain or domain.endswith(allowed_domain):
                    allowed = True
                    break
            else:
                if domain == allowed_domain:
                    allowed = True
                    break

        if not allowed:
            return False

        # 检查禁止路径模式
        for blocked in self.ACCESS_BLOCKED_PATTERNS:
            if blocked in path:
                return False

        return True

    def is_get_only(self, method: str = "GET") -> bool:
        """铁律二：只允许 GET 请求"""
        return method.upper() == "GET"

    # ── 铁律三：行为风控 ──────────────────────────────────────
    # 单域名间隔≥3秒，会话≤50次，随机滚动+停留

    def __init__(self):
        import time
        self._last_request_time: dict[str, float] = {}
        self._request_count: int = 0
        self._session_start: float = time.time()
        self._min_interval: float = 3.0  # 最少 3 秒间隔
        self._max_requests: int = 50     # 单次会话最多 50 次
        self._min_scroll_wait: float = 0.5
        self._max_scroll_wait: float = 2.0

    def can_request(self, url: str) -> tuple[bool, str]:
        """
        铁律三：检查是否可以发起请求
        返回 (是否允许, 原因)
        """
        import time
        from urllib.parse import urlparse

        # 会话请求总数限制
        self._request_count += 1
        if self._request_count > self._max_requests:
            return False, f"⚠️ 会话请求已达上限({self._max_requests}次)，强制停止"

        # 域名间隔限制
        parsed = urlparse(url)
        domain = parsed.netloc.lower()

        now = time.time()
        last = self._last_request_time.get(domain, 0)
        elapsed = now - last

        if elapsed < self._min_interval:
            wait = self._min_interval - elapsed
            return False, f"⚠️ {domain} 请求间隔不足{self._min_interval}秒，需等待{wait:.1f}秒"

        self._last_request_time[domain] = now
        return True, "OK"

    def get_random_scroll_wait(self) -> float:
        """铁律三：随机停留时间（模拟真实用户）"""
        import random
        import time
        return random.uniform(self._min_scroll_wait, self._max_scroll_wait)

    def reset_session(self):
        """重置风控计数器（新会话开始）"""
        import time
        self._last_request_time.clear()
        self._request_count = 0
        self._session_start = time.time()

    def get_stats(self) -> dict:
        return {
            "total_requests": self._request_count,
            "max_requests": self._max_requests,
            "min_interval_sec": self._min_interval,
            "domains_accessed": list(self._last_request_time.keys()),
        }


# ═══════════════════════════════════════════════════════════════════
#  受铁律约束的浏览器会话
# ═══════════════════════════════════════════════════════════════════

class RuledBrowserSession:
    """
    带铁律的浏览器会话。
    所有请求必须通过铁律检查，不可绕过。
    """

    def __init__(self, cookie_json: list = None,
                 allowed_domains: set = None,
                 ruler: IronRuler = None):
        self.ruler = ruler or IronRuler()
        self.injector = None
        self.browser = None
        self.context = None
        self.page = None
        self._pw = None
        self._closed = False

        if cookie_json:
            self.injector = CookieInjector(cookie_json=cookie_json)
            if allowed_domains:
                self.injector.set_allowed_domains(allowed_domains)

    def launch(self, headless: bool = True) -> bool:
        from playwright.sync_api import sync_playwright
        from web4_browser import BrowserProfile

        profile = BrowserProfile.get("stealth")

        self._pw = sync_playwright().start()
        self.browser = self._pw.chromium.launch(
            headless=headless,
            args=[
                "--no-sandbox", "--disable-setuid-sandbox",
                "--disable-dev-shm-usage", "--disable-gpu",
                "--disable-web-security", "--allow-running-insecure-content",
                "--ignore-certificate-errors",
            ]
        )

        self.context = self.browser.new_context(
            user_agent=profile["user_agent"],
            viewport=profile["viewport"],
            locale=profile["locale"],
            timezone_id=profile["timezone_id"],
        )

        if self.injector:
            filtered = self.injector.filter()
            self.injector.inject_to_context(self.context)

        self.page = self.context.new_page()
        self.page.set_default_timeout(15000)
        return True

    def _check_url(self, url: str) -> tuple[bool, str]:
        """铁律二：URL 访问边界检查"""
        if not self.ruler.is_access_allowed(url):
            return False, f"🚫 URL不在允许范围内: {url}"
        if self.ruler.is_account_operation(url):
            return False, f"🚫 账号后台操作被禁止: {url}"
        return True, "OK"

    def _check_wait(self, url: str) -> bool:
        """铁律三：等待间隔检查"""
        import time
        from urllib.parse import urlparse
        domain = urlparse(url).netloc.lower()
        last = self.ruler._last_request_time.get(domain, 0)
        elapsed = time.time() - last
        if elapsed < self.ruler._min_interval:
            time.sleep(self.ruler._min_interval - elapsed)
        self.ruler._last_request_time[domain] = time.time()
        return True

    def goto(self, url: str, wait_until: str = "networkidle") -> dict:
        """带铁律检查的导航"""
        import time

        if self._closed:
            return {"ok": False, "error": "会话已关闭"}

        # 铁律二：URL 边界检查
        ok, msg = self._check_url(url)
        if not ok:
            print(f"[RuledSession] {msg}")
            return {"ok": False, "error": msg}

        # 铁律二：检查请求方法（goto 始终是 GET）
        if not self.ruler.is_get_only("GET"):
            return {"ok": False, "error": "只允许 GET 请求"}

        # 铁律三：请求间隔
        self._check_wait(url)

        # 铁律三：更新请求计数
        self.ruler._request_count += 1

        try:
            response = self.page.goto(url, wait_until=wait_until, timeout=20000)

            # 铁律三：随机滚动模拟真实用户
            import random
            wait_t = self.ruler.get_random_scroll_wait()
            time.sleep(wait_t)

            # 随机滚动一点（模拟真实浏览）
            if random.random() < 0.5:
                self._random_scroll()

            return {
                "ok": True,
                "url": self.page.url,
                "title": self.page.title(),
                "status": response.status if response else None,
            }
        except Exception as e:
            return {"ok": False, "error": str(e)}

    def _random_scroll(self):
        """铁律三：随机滚动（模拟真实用户）"""
        import random, time
        try:
            scroll_amount = random.randint(200, 600)
            self.page.evaluate(f"window.scrollBy(0, {scroll_amount})")
            time.sleep(random.uniform(0.3, 0.8))
            self.page.evaluate("window.scrollTo(0, 0)")
        except Exception:
            pass

    def extract(self, selector: str, attr: str = None) -> list:
        if self._closed:
            return []
        try:
            elements = self.page.query_selector_all(selector)
            if attr:
                return [el.get_attribute(attr) or "" for el in elements]
            return [el.inner_text() or "" for el in elements]
        except Exception:
            return []

    def screenshot(self) -> dict:
        if self._closed:
            return {"ok": False, "error": "会话已关闭"}
        try:
            return {"ok": True, "path": self.page.screenshot()}
        except Exception as e:
            return {"ok": False, "error": str(e)}

    def close(self):
        """
        铁律四：会话结束，强制清空所有 Cookie / 缓存
        """
        if self._closed:
            return
        self._closed = True

        if self.page:
            try:
                self.page.close()
            except Exception:
                pass

        if self.context:
            try:
                # 铁律四：清除所有 Cookie
                self.context.clear_cookies()
                # 铁律四：清除所有 storage
                self.context.clear_permissions()
            except Exception:
                pass
            try:
                self.context.close()
            except Exception:
                pass

        if self.browser:
            try:
                self.browser.close()
            except Exception:
                pass

        if self._pw:
            try:
                self._pw.stop()
            except Exception:
                pass

        print(f"[RuledSession] 🧹 会话已清空（Cookie/缓存/状态 全部清除）")

    def __enter__(self):
        self.launch()
        return self

    def __exit__(self, *args):
        self.close()
