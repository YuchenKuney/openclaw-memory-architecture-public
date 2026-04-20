#!/usr/bin/env python3
"""
Web4.0 Cooking 注入引擎
供坤哥配置 AI 的网页研究行为策略。

用法（在我的会话中）：
  from web4_cooker import COOKER, cooking

  # 方式1：装饰器
  @cooking(language="zh", strategy="deep")
  def my_research():
      from web4_controller import research
      return research("量子计算最新进展")

  # 方式2：上下文管理器
  with COOKER.profile(language="zh", avoid_sites=["baidu.com"]):
      from web4_controller import research
      research("AI安全研究")

  # 方式3：直接注入
  COOKER.set(language="en", priority="latest", max_pages=5)
"""

import os
import sys
import json
import time
import datetime
import threading
from pathlib import Path
from typing import Callable, Optional
from functools import wraps


# ══════════════════════════════════════════════════════════════
#  Cooking 预设配置
# ══════════════════════════════════════════════════════════════

COOKING_PRESETS = {
    # 坤哥常用预设
    "中文优先": {
        "language": "zh",
        "priority": "latest",
        "max_pages": 10,
        "strategy": "standard",
        "scroll_behavior": "normal",
        "extract_fields": ["title", "text", "meta"],
    },
    "学术研究": {
        "language": "en",
        "priority": "latest",
        "max_pages": 15,
        "strategy": "deep",
        "scroll_behavior": "full",
        "extract_fields": ["title", "text", "meta", "links", "network"],
        "avoid_sites": ["zhihu.com", "baidu.com"],
    },
    "快速扫描": {
        "language": "any",
        "priority": "relevant",
        "max_pages": 5,
        "strategy": "brief",
        "scroll_behavior": "none",
        "extract_fields": ["title", "links"],
    },
    "最新资讯": {
        "language": "zh",
        "priority": "latest",
        "max_pages": 8,
        "strategy": "standard",
        "scroll_behavior": "normal",
        "extract_fields": ["title", "text", "images"],
    },
    "技术深度": {
        "language": "en",
        "priority": "relevant",
        "max_pages": 20,
        "strategy": "deep",
        "scroll_behavior": "full",
        "extract_fields": ["title", "text", "meta", "links", "network"],
        "wait_time": 2.0,
    },
    "无图模式": {
        "language": "any",
        "priority": "relevant",
        "max_pages": 10,
        "strategy": "standard",
        "extract_fields": ["title", "text"],
        "block_ads": True,
    },
}


# ══════════════════════════════════════════════════════════════
#  Cooking 全局状态
# ══════════════════════════════════════════════════════════════

class CookingState:
    """全局 Cooking 状态（线程安全）"""

    def __init__(self):
        self._lock = threading.RLock()
        self._preset: Optional[str] = None
        self._custom: dict = {}
        self._history: list[dict] = []  # 记录每次 cooking
        self._stats: dict = {
            "total_researches": 0,
            "total_pages": 0,
            "by_preset": {},
        }

    def set_preset(self, name: str):
        """切换预设"""
        with self._lock:
            if name not in COOKING_PRESETS:
                raise ValueError(f"未知预设: {name}，可用: {list(COOKING_PRESETS.keys())}")
            self._preset = name
            self._custom = {}
            self._log("preset", name)

    def set(self, **kwargs):
        """直接设置参数（覆盖预设）"""
        with self._lock:
            self._preset = None
            self._custom.update(kwargs)
            self._log("custom", kwargs)

    def get(self) -> dict:
        """获取当前 cooking 配置"""
        with self._lock:
            if self._preset:
                base = COOKING_PRESETS[self._preset]
            else:
                base = {}
            return {**base, **self._custom}

    def clear(self):
        """清除自定义配置（恢复到默认）"""
        with self._lock:
            self._preset = None
            self._custom = {}

    def _log(self, kind: str, value):
        self._history.append({
            "kind": kind,
            "value": value,
            "at": datetime.datetime.now().isoformat(),
        })

    def record_research(self, pages_count: int):
        with self._lock:
            self._stats["total_researches"] += 1
            self._stats["total_pages"] += pages_count
            preset = self._preset or "custom"
            self._stats["by_preset"][preset] = self._stats["by_preset"].get(preset, 0) + 1

    def stats(self) -> dict:
        with self._lock:
            return {
                **self._stats,
                "current": self.get(),
                "preset": self._preset,
                "history_size": len(self._history),
            }


# ══════════════════════════════════════════════════════════════
#  全局单例
# ══════════════════════════════════════════════════════════════

_COOKING = CookingState()


# ══════════════════════════════════════════════════════════════
#  便捷访问 API
# ══════════════════════════════════════════════════════════════

