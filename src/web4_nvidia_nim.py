#!/usr/bin/env python3
"""
Web4.0 NVIDIA NIM API 调用封装
基于 NVIDIA NIM（AI Foundation Endpoints）的 LLM 调用。

用法：
  from web4_nvidia_nim import NVIDIA

  # 方式1：直接调用
  nvidia = NVIDIA()
  reply = nvidia.chat("解释量子计算")
  print(reply)

  # 方式2：指定模型
  nvidia = NVIDIA(model="meta/llama-3.1-70b-instruct")
  reply = nvidia.chat("用中文回复")

  # 方式3：流式输出
  for chunk in nvidia.stream("写一个快猫"):
      print(chunk, end="")
"""

import os
import json
import urllib.request
from typing import Optional


class NVIDIA:
    """
    NVIDIA NIM API 封装。
    支持 133+ 模型（Llama3.1 70B / Mixtral / Nemotron 等）。
    """

    BASE_URL = "https://integrate.api.nvidia.com/v1"
    DEFAULT_MODEL = "meta/llama-3.1-70b-instruct"

    # 可用模型速查
    MODELS = {
        # 免费模型（通过 NVIDIA NIM）
        "llama70b":   "meta/llama-3.1-70b-instruct",
        "llama8b":    "meta/llama-3.1-8b-instruct",
        "mixtral":    "mistralai/mixtral-8x7b-instruct",
        "nemotron":    "nvidia/llama-3.1-nemotron-70b-instruct",
        "mistral":     "mistralai/mistral-large",
        "qwen":        "qwen/qwen2.5-72b-instruct",
        "qwen7":       "qwen/qwen2.5-7b-instruct",
        "gemma27b":    "google/gemma-2-27b-instruct",
        "gemma9b":     "google/gemma-2-9b-it",
        "codellama":   "meta/codellama-70b",
        "deepseek":    "deepseek-ai/deepseek-v3.1-terminus",
        "deepseekcoder": "deepseek-ai/deepseek-coder-6.7b-instruct",
    }

    def __init__(self, model: str = None, api_key: str = None, temperature: float = 0.7):
        self.model = model or os.environ.get("NVIDIA_API_MODEL", self.DEFAULT_MODEL)
        self.temperature = temperature
        self.api_key = api_key or os.environ.get(
            "NVIDIA_API_KEY",
            "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"
        )

    def _build_request(self, payload: dict) -> urllib.request.Request:
        url = f"{self.BASE_URL}/chat/completions"
        data = json.dumps(payload).encode("utf-8")
        return urllib.request.Request(
            url,
            data=data,
            headers={
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json",
            },
        )

    def chat(self, prompt: str, system: str = None, max_tokens: int = 1024,
             temperature: float = None) -> str:
        """
        简单对话调用。
        返回 AI 回复的文本。
        """
        messages = []
        if system:
            messages.append({"role": "system", "content": system})
        messages.append({"role": "user", "content": prompt})

        payload = {
            "model": self.model,
            "messages": messages,
            "max_tokens": max_tokens,
            "temperature": temperature if temperature is not None else self.temperature,
            "stream": False,
        }

        req = self._build_request(payload)
        try:
            with urllib.request.urlopen(req, timeout=60) as resp:
                result = json.loads(resp.read())
                return result["choices"][0]["message"]["content"]
        except urllib.error.HTTPError as e:
            error_body = e.read().decode("utf-8", errors="replace")
            raise RuntimeError(f"NVIDIA API 错误 {e.code}: {error_body}")

    def stream(self, prompt: str, system: str = None, max_tokens: int = 1024,
               temperature: float = None):
        """
        流式对话调用。
        返回一个生成器，逐字产出回复。

        用法：
          for word in nvidia.stream("写一个故事"):
              print(word, end="", flush=True)
        """
        messages = []
        if system:
            messages.append({"role": "system", "content": system})
        messages.append({"role": "user", "content": prompt})

        payload = {
            "model": self.model,
            "messages": messages,
            "max_tokens": max_tokens,
            "temperature": temperature if temperature is not None else self.temperature,
            "stream": True,
        }

        req = self._build_request(payload)
        try:
            with urllib.request.urlopen(req, timeout=120) as resp:
                for line in resp:
                    line = line.decode("utf-8", errors="replace").strip()
                    if line.startswith("data: "):
                        data_str = line[6:]
                        if data_str == "[DONE]":
                            break
                        try:
                            data = json.loads(data_str)
                            delta = data["choices"][0]["delta"]
                            if "content" in delta:
                                yield delta["content"]
                        except Exception:
                            pass
        except urllib.error.HTTPError as e:
            error_body = e.read().decode("utf-8", errors="replace")
            raise RuntimeError(f"NVIDIA API 错误 {e.code}: {error_body}")

    def list_models(self) -> list[str]:
        """列出所有可用模型"""
        req = urllib.request.Request(
            f"{self.BASE_URL}/models",
            headers={"Authorization": f"Bearer {self.api_key}", "Accept": "application/json"},
        )
        with urllib.request.urlopen(req, timeout=20) as resp:
            data = json.loads(resp.read())
            return [m["id"] for m in data.get("data", [])]


# ══════════════════════════════════════════════════════════════
#  快速测试
# ══════════════════════════════════════════════════════════════

if __name__ == "__main__":
    print("NVIDIA NIM API 测试")
    print("=" * 50)

    nvidia = NVIDIA()
    print(f"使用模型: {nvidia.model}")
    print()

    # 简单对话测试
    print("【测试1】简单对话")
    reply = nvidia.chat("用一句话解释量子计算", max_tokens=50)
    print(f"Q: 用一句话解释量子计算")
    print(f"A: {reply}")
    print()

    # 中文测试
    print("【测试2】中文对话")
    reply = nvidia.chat(
        "你是一个电商专家，用中文分析 Shopee 在东南亚市场的竞争格局",
        max_tokens=200
    )
    print(f"Q: Shopee 东南亚市场分析")
    print(f"A: {reply[:200]}...")
    print()

    print("✅ NVIDIA NIM API 测试完成")
