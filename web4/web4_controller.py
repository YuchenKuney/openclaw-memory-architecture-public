#!/usr/bin/env python3
"""
Web4.0 AI 控制接口
供 AI Agent（我）直接调用的 Python API。

用法示例（在我的会话中直接调用）：
  from web4_controller import research
  result = research(
      query="量子计算最新进展",
      sites=["arxiv.org", "nature.com"],
      cooking={"language": "zh", "max_pages": 5}
  )

烹饪注入（cooking）示例：
  research(query="...", cooking={
      "language": "zh",           # 只看中文
      "avoid_sites": ["baidu.com"], # 避开某些站
      "strategy": "deep",          # deep=深度阅读 brief=快速扫描
      "priority": "latest",        # latest=最新优先 relevant=相关优先
      "extract_fields": ["title", "abstract", "authors", "date"]
  })
"""

import os
import sys
import json
import time
import datetime
import threading
from pathlib import Path
from typing import Optional

# 导入浏览器核心
from web4_browser import Web4Browser, BrowserSession, get_pool
from web4_container import manager, Web4Container

# 结果存储
RESULTS_DIR = Path("/root/.openclaw/web4_sandbox/results")
RESULTS_DIR.mkdir(parents=True, exist_ok=True)


# ══════════════════════════════════════════════════════════════
#  Cooking 引擎
# ══════════════════════════════════════════════════════════════

class CookingEngine:
    """
    烹饪注入引擎 — 定制 AI 的网页研究行为。
    坤哥可以给各种 cooking 指令，我在这里解析并应用到浏览器行为。
    """

    DEFAULT_COOKING = {
        "language": "any",          # zh | en | any
        "avoid_sites": [],          # 避开的域名列表
        "strategy": "standard",     # brief | standard | deep
        "priority": "relevant",      # latest | relevant
        "extract_fields": ["title", "url", "text"],
        "max_pages": 10,
        "headless": True,
        "profile": "stealth",
        "scroll_behavior": "normal", # none | normal | full
        "wait_time": 1.0,           # 页面操作后等待秒数
        "block_ads": True,
        "stealth": True,
    }

    def __init__(self, cooking: dict = None):
        self.cooking = {**self.DEFAULT_COOKING, **(cooking or {})}

    def apply(self, url: str) -> bool:
        """判断是否允许访问此 URL（cooking 过滤）"""
        from urllib.parse import urlparse
        parsed = urlparse(url)
        domain = parsed.netloc.lower()

        # 避开域名
        for avoid in self.cooking.get("avoid_sites", []):
            if avoid.lower() in domain:
                return False
        return True

    def get_wait_time(self) -> float:
        """根据策略返回页面等待时间"""
        strategy = self.cooking.get("strategy", "standard")
        wait = self.cooking.get("wait_time", 1.0)
        if strategy == "deep":
            return wait * 2
        elif strategy == "brief":
            return wait * 0.5
        return wait

    def get_scroll_behavior(self) -> str:
        return self.cooking.get("scroll_behavior", "normal")

    def build_search_url(self, query: str, engine: str = "bing") -> str:
        """根据 cooking 语言和优先级构建搜索 URL"""
        import urllib.parse

        lang = self.cooking.get("language", "any")
        priority = self.cooking.get("priority", "relevant")

        # 决定搜索语言参数
        setlang = "zh-cn" if lang == "zh" else "en-us" if lang == "en" else "en-us"

        q = urllib.parse.quote_plus(query)
        if engine == "bing":
            # Bing HTML 搜索（无 JS，适合 headless）
            return f"https://www.bing.com/search?q={q}&setlang={setlang}&hl={setlang}"
        elif engine == "duckduckgo":
            # DuckDuckGo HTML（备选）
            return f"https://duckduckgo.com/html/?q={q}&hl={lang}"
        else:
            # 默认 Bing
            return f"https://www.bing.com/search?q={q}"

    def extract_page(self, browser: Web4Browser, fields: list = None) -> dict:
        """根据 cooking 提取页面内容"""
        if fields is None:
            fields = self.cooking.get("extract_fields", ["title", "url", "text"])

        result = {
            "url": browser.url(),
            "title": browser.title(),
            "extracted_at": datetime.datetime.now().isoformat(),
        }

        if "text" in fields:
            content = browser.extract_all()
            result["text"] = content["text"][:5000]  # 限制长度
            result["html"] = content.get("html", "")[:2000]

        if "links" in fields:
            links = []
            for el in browser.extract("a[href]", attr="href")[:20]:
                if el and el.startswith("http"):
                    links.append(el)
            result["links"] = links

        if "images" in fields:
            result["images"] = browser.extract("img[src]", attr="src")[:10]

        if "meta" in fields:
            result["meta"] = {
                "description": browser.extract_one(
                    'meta[name="description"]', attr="content", default=""),
                "keywords": browser.extract_one(
                    'meta[name="keywords"]', attr="content", default=""),
                "author": browser.extract_one(
                    'meta[name="author"]', attr="content", default=""),
            }

        if "network" in fields:
            result["network_summary"] = browser.get_network_summary()

        # 截图
        if "screenshot" in fields:
            shot = browser.screenshot()
            result["screenshot"] = shot.get("path", "")

        return result