class CookingInterface:
    """对外暴露的 Cooking 接口"""

    PRESETS = COOKING_PRESETS

    def set_preset(self, name: str):
        _COOKING.set_preset(name)
        return self

    def set(self, **kwargs):
        _COOKING.set(**kwargs)
        return self

    def get(self) -> dict:
        return _COOKING.get()

    def clear(self):
        _COOKING.clear()
        return self

    def stats(self) -> dict:
        return _COOKING.stats()

    def profile(self, **kwargs):
        """
        上下文管理器：在其中设置临时的 cooking。
        用法：
          with COOKER.profile(language="zh"):
              research("量子计算")
        """
        return _CookingContextManager(kwargs)

    def preset(self, name: str):
        """装饰器：为一个函数设置 cooking"""
        def decorator(fn: Callable):
            @wraps(fn)
            def wrapper(*args, **kw):
                prev = _COOKING.get()
                _COOKING.set_preset(name) if name else _COOKING.clear()
                try:
                    return fn(*args, **kw)
                finally:
                    _COOKING.clear()
                    _COOKING.set(**prev)
            return wrapper
        return decorator

    def inject(self, **kwargs):
        """装饰器：为一个函数注入自定义 cooking"""
        def decorator(fn: Callable):
            @wraps(fn)
            def wrapper(*args, **kw):
                prev = _COOKING.get()
                _COOKING.set(**kwargs)
                try:
                    return fn(*args, **kw)
                finally:
                    _COOKING.clear()
                    _COOKING.set(**prev)
            return wrapper
        return decorator

    def list_presets(self) -> list[str]:
        return list(COOKING_PRESETS.keys())

    def describe_preset(self, name: str) -> dict:
        if name not in COOKING_PRESETS:
            return {}
        return {
            "name": name,
            "config": COOKING_PRESETS[name],
        }


class _CookingContextManager:
    """临时 cooking 上下文"""

    def __init__(self, overrides: dict):
        self.overrides = overrides
        self._prev: dict = {}

    def __enter__(self):
        self._prev = _COOKING.get()
        _COOKING.set(**self.overrides)
        return _COOKING

    def __exit__(self, *args):
        _COOKING.clear()
        _COOKING.set(**self._prev)


# 全局单例
COOKER = CookingInterface()


# ══════════════════════════════════════════════════════════════
#  装饰器形式的 cooking（最常用）
# ══════════════════════════════════════════════════════════════

def cooking(**kwargs):
    """
    装饰器：为函数应用 cooking 配置。
    用法：
      @cooking(language="zh", strategy="deep")
      def research_quantum():
          from web4_controller import research
          return research("量子计算最新进展")
    """
    return COOKER.inject(**kwargs)


# ══════════════════════════════════════════════════════════════
#  研究钩子（可选：自动化记录每次研究）
# ══════════════════════════════════════════════════════════════

class ResearchHook:
    """
    研究钩子：在 research() 调用前后自动执行。
    可用于：记录日志、发送通知、更新记忆文件。
    """

    _hooks: list[Callable] = []

    @classmethod
    def register(cls, fn: Callable):
        cls._hooks.append(fn)

    @classmethod
    def before(cls, query: str, cooking: dict):
        for h in cls._hooks:
            try:
                h.before(query, cooking)
            except Exception:
                pass

    @classmethod
    def after(cls, result: dict, cooking: dict):
        for h in cls._hooks:
            try:
                h.after(result, cooking)
            except Exception:
                pass
        _COOKING.record_research(result.get("total_pages", 0))


# 内置钩子：写入记忆文件
class _MemoryHook:
    """自动将研究历史写入记忆文件"""

    def __init__(self):
        self.log_file = Path("/root/.openclaw/workspace/memory/research_log.md")

    def before(self, query: str, cooking: dict):
        entry = f"\n## 研究记录 {datetime.datetime.now().strftime('%Y-%m-%d %H:%M')}\n\n"
        entry += f"- **主题**: {query}\n"
        entry += f"- **Cooking**: `{json.dumps(cooking, ensure_ascii=False)}`\n"
        entry += f"- **状态**: 进行中\n"
        self.log_file.parent.mkdir(parents=True, exist_ok=True)
        self.log_file.append_text(entry)

    def after(self, result: dict, cooking: dict):
        entry = f"- **完成**: {result.get('total_pages', 0)} 页, "
        entry += f"{len(result.get('results', []))} 条结果\n"
        entry += f"- **访问页面**: {', '.join(result.get('pages_visited', [])[:3])}...\n"
        # 追加到已有条目
        try:
            content = self.log_file.read_text()
            content = content.replace("- **状态**: 进行中\n", entry)
            self.log_file.write_text(content)
        except Exception:
            pass


# 注册内置钩子
ResearchHook.register(_MemoryHook())


# ══════════════════════════════════════════════════════════════
#  Cooking Dashboard（坤哥可以查看状态）
# ══════════════════════════════════════════════════════════════

def show_dashboard():
    """打印 Cooking 状态面板"""
    stats = COOKER.stats()
    print()
    print("╔══════════════════════════════════════════════╗")
    print("║  🍳 Web4.0 Cooking Dashboard                ║")
    print("╠══════════════════════════════════════════════╣")
    print(f"║  当前预设: {stats.get('preset') or 'custom':<28}║")
    cfg = stats.get('current', {})
    print(f"║  语言: {cfg.get('language', 'any'):<35}║")
    print(f"║  策略: {cfg.get('strategy', 'standard'):<34}║")
    print(f"║  优先级: {cfg.get('priority', 'relevant'):<31}║")
    print(f"║  最大页数: {cfg.get('max_pages', 10):<31}║")
    print("╠══════════════════════════════════════════════╣")
    print(f"║  总研究次数: {stats.get('total_researches', 0):<28}║")
    print(f"║  总访问页面: {stats.get('total_pages', 0):<28}║")
    print("╠══════════════════════════════════════════════╣")
    print("║  预设列表:                                   ║")
    for name in COOKER.list_presets():
        print(f"║    • {name:<42}║")
    print("╚══════════════════════════════════════════════╝")
    print()
    print("切换预设示例：")
    print('  COOKER.set_preset("中文优先")')
    print('  COOKER.set(language="en", priority="latest")')
    print()


if __name__ == "__main__":
    show_dashboard()
