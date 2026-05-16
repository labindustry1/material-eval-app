"""Unified LLM polishing provider supporting OpenAI and DeepSeek.

Both backends share an OpenAI-compatible chat-completions API. Provider is
auto-detected from environment variables. Priority:

  1. ``DEEPSEEK_API_KEY``  → DeepSeek (default model: ``deepseek-chat``)
  2. ``OPENAI_API_KEY``    → OpenAI   (default model: ``gpt-4.1-mini``)

The deterministic local report remains the source of truth. The LLM only
improves Chinese readability and is forbidden from adding facts or
removing risk disclaimers.
"""

from __future__ import annotations

import os
from dataclasses import dataclass

import requests


@dataclass(frozen=True)
class PolishResult:
    ok: bool
    text: str
    provider: str = ""
    error: str = ""


_POLISH_PROMPT = (
    "你是材料工程报告编辑。请在不新增事实、不新增数值、不删除风险提示和告警的前提下，"
    "润色下面的中文内部研发报告，让表达更专业、流畅。"
    "保留所有 Markdown 结构、表格、数值区间、证据来源和计算告警。"
    "不要改任何数字、单位、材料名、零件名。\n\n"
)


def polish_report_with_llm(markdown: str, model: str | None = None) -> PolishResult:
    """Try DeepSeek first, fall back to OpenAI, then to local-only.

    Returns a PolishResult; never raises.
    """
    deepseek_key = os.getenv("DEEPSEEK_API_KEY", "").strip()
    openai_key = os.getenv("OPENAI_API_KEY", "").strip()

    if deepseek_key:
        return _call_chat_completion(
            api_key=deepseek_key,
            url="https://api.deepseek.com/v1/chat/completions",
            model=model or os.getenv("DEEPSEEK_MODEL", "deepseek-chat"),
            markdown=markdown,
            provider="deepseek",
        )
    if openai_key:
        return _call_chat_completion(
            api_key=openai_key,
            url="https://api.openai.com/v1/chat/completions",
            model=model or os.getenv("OPENAI_MODEL", "gpt-4.1-mini"),
            markdown=markdown,
            provider="openai",
        )
    return PolishResult(
        ok=False,
        text=markdown,
        provider="none",
        error="未配置 DEEPSEEK_API_KEY 或 OPENAI_API_KEY，已保留本地确定性报告。",
    )


def _call_chat_completion(
    *,
    api_key: str,
    url: str,
    model: str,
    markdown: str,
    provider: str,
) -> PolishResult:
    try:
        response = requests.post(
            url,
            headers={
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json",
            },
            json={
                "model": model,
                "messages": [
                    {"role": "system", "content": "你是严谨的材料工程报告编辑助手。"},
                    {"role": "user", "content": _POLISH_PROMPT + markdown},
                ],
                "temperature": 0.3,
            },
            timeout=120,
        )
        response.raise_for_status()
        payload = response.json()
        text = _extract_chat_text(payload)
        if not text:
            return PolishResult(
                ok=False,
                text=markdown,
                provider=provider,
                error=f"{provider} 返回为空，已保留本地报告。",
            )
        return PolishResult(ok=True, text=text, provider=provider)
    except Exception as exc:
        return PolishResult(
            ok=False,
            text=markdown,
            provider=provider,
            error=f"{provider} 调用失败：{exc}",
        )


def _extract_chat_text(payload: dict) -> str:
    """OpenAI-compatible chat completions response: choices[0].message.content."""
    choices = payload.get("choices") or []
    if not choices:
        return ""
    message = choices[0].get("message") or {}
    content = message.get("content")
    if isinstance(content, str):
        return content.strip()
    return ""
