from __future__ import annotations

import os
from dataclasses import dataclass

import requests


@dataclass(frozen=True)
class OpenAIResult:
    ok: bool
    text: str
    error: str = ""


def polish_report_with_openai(markdown: str, model: str | None = None) -> OpenAIResult:
    """Optional cloud LLM polishing step.

    The deterministic report remains the source of truth. This function only
    improves Chinese readability when OPENAI_API_KEY is configured.
    """

    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        return OpenAIResult(ok=False, text=markdown, error="OPENAI_API_KEY 未配置。")

    selected_model = model or os.getenv("OPENAI_MODEL", "gpt-4.1-mini")
    prompt = (
        "请在不新增事实、不新增数值、不删除风险提示的前提下，润色下面的中文内部研发报告。"
        "保留 Markdown 结构，保留所有证据来源和计算告警。\n\n"
        f"{markdown}"
    )
    try:
        response = requests.post(
            "https://api.openai.com/v1/responses",
            headers={
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json",
            },
            json={
                "model": selected_model,
                "input": prompt,
            },
            timeout=60,
        )
        response.raise_for_status()
        payload = response.json()
        text = _extract_output_text(payload)
        if not text:
            return OpenAIResult(ok=False, text=markdown, error="OpenAI 返回为空，已保留本地报告。")
        return OpenAIResult(ok=True, text=text)
    except Exception as exc:  # pragma: no cover - network fallback
        return OpenAIResult(ok=False, text=markdown, error=f"OpenAI 调用失败：{exc}")


def _extract_output_text(payload: dict) -> str:
    if isinstance(payload.get("output_text"), str):
        return payload["output_text"]
    chunks: list[str] = []
    for item in payload.get("output", []):
        for content in item.get("content", []):
            if content.get("type") in {"output_text", "text"} and content.get("text"):
                chunks.append(content["text"])
    return "\n".join(chunks).strip()
