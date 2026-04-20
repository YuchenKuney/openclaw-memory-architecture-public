#!/usr/bin/env python3
"""
Web4.0 Shopee 印尼市场研究器
铁律浏览器抓取 + NVIDIA NIM 分析，完整链路。

用法：
  python3 web4_shopee_researcher.py --region id    # 印尼（默认）
  python3 web4_shopee_researcher.py --region my    # 马来西亚
  python3 web4_shopee_researcher.py --region ph    # 菲律宾
"""

import os
import sys
import json
import time
import datetime
from pathlib import Path

# ── 模块路径 ──────────────────────────────────────────────────
WORKSPACE = Path("/root/.openclaw/workspace")
sys.path.insert(0, str(WORKSPACE))

# ── 核心模块 ──────────────────────────────────────────────────
from web4_controller import research_with_ruler, CookingEngine
from web4_nvidia_nim import NVIDIA


# ══════════════════════════════════════════════════════════════
#  研究器主类
# ══════════════════════════════════════════════════════════════

class ShopeeResearcher:
    """
    Shopee 市场研究器。
    铁律：只爬取公开页面，不碰任何私密/账号数据。
    """

    # Shopee 各站点公开域名
    REGION_DOMAINS = {
        "id": ["shopee.co.id", ".shopee.co.id"],
        "my": ["shopee.my", ".shopee.my"],
        "ph": ["shopee.ph", ".shopee.ph"],
        "sg": ["shopee.sg", ".shopee.sg"],
        "th": ["shopee.th", ".shopee.th"],
        "vn": ["shopee.vn", ".shopee.vn"],
        "tw": ["shopee.tw", ".shopee.tw"],
    }

    def __init__(self, region: str = "id"):
        self.region = region
        self.sites = self.REGION_DOMAINS.get(region, ["shopee.com", ".shopee.com"])
        self.nvidia = NVIDIA()
        self.results = []
        self.search_queries = []
        self.started_at = None
        self.finished_at = None

    # ── Step 1: 搜索阶段 ───────────────────────────────────

    def search(self, queries: list[str], cooking: dict = None,
               max_pages_per_query: int = 3, verbose: bool = True) -> dict:
        """
        搜索 Shopee 相关公开信息。
        每个 query 独立搜索，结果合并。
        """
        self.started_at = datetime.datetime.now().isoformat()
        all_results = []
        all_pages = []
        all_errors = []

        if cooking is None:
            cooking = {
                "language": "zh",
                "strategy": "standard",
                "priority": "latest",
                "max_pages": max_pages_per_query,
                "avoid_sites": ["baidu.com", "zhihu.com"],  # 不需要中文站
            }

        def vprint(msg):
            if verbose:
                ts = datetime.datetime.now().strftime("%H:%M:%S")
                print(f"[{ts}] {msg}")

        vprint(f"🔍 开始 Shopee {self.region.upper()} 市场研究")
        vprint(f"🍳 Cooking: {json.dumps(cooking, ensure_ascii=False)}")

        for i, query in enumerate(queries):
            vprint(f"\n{'='*50}")
            vprint(f"【Query {i+1}/{len(queries)}】{query}")
            vprint(f"{'='*50}")

            try:
                result = research_with_ruler(
                    query=query,
                    sites=self.sites,
                    cooking={**cooking, "max_pages": max_pages_per_query},
                    verbose=verbose,
                    use_cookie=True,
                )

                all_pages.extend(result.get("pages_visited", []))
                all_results.extend(result.get("results", []))
                all_errors.extend(result.get("errors", []))

                vprint(f"  → 获得 {len(result.get('results', []))} 条结果")

            except Exception as e:
                vprint(f"  ❌ Query 失败: {e}")
                all_errors.append({"query": query, "error": str(e)})

        self.results = all_results
        self.finished_at = datetime.datetime.now().isoformat()

        return {
            "region": self.region,
            "queries": queries,
            "pages_visited": list(set(all_pages)),
            "total_results": len(all_results),
            "results": all_results,
            "errors": all_errors,
            "started_at": self.started_at,
            "finished_at": self.finished_at,
        }

    # ── Step 2: AI 分析阶段 ─────────────────────────────────

    def analyze(self, research_data: dict,
                system_prompt: str = None, max_tokens: int = 2048) -> str:
        """
        用 NVIDIA NIM (Llama3.1 70B) 分析抓取到的内容。
        """
        if not research_data.get("results"):
            return "❌ 没有抓取到任何内容，无法分析。"

        # 构建分析上下文
        context = self._build_context(research_data)

        if system_prompt is None:
            system_prompt = (
                f"你是一个专业的东南亚电商市场分析师。"
                f"请根据以下从 Shopee {self.region.upper()} 市场抓取的公开信息，"
                f"用中文撰写一份客观、结构化的市场分析报告。"
                f"只引用提供的信息，不要编造数据。"
            )

        prompt = f"""## 背景任务
分析 Shopee {self.region.upper()} 市场的以下公开信息：

## 抓取到的公开信息
{context}

## 分析要求
请从以下几个角度分析（用中文输出）：
1. **市场概况**：Shopee 在该市场的地位、用户规模
2. **热门品类**：哪些品类在该市场表现最好
3. **竞争格局**：主要竞争对手（lazada、tiktok shop 等）
4. **趋势洞察**：2025-2026 年的主要变化和趋势
5. **数据来源说明**：列出抓取到信息的具体页面 URL

请用中文回答，结构清晰，数据客观。"""

        print(f"\n🤖 NVIDIA NIM (Llama3.1 70B) 分析中...")
        reply = self.nvidia.chat(
            prompt,
            system=system_prompt,
            max_tokens=max_tokens,
        )

        return reply

    def _build_context(self, research_data: dict) -> str:
        """将搜索结果构建成分析上下文"""
        lines = []
        for i, r in enumerate(research_data.get("results", [])):
            title = r.get("title", "")
            text = r.get("text", "")[:800]  # 限制长度
            url = r.get("url", "")
            lines.append(f"\n### 来源 {i+1}\n标题: {title}\nURL: {url}\n内容:\n{text}\n")

        if not lines:
            return "（无抓取结果）"

        return "\n".join(lines)

    # ── Step 3: 完整流程 ────────────────────────────────────

    def full_research(self, queries: list[str],
                      analyze: bool = True,
                      save: bool = True) -> dict:
        """
        完整研究流程：
        1. 搜索抓取（铁律浏览器）
        2. AI 分析（NVIDIA NIM）
        3. 保存结果
        """
        print(f"\n{'#'*60}")
        print(f"#  Shopee {self.region.upper()} 市场研究 — 完整流程")
        print(f"#  铁律：只爬取公开页面，不碰任何私密数据")
        print(f"{'#'*60}\n")

        # Step 1: 搜索
        search_data = self.search(queries, verbose=True)

        print(f"\n📊 搜索完成:")
        print(f"   访问页面: {len(search_data['pages_visited'])} 个")
        print(f"   抓取结果: {search_data['total_results']} 条")
        print(f"   错误数:   {len(search_data['errors'])} 个")

        # Step 2: 分析
        analysis = None
        if analyze and search_data["total_results"] > 0:
            print()
            analysis = self.analyze(search_data)
            print(f"\n📋 分析结果:\n{analysis[:500]}...")
        else:
            print("\n⏭️ 跳过 AI 分析（无抓取结果）")

        # Step 3: 保存
        output = {
            "region": self.region,
            "queries": queries,
            "search_data": search_data,
            "analysis": analysis,
            "saved_at": datetime.datetime.now().isoformat(),
        }

        if save:
            save_dir = Path("/root/.openclaw/web4_sandbox/results")
            save_dir.mkdir(parents=True, exist_ok=True)
            ts = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
            save_file = save_dir / f"shopee_{self.region}_{ts}.json"
            save_file.write_text(
                json.dumps(output, indent=2, ensure_ascii=False),
                encoding="utf-8"
            )
            print(f"\n💾 结果已保存: {save_file}")

        return output


