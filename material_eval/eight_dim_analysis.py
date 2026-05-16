"""八维商业剖析（lifted-and-adapted from legacy/app_legacy_streamlit.py）。

调用 LLM（DeepSeek 优先，OpenAI 兜底）把"材料 + 零件 + 计算结果 + 证据"汇总
为商业级 8 维剖析，每维含定性论证 + 现役基准 vs 本案设计的对比数值。

非工程计算！本模块输出是 LLM 论证产物，仅作业务展示和商业沟通用，
不能替代失效准则、不确定度传播、工况包络这些工程模块。
"""

from __future__ import annotations

import json
import os
from dataclasses import dataclass, field
from typing import Any

import requests


@dataclass(frozen=True)
class DimensionSlice:
    """单个维度的剖析。"""
    dim: str               # "1. 静态载荷" / "2. 动态疲劳" 等
    details: tuple[str, ...]
    chart_metric: str       # e.g. "倍数", "寿命", "良率"
    base_val: float
    new_val: float


@dataclass(frozen=True)
class GrandVerdict:
    summary: str
    strengths: tuple[str, ...]
    weaknesses: tuple[str, ...]


@dataclass(frozen=True)
class EightDimReport:
    ok: bool
    market_tier: str = ""
    market_verdict: str = ""
    dimensions: tuple[DimensionSlice, ...] = field(default_factory=tuple)
    summary: str = ""
    grand_verdict: GrandVerdict | None = None
    reference_sources: tuple[str, ...] = field(default_factory=tuple)
    provider: str = ""
    error: str = ""
    raw_json: str = ""


_DIM_NAMES = (
    "1. 静态载荷",
    "2. 动态疲劳",
    "3. 几何工艺",
    "4. 专属抗性",
    "5. 微观混合",
    "6. 经济降本",
    "7. ESG 表现",
    "8. 行业壁垒",
)


def analyze_eight_dimensions(
    *,
    material_name: str,
    part_name: str,
    domain: str,
    constraint: str,
    calculation_summary: str,
    evidence_summary: str = "",
    timeout: int = 120,
) -> EightDimReport:
    """生成八维商业剖析。DeepSeek 优先，缺密钥则用 OpenAI；都没就返回 ok=False。"""
    deepseek_key = os.getenv("DEEPSEEK_API_KEY", "").strip()
    openai_key = os.getenv("OPENAI_API_KEY", "").strip()
    if deepseek_key:
        url = "https://api.deepseek.com/v1/chat/completions"
        model = os.getenv("DEEPSEEK_MODEL", "deepseek-chat")
        api_key = deepseek_key
        provider = "deepseek"
    elif openai_key:
        url = "https://api.openai.com/v1/chat/completions"
        model = os.getenv("OPENAI_MODEL", "gpt-4.1-mini")
        api_key = openai_key
        provider = "openai"
    else:
        return EightDimReport(
            ok=False,
            error="未配置 DEEPSEEK_API_KEY 或 OPENAI_API_KEY，无法生成八维剖析。",
        )

    prompt = _build_prompt(
        material_name=material_name,
        part_name=part_name,
        domain=domain,
        constraint=constraint,
        calculation_summary=calculation_summary,
        evidence_summary=evidence_summary,
    )
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
                    {"role": "system", "content": "你是严谨的材料工程 + 商业战略联合分析师。输出严格 JSON。"},
                    {"role": "user", "content": prompt},
                ],
                "temperature": 0.2,
                "response_format": {"type": "json_object"},
            },
            timeout=timeout,
        )
        response.raise_for_status()
        payload = response.json()
        raw_text = payload["choices"][0]["message"]["content"]
        return _parse_response(raw_text, provider=provider)
    except Exception as exc:
        return EightDimReport(ok=False, error=f"{provider} 调用失败：{exc}", provider=provider)