# ══════════════════════════════════════════════════════════════
#  核心研究函数（供 AI 直接调用）
# ══════════════════════════════════════════════════════════════

def research(
    query: str,
    sites: list[str] = None,
    cooking: dict = None,
    output_file: str = None,
    verbose: bool = True,
) -> dict:
    """
    AI 研究网页的核心函数。

    参数：
      query      : 研究主题
      sites      : 指定网站列表（可选，e.g. ["arxiv.org", "nature.com"]）
      cooking    : 烹饪注入配置（见 CookingEngine）
      output_file: 结果保存路径（可选）
      verbose    : 是否打印进度

    返回：
      {
        "query": "...",
        "pages_visited": [...],
        "results": [...],   # 每页提取内容
        "total_pages": N,
        "cooking_applied": {...},
        "started_at": "...",
        "finished_at": "...",
      }
    """
    cooker = CookingEngine(cooking)
    started_at = datetime.datetime.now().isoformat()
    pages_visited = []
    results = []
    errors = []

    def vprint(msg):
        if verbose:
            ts = datetime.datetime.now().strftime("%H:%M:%S")
            print(f"[{ts}] {msg}")

    vprint(f"🍳 研究开始: {query}")
    if cooking:
        vprint(f"🍳 Cooking: {json.dumps(cooking, ensure_ascii=False)}")

    try:
        with BrowserSession(pool=True, profile=cooker.cooking.get("profile", "stealth"),
                           headless=cooker.cooking.get("headless", True)) as browser:

            # ── 搜索阶段（使用 Bing，兼容无 JS 环境）──────────
            search_url = cooker.build_search_url(query, engine="bing")
            vprint(f"🔍 搜索: {search_url}")

            nav = browser.goto(search_url, wait_until="domcontentloaded")
            if not nav.get("ok"):
                errors.append(f"搜索失败: {nav.get('error')}")
                vprint(f"❌ 搜索失败: {nav.get('error')}")
            else:
                # 等待 Bing 结果渲染
                try:
                    browser.wait_for_selector("#b_results", timeout=10000)
                except Exception:
                    pass
                time.sleep(cooker.get_wait_time())

                # 提取搜索结果链接（Bing 重定向链接）
                search_links = []
                if sites:
                    # 指定站点的链接优先
                    for site in sites:
                        found = browser.extract(f'a[href*="{site}"]', attr="href")
                        search_links.extend(found[:5])
                else:
                    # Bing 搜索结果容器
                    found = browser.extract("#b_results a[href]", attr="href")
                    if not found:
                        found = browser.extract("a[href*='http']", attr="href")
                    search_links = found[:20]

                # 去重 + 过滤非 http(s) 链接
                seen = set()
                clean_links = []
                skip_prefixes = ("mailto:", "javascript:", "/images/", "/search?")
                for link in search_links:
                    # 去掉 Bing 内部链接
                    if any(link.startswith(p) for p in skip_prefixes):
                        continue
                    # 去掉锚点
                    if "#" in link:
                        link = link.split("#")[0]
                    if link and link.startswith("http") and link not in seen:
                        seen.add(link)
                        clean_links.append(link)

                vprint(f"🔗 找到 {len(clean_links)} 个链接，开始访问...")

                # ── 访问每个页面 ────────────────────────────────
                max_pages = cooker.cooking.get("max_pages", 10)
                for i, link in enumerate(clean_links[:max_pages]):
                    if not cooker.apply(link):
                        vprint(f"  ⏭️  跳过（cooking过滤）: {link}")
                        continue

                    vprint(f"  [{i+1}/{min(len(clean_links), max_pages)}] → {link}")
                    nav = browser.goto(link, wait_until="networkidle")
                    time.sleep(cooker.get_wait_time())

                    if nav.get("ok"):
                        pages_visited.append(link)

                        # 提取内容
                        page_result = cooker.extract_page(browser)
                        page_result["search_query"] = query
                        page_result["visited_at"] = datetime.datetime.now().isoformat()
                        results.append(page_result)

                        vprint(f"       ✅ {browser.title()[:60]}")

                        # 滚动行为
                        scroll = cooker.get_scroll_behavior()
                        if scroll == "full":
                            browser.scroll_to_bottom()
                        elif scroll == "normal":
                            browser.scroll_to_top()
                            time.sleep(0.5)
                    else:
                        vprint(f"       ❌ 导航失败: {nav.get('error')}")
                        errors.append({"url": link, "error": nav.get("error")})

            # ── 截图概览 ──────────────────────────────────────
            browser.screenshot()

    except Exception as e:
        errors.append({"fatal": str(e)})
        vprint(f"❌ 致命错误: {e}")

    finished_at = datetime.datetime.now().isoformat()

    output = {
        "query": query,
        "cooking_applied": cooker.cooking,
        "started_at": started_at,
        "finished_at": finished_at,
        "pages_visited": pages_visited,
        "total_pages": len(pages_visited),
        "results": results,
        "errors": errors,
    }

    # 保存结果
    if output_file:
        save_path = Path(output_file)
    else:
        safe_name = query.replace(" ", "_")[:40]
        ts = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
        save_path = RESULTS_DIR / f"research_{safe_name}_{ts}.json"

    save_path.parent.mkdir(parents=True, exist_ok=True)
    save_path.write_text(json.dumps(output, indent=2, ensure_ascii=False), encoding="utf-8")
    vprint(f"💾 结果已保存: {save_path}")

    vprint(f"\n📊 研究完成: {len(pages_visited)} 个页面, {len(results)} 条结果, {len(errors)} 个错误")
    return output