# ══════════════════════════════════════════════════════════════
#  命令行入口
# ══════════════════════════════════════════════════════════════

if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Shopee 市场研究器")
    parser.add_argument("--region", "-r", default="id",
                        choices=["id", "my", "ph", "sg", "th", "vn", "tw"],
                        help="区域代码（默认: id=印尼）")
    parser.add_argument("--query", "-q", action="append",
                        help="搜索关键词（可多次指定）")
    parser.add_argument("--no-analyze", action="store_true",
                        help="跳过 AI 分析（只搜索）")
    parser.add_argument("--max-pages", type=int, default=3,
                        help="每个 query 最大抓取页数（默认: 3）")
    args = parser.parse_args()

    # 默认 queries
    if args.query:
        queries = args.query
    else:
        queries = [
            f"Shopee Indonesia market share 2025 2026",
            f"Shopee Indonesia popular categories electronics fashion",
            f"Shopee vs Lazada Indonesia competition 2025",
            f"TikTok Shop vs Shopee Indonesia ecommerce 2026",
        ]

    researcher = ShopeeResearcher(region=args.region)
    result = researcher.full_research(
        queries=queries,
        analyze=not args.no_analyze,
        save=True,
    )

    print(f"\n✅ Shopee {args.region.upper()} 市场研究完成！")
