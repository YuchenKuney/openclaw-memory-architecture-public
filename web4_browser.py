#!/usr/bin/env python3
"""
Web4.0 无头浏览器控制
基于 Playwright，为 AI Agent 提供：
  - 网页导航（goto）
  - 元素提取（query_selector / extract_text）
  - 截图（screenshot）
  - JavaScript 执行
  - Cookie / Storage 管理
  - 标签页管理
  - 拦截请求（用于 AI 分析网络行为）
"""

import os
import sys
import json
import time
import threading
import urllib.parse
from pathlib import Path
from datetime import datetime
from typing import Optional

try:
    from playwright.sync_api import sync_playwright, Browser, Page, BrowserContext
except ImportError:
    print("❌ Playwright 未安装，运行: pip3 install playwright && python3 -m playwright install chromium")
    sys.exit(1)


class BrowserProfile:
    """浏览器配置文件"""
    HUMAN_PROFILES = {
        "stealth": {
            "user_agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                          "(KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36",
            "viewport": {"width": 1920, "height": 1080},
            "locale": "zh-CN",
            "timezone_id": "Asia/Shanghai",
            "permissions": ["geolocation"],
            "color_scheme": "light",
            "device_scale_factor": 1.0,
            "has_touch": False,
            "is_mobile": False,
            "navigator_platform": "Win32",
        },
        "mobile": {
            "user_agent": "Mozilla/5.0 (iPhone; CPU iPhone OS 17_0 like Mac OS X) "
                          "AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.0 "
                          "Mobile/15E148 Safari/604.1",
            "viewport": {"width": 390, "height": 844},
            "locale": "zh-CN",
            "timezone_id": "Asia/Shanghai",
            "permissions": ["geolocation"],
            "color_scheme": "light",
            "device_scale_factor": 3.0,
            "has_touch": True,
            "is_mobile": True,
            "navigator_platform": "iPhone",
        },
    }

    @classmethod
    def get(cls, name: str = "stealth"):
        return cls.HUMAN_PROFILES.get(name, cls.HUMAN_PROFILES["stealth"])


class ScreenshotCache:
    """截图缓存（避免重复截图浪费资源）"""

    def __init__(self, cache_dir: Path = Path("/root/.openclaw/web4_sandbox/.screenshots")):
        self.cache_dir = cache_dir
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        self._index: dict[str, dict] = {}

    def get(self, url: str) -> Optional[Path]:
        url_hash = str(hash(url))
        meta_file = self.cache_dir / f"{url_hash}.meta"
        if meta_file.exists():
            try:
                meta = json.loads(meta_file.read_text())
                img_file = self.cache_dir / meta["filename"]
                if img_file.exists() and time.time() - meta["cached_at"] < 3600:
                    return img_file
            except Exception:
                pass
        return None

    def put(self, url: str, image_bytes: bytes, prefix: str = "screen") -> Path:
        url_hash = str(hash(url))
        ts = datetime.now().strftime("%Y%m%d%H%M%S")
        filename = f"{prefix}_{ts}_{url_hash[:8]}.png"
        img_file = self.cache_dir / filename
        img_file.write_bytes(image_bytes)
        meta = {
            "url": url,
            "filename": filename,
            "cached_at": time.time(),
            "size_bytes": len(image_bytes),
        }
        (self.cache_dir / f"{url_hash}.meta").write_text(json.dumps(meta))
        return img_file


class Web4Browser:
    """AI Agent 的无头浏览器控制对象"""

    def __init__(self, profile: str = "stealth", headless: bool = True,
                 container_mode: bool = False, container_pid: int = None):
        self.profile_name = profile
        self.profile = BrowserProfile.get(profile)
        self.headless = headless
        self.container_mode = container_mode
        self.container_pid = container_pid
        self._page: Optional[Page] = None
        self._context: Optional[BrowserContext] = None
        self._browser = None
        self._pw = None
        self._lock = threading.RLock()
        self._history: list[dict] = []
        self.screenshot_cache = ScreenshotCache()
        self.id = f"browser-{id(self):08x}"
        self.started_at = datetime.now().isoformat()
        self._requests: list[dict] = []
        self._responses: list[dict] = []

    # ── 浏览器生命周期 ───────────────────────────────────────

    def start(self) -> bool:
        try:
            self._pw = sync_playwright().start()
            self._browser = self._pw.chromium.launch(
                headless=self.headless,
                args=[
                    "--no-sandbox",
                    "--disable-setuid-sandbox",
                    "--disable-dev-shm-usage",
                    "--disable-gpu",
                    "--disable-web-security",
                    "--disable-features=IsolateOrigins,site-per-process",
                    "--allow-running-insecure-content",
                    "--ignore-certificate-errors",
                ]
            )

            ctx_options = {
                "user_agent": self.profile["user_agent"],
                "viewport": self.profile["viewport"],
                "locale": self.profile["locale"],
                "timezone_id": self.profile["timezone_id"],
                "color_scheme": self.profile["color_scheme"],
                "device_scale_factor": self.profile["device_scale_factor"],
                "has_touch": self.profile["has_touch"],
                "permissions": self.profile.get("permissions", []),
            }

            self._context = self._browser.new_context(**ctx_options)
            self._inject_stealth_js()
            self._setup_interceptors()
            self._page = self._context.new_page()
            self._page.set_default_timeout(30000)

            print(f"[{self.id}] 浏览器已启动 (profile={self.profile_name})")
            return True
        except Exception as e:
            print(f"[{self.id}] 启动失败: {e}")
            return False

    def _inject_stealth_js(self):
        stealth_script = """
        Object.defineProperty(navigator, 'webdriver', {
            get: () => undefined, configurable: true
        });
        window.chrome = { runtime: {}, app: {}, loadTimes: function() {}, csi: function() {} };
        const _query = window.navigator.permissions.query;
        window.navigator.permissions.query = (parameters) =>
            parameters.name === 'notifications' ?
            Promise.resolve({ state: Notification.permission }) : _query(parameters);
        Object.defineProperty(navigator, 'plugins', {
            get: () => [1, 2, 3, 4, 5], configurable: true
        });
        Object.defineProperty(navigator, 'languages', {
            get: () => ['zh-CN', 'zh', 'en-US', 'en'], configurable: true
        });
        """
        try:
            self._context.add_init_script(stealth_script)
        except Exception:
            pass

    def _setup_interceptors(self):
        self._requests = []
        self._responses = []

        def on_request(request):
            pd = None
            try:
                raw_pd = request.post_data
                if isinstance(raw_pd, bytes) and len(raw_pd) < 1024:
                    try:
                        pd = raw_pd.decode("utf-8", errors="replace")
                    except Exception:
                        pd = f"<binary {len(raw_pd)}b>"
                elif isinstance(raw_pd, bytes):
                    pd = f"<binary {len(raw_pd)}b>"
            except Exception:
                pd = None
            self._requests.append({
                "url": request.url,
                "method": request.method,
                "resource_type": request.resource_type,
                "post_data": pd,
                "timestamp": datetime.now().isoformat(),
            })

        def on_response(response):
            self._responses.append({
                "url": response.url,
                "status": response.status,
                "timestamp": datetime.now().isoformat(),
            })

        if self._page:
            self._page.on("request", on_request)
            self._page.on("response", on_response)

    # ── 导航 ────────────────────────────────────────────────

    def goto(self, url: str, wait_until: str = "networkidle", timeout: int = 30000) -> dict:
        if not self._page:
            return {"ok": False, "error": "浏览器未启动"}
        try:
            if not urllib.parse.urlparse(url).scheme:
                url = "https://" + url
            print(f"[{self.id}] → {url}")
            response = self._page.goto(url, wait_until=wait_until, timeout=timeout)
            self._history.append({
                "url": self._page.url,
                "title": self.title(),
                "timestamp": datetime.now().isoformat(),
            })
            return {
                "ok": True,
                "url": self._page.url,
                "title": self.title(),
                "status": response.status if response else None,
            }
        except Exception as e:
            return {"ok": False, "error": str(e)}

    def click(self, selector: str, timeout: int = 5000) -> dict:
        if not self._page:
            return {"ok": False, "error": "浏览器未启动"}
        try:
            self._page.click(selector, timeout=timeout)
            time.sleep(0.3)
            return {"ok": True, "url": self._page.url}
        except Exception as e:
            return {"ok": False, "error": str(e)}

    def type(self, selector: str, text: str, delay: int = 100) -> dict:
        if not self._page:
            return {"ok": False, "error": "浏览器未启动"}
        try:
            self._page.fill(selector, text)
            return {"ok": True}
        except Exception as e:
            return {"ok": False, "error": str(e)}

    # ── 内容提取 ──────────────────────────────────────────────

    def extract(self, selector: str, attr: str = None) -> list[str]:
        if not self._page:
            return []
        try:
            elements = self._page.query_selector_all(selector)
            if attr:
                return [el.get_attribute(attr) or "" for el in elements]
            return [el.inner_text() or "" for el in elements]
        except Exception:
            return []

    def extract_one(self, selector: str, attr: str = None, default: str = "") -> str:
        results = self.extract(selector, attr)
        return results[0] if results else default

    def extract_all(self) -> dict:
        if not self._page:
            return {"text": "", "html": "", "url": "", "title": ""}
        text = ""
        try:
            if self._page.query_selector("body"):
                text = self._page.inner_text("body") or ""
        except Exception:
            pass
        return {
            "text": text.strip(),
            "html": self._page.content() if self._page else "",
            "url": self._page.url if self._page else "",
            "title": self.title(),
        }

    def query(self, selector: str) -> bool:
        return self._page is not None and self._page.query_selector(selector) is not None

    def count(self, selector: str) -> int:
        if not self._page:
            return 0
        return len(self._page.query_selector_all(selector))

    # ── 截图 ─────────────────────────────────────────────────

    def screenshot(self, path: str = None, full_page: bool = False) -> dict:
        if not self._page:
            return {"ok": False, "error": "浏览器未启动"}
        try:
            cached = self.screenshot_cache.get(self._page.url) if not path else None
            if cached:
                return {"ok": True, "path": str(cached), "cached": True}

            try:
                self._page.evaluate("window.scrollTo(0, 0)")
                time.sleep(0.3)
            except Exception:
                pass

            if path:
                self._page.screenshot(path=path, full_page=full_page)
                saved_path = path
            else:
                img_bytes = self._page.screenshot(full_page=full_page)
                saved_path_obj = self.screenshot_cache.put(self._page.url, img_bytes)
                saved_path = str(saved_path_obj)

            return {"ok": True, "path": saved_path, "url": self._page.url, "cached": False}
        except Exception as e:
            return {"ok": False, "error": str(e)}

    # ── JavaScript ────────────────────────────────────────────

    def eval_js(self, script: str):
        if not self._page:
            return None
        try:
            return self._page.evaluate(f"(() => {{ {script} }})()")
        except Exception:
            return None

    # ── 滚动 ─────────────────────────────────────────────────

    def scroll_to_bottom(self, step: int = 500):
        if not self._page:
            return
        try:
            total = self._page.evaluate("document.body.scrollHeight")
            pos = 0
            while pos < total:
                self._page.evaluate(f"window.scrollTo(0, {pos})")
                time.sleep(0.3)
                pos += step
                try:
                    total = self._page.evaluate("document.body.scrollHeight")
                except Exception:
                    break
        except Exception:
            pass

    def scroll_to_top(self):
        if self._page:
            try:
                self._page.evaluate("window.scrollTo(0, 0)")
            except Exception:
                pass

    # ── 等待 ─────────────────────────────────────────────────

    def wait_for_selector(self, selector: str, timeout: int = 10000) -> bool:
        if not self._page:
            return False
        try:
            self._page.wait_for_selector(selector, timeout=timeout)
            return True
        except Exception:
            return False

    # ── Cookie / Storage ──────────────────────────────────────

    def set_cookie(self, name: str, value: str, domain: str = None):
        if not self._context:
            return
        if not domain and self._page:
            try:
                domain = urllib.parse.urlparse(self._page.url).netloc
            except Exception:
                domain = ".example.com"
        self._context.add_cookies([{
            "name": name, "value": value, "domain": domain, "path": "/",
        }])

    def get_cookies(self) -> list[dict]:
        if self._context:
            return self._context.cookies()
        return []

    def clear_cookies(self):
        if self._context:
            self._context.clear_cookies()

    # ── 工具方法 ──────────────────────────────────────────────

    def title(self) -> str:
        return self._page.title() if self._page else ""

    def url(self) -> str:
        return self._page.url if self._page else ""

    def is_loaded(self) -> bool:
        return self._page is not None and self._page.url != "about:blank"

    def get_requests(self) -> list[dict]:
        return self._requests

    def get_responses(self) -> list[dict]:
        return self._responses

    def get_network_summary(self) -> dict:
        if not self._requests:
            return {"total_requests": 0, "by_type": {}}
        by_type: dict = {}
        for req in self._requests:
            t = req.get("resource_type", "unknown")
            by_type[t] = by_type.get(t, 0) + 1
        domains = []
        for r in self._requests:
            try:
                d = urllib.parse.urlparse(r["url"]).netloc
                if d:
                    domains.append(d)
            except Exception:
                pass
        return {
            "total_requests": len(self._requests),
            "by_type": by_type,
            "domains": list(set(domains)),
        }

    def clear_history(self):
        self._requests.clear()
        self._responses.clear()
        self._history.clear()

    # ── 关闭 ─────────────────────────────────────────────────

    def close(self):
        if self._page:
            try:
                self._page.close()
            except Exception:
                pass
            self._page = None

    def quit(self):
        self.close()
        if self._context:
            try:
                self._context.close()
            except Exception:
                pass
            self._context = None
        if self._browser:
            try:
                self._browser.close()
            except Exception:
                pass
            self._browser = None
        if self._pw:
            try:
                self._pw.stop()
            except Exception:
                pass
            self._pw = None
        print(f"[{self.id}] 浏览器已关闭")


# ══════════════════════════════════════════════════════════════
#  浏览器池
# ══════════════════════════════════════════════════════════════

class BrowserPool:
    def __init__(self, max_size: int = 3):
        self.max_size = max_size
        self._pool: list[Web4Browser] = []
        self._in_use: set[Web4Browser] = set()
        self._lock = threading.Lock()
        self._auto_id = 0

    def acquire(self, profile: str = "stealth", headless: bool = True) -> Web4Browser:
        with self._lock:
            while self._pool:
                b = self._pool.pop()
                if b.is_loaded():
                    self._in_use.add(b)
                    return b
            if len(self._in_use) < self.max_size:
                self._auto_id += 1
                b = Web4Browser(profile=profile, headless=headless)
                b.id = f"pool-browser-{self._auto_id:03d}"
                b.start()
                self._in_use.add(b)
                return b
            raise RuntimeError(f"浏览器池已满（max={self.max_size}），请等待空闲实例")

    def release(self, browser: Web4Browser):
        with self._lock:
            if browser in self._in_use:
                self._in_use.remove(browser)
                browser.clear_history()
                browser.clear_cookies()
                self._pool.append(browser)

    def close_all(self):
        with self._lock:
            for b in list(self._pool) + list(self._in_use):
                b.quit()
            self._pool.clear()
            self._in_use.clear()

    def status(self) -> dict:
        return {
            "total": len(self._pool) + len(self._in_use),
            "available": len(self._pool),
            "in_use": len(self._in_use),
            "max": self.max_size,
        }


_pool = BrowserPool(max_size=3)


def get_pool() -> BrowserPool:
    return _pool


class BrowserSession:
    def __init__(self, profile: str = "stealth", headless: bool = True, pool: bool = True):
        self.profile = profile
        self.headless = headless
        self.pool = pool
        self._pool_instance: Optional[BrowserPool] = None
        self._browser: Optional[Web4Browser] = None

    def __enter__(self) -> Web4Browser:
        if self.pool:
            self._pool_instance = get_pool()
            self._browser = self._pool_instance.acquire(self.profile, self.headless)
        else:
            self._browser = Web4Browser(self.profile, self.headless)
            self._browser.start()
        return self._browser

    def __exit__(self, exc_type, exc_val, exc_tb):
        if self._browser:
            if self.pool and self._pool_instance:
                self._pool_instance.release(self._browser)
            else:
                self._browser.quit()


if __name__ == "__main__":
    print("Web4.0 无头浏览器")
    print("=" * 50)

    print("\n[测试] 浏览器池")
    pool = get_pool()
    print(f"池状态: {pool.status()}")

    with BrowserSession(pool=True) as browser:
        print(f"获取到浏览器: {browser.id}")
        result = browser.goto("https://example.com")
        print(f"导航结果: {result}")
        print(f"页面标题: {browser.title()}")
        shot = browser.screenshot()
        print(f"截图: {shot}")
        net = browser.get_network_summary()
        print(f"网络请求: {net}")

    print(f"\n池状态: {pool.status()}")
    print("\n✅ 测试完成")