# ══════════════════════════════════════════════════════════════
#  快速浏览器操作（细粒度控制）
# ══════════════════════════════════════════════════════════════

class BrowserTool:
    """
    细粒度浏览器控制工具 — 供 AI 精确操作。
    用法：
      bt = BrowserTool()
      bt.goto("https://news.ycombinator.com")
      titles = bt.extract_text("a.titlelink")
      for t in titles:
          print(t)
      bt.screenshot()
      bt.close()
    """

    def __init__(self, profile: str = "stealth", headless: bool = True):
        self.browser: Optional[Web4Browser] = None
        self.profile = profile
        self.headless = headless
        self._pool = get_pool()

    def __enter__(self):
        self.browser = self._pool.acquire(self.profile, self.headless)
        return self

    def __exit__(self, *args):
        if self.browser:
            self._pool.release(self.browser)

    def goto(self, url: str, **kwargs):
        return self.browser.goto(url, **kwargs)

    def extract(self, selector: str, attr: str = None):
        return self.browser.extract(selector, attr)

    def extract_one(self, selector: str, attr: str = None, default: str = ""):
        return self.browser.extract_one(selector, attr, default)

    def extract_all(self):
        return self.browser.extract_all()

    def click(self, selector: str):
        return self.browser.click(selector)

    def type(self, selector: str, text: str):
        return self.browser.type(selector, text)

    def screenshot(self, path: str = None, **kwargs):
        return self.browser.screenshot(path, **kwargs)

    def eval_js(self, script: str):
        return self.browser.eval_js(script)

    def query(self, selector: str) -> bool:
        return self.browser.query(selector)

    def scroll_to_bottom(self):
        self.browser.scroll_to_bottom()

    def scroll_to_top(self):
        self.browser.scroll_to_top()

    def title(self) -> str:
        return self.browser.title()

    def url(self) -> str:
        return self.browser.url()

    def wait_for_selector(self, selector: str, timeout: int = 10000) -> bool:
        return self.browser.wait_for_selector(selector, timeout=timeout)

    def close(self):
        pass  # __exit__ 自动归还


# ══════════════════════════════════════════════════════════════
#  命令行接口（测试用）
# ══════════════════════════════════════════════════════════════

if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="Web4.0 AI 浏览器控制器")
    parser.add_argument("query", nargs="?", help="研究主题")
    parser.add_argument("--sites", nargs="*", help="指定网站列表")
    parser.add_argument("--cooking", default="{}", help='Cooking JSON，e.g. \'{"language":"zh","strategy":"deep"}\'')
    parser.add_argument("--output", help="结果保存路径")
    parser.add_argument("--headless", action="store_true", default=True)
    parser.add_argument("--no-headless", dest="headless", action="store_false")
    args = parser.parse_args()

    if not args.query:
        print("Web4.0 AI 浏览器控制器")
        print("=" * 50)
        print("用法:")
        print("  python3 web4_controller.py \"量子计算最新进展\"")
        print("  python3 web4_controller.py \"AI news\" --sites arxiv.org nature.com")
        print("  python3 web4_controller.py \"搜索\" --cooking '{\"language\":\"zh\",\"max_pages\":5}'")
        print()
        print("池状态:", get_pool().status())

        # 简单测试
        print("\n[浏览器池测试]")
        with BrowserSession(pool=True) as b:
            r = b.goto("https://example.com")
            print(f"example.com → {r['ok']} | {b.title()}")
            r2 = b.goto("https://httpbin.org/html")
            print(f"httpbin.org → {r2['ok']} | {b.title()}")
        print("✅ 归还成功，池状态:", get_pool().status())
        sys.exit(0)

    import json as _json
    try:
        cooking_cfg = _json.loads(args.cooking)
    except Exception:
        cooking_cfg = {}

    result = research(
        query=args.query,
        sites=args.sites,
        cooking=cooking_cfg,
        output_file=args.output,
        verbose=True,
    )

    print(f"\n📋 结果摘要 ({result['total_pages']} 页):")
    for r in result["results"]:
        print(f"  • {r.get('title', '(无标题)')[:80]}")
        if "text" in r:
            print(f"    {r['text'][:100]}...")