def _build_prompt(
    *,
    material_name: str,
    part_name: str,
    domain: str,
    constraint: str,
    calculation_summary: str,
    evidence_summary: str,
) -> str:
    return f"""请以材料工程师 + 商业战略分析师的双重视角，对以下候选方案做商业级八维剖析。

候选方案：
- 材料：{material_name}
- 零部件：{part_name}（{domain}）
- 约束：{constraint}

工程计算摘要：
{calculation_summary}

证据摘要：
{evidence_summary or "（无）"}

请严格输出以下结构的 JSON（不要有任何其他文本）：

{{
  "market_tier": "高端高利润 / 中端可量产 / 边缘/不推荐 中的一种",
  "market_verdict": "一句话商业定位",
  "eight_dimensions": [
    {{
      "dim": "1. 静态载荷",
      "details": ["3-5 条工程定性论证（每条 30-60 字）"],
      "chart_metric": "倍数/比值/百分比/相对值 等单位标签",
      "base_val": <现役基准材料的数值>,
      "new_val": <本案材料的数值>
    }},
    {{ "dim": "2. 动态疲劳", "details": [...], "chart_metric": "寿命周期", "base_val": ..., "new_val": ... }},
    {{ "dim": "3. 几何工艺", "details": [...], "chart_metric": "良率(%)", "base_val": ..., "new_val": ... }},
    {{ "dim": "4. 专属抗性", "details": [...], "chart_metric": "保持率(%)", "base_val": ..., "new_val": ... }},
    {{ "dim": "5. 微观混合", "details": [...], "chart_metric": "优越度", "base_val": ..., "new_val": ... }},
    {{ "dim": "6. 经济降本", "details": [...], "chart_metric": "降本(%)", "base_val": ..., "new_val": ... }},
    {{ "dim": "7. ESG 表现", "details": [...], "chart_metric": "表现分", "base_val": ..., "new_val": ... }},
    {{ "dim": "8. 行业壁垒", "details": [...], "chart_metric": "认证周期(月)", "base_val": ..., "new_val": ... }}
  ],
  "summary": "八维切片整体小结（80-120 字）",
  "grand_verdict": {{
    "summary": "最终商业落地决议（红绿灯式陈词，60-100 字）",
    "strengths": ["3-5 条核心投产优势"],
    "weaknesses": ["3-5 条致命短板与风险"]
  }},
  "reference_sources": ["3-5 条数据来源（行业标准 / 学术文献 / 内部数据库）"]
}}

要求：
1. 所有数值有工程意义，base_val 和 new_val 的对比要能讲故事
2. details 严禁出现"很好""差不多"等模糊表达，每条要带具体的工程或商业判断
3. 风险与短板必须如实写出，不要因为是"候选方案"就回避
4. JSON 必须可被 json.loads 解析"""


def _parse_response(raw_text: str, *, provider: str) -> EightDimReport:
    """从 LLM 返回的可能含 markdown 包裹的文本中提取 JSON。"""
    text = raw_text.strip()
    if "```json" in text:
        text = text.split("```json", 1)[1].split("```", 1)[0].strip()
    elif text.startswith("```"):
        text = text.split("```", 2)[1].split("```", 1)[0].strip()
    try:
        data: dict[str, Any] = json.loads(text)
    except json.JSONDecodeError as exc:
        return EightDimReport(
            ok=False,
            error=f"LLM 返回的 JSON 无法解析：{exc}",
            provider=provider,
            raw_json=text[:1000],
        )

    dim_list = data.get("eight_dimensions") or []
    dimensions = tuple(
        DimensionSlice(
            dim=str(item.get("dim", _DIM_NAMES[idx % len(_DIM_NAMES)])),
            details=tuple(str(x) for x in (item.get("details") or [])),
            chart_metric=str(item.get("chart_metric", "")),
            base_val=float(item.get("base_val", 0) or 0),
            new_val=float(item.get("new_val", 0) or 0),
        )
        for idx, item in enumerate(dim_list)
    )

    gv = data.get("grand_verdict") or {}
    grand_verdict = GrandVerdict(
        summary=str(gv.get("summary", "")),
        strengths=tuple(str(x) for x in (gv.get("strengths") or [])),
        weaknesses=tuple(str(x) for x in (gv.get("weaknesses") or [])),
    )

    return EightDimReport(
        ok=True,
        market_tier=str(data.get("market_tier", "")),
        market_verdict=str(data.get("market_verdict", "")),
        dimensions=dimensions,
        summary=str(data.get("summary", "")),
        grand_verdict=grand_verdict,
        reference_sources=tuple(str(x) for x in (data.get("reference_sources") or [])),
        provider=provider,
        raw_json=text,
    )
