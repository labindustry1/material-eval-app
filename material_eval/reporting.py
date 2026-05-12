from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import datetime

from material_eval.catalog import PartTemplate
from material_eval.computation import CalculationResult
from material_eval.evidence import EvidenceCard
from material_eval.laminates import LaminateResult
from material_eval.materials import MaterialCandidate
from material_eval.report_schema import StructuredReport, build_structured_report
from material_eval.scoring import Scorecard, build_scorecard


@dataclass(frozen=True)
class ReportDraft:
    title: str
    filename: str
    markdown: str
    report_json: dict
    structured_report: StructuredReport
    scorecard: Scorecard


def build_internal_report(
    *,
    material: MaterialCandidate,
    part: PartTemplate,
    dimensions: dict[str, float],
    calculation: CalculationResult,
    laminate_result: LaminateResult | None = None,
    evidence_cards: list[EvidenceCard],
) -> ReportDraft:
    now = datetime.now().strftime("%Y-%m-%d %H:%M")
    title = f"{material.name}在{part.name}中的可行性初筛报告"
    filename = _safe_filename(f"{material.name}-{part.name}-初筛报告.md")

    verdict, risks = _verdict(calculation, evidence_cards)
    metrics_md = "\n".join(
        f"| {metric.name} | {metric.value:.4g} | {metric.unit} | {metric.description} |"
        for metric in calculation.metrics
    )
    dims_md = "\n".join(f"- {key}: {value:g} mm" for key, value in dimensions.items())
    evidence_md = "\n".join(
        f"- [{idx}] {card.source_type} `{card.source}`"
        f"（{card.retrieval_method}, score={card.score:.3g}）：{card.summary}"
        for idx, card in enumerate(evidence_cards, start=1)
    ) or "- 暂未检索到可用内部资料。"
    assumptions_md = "\n".join(f"- {item}" for item in calculation.assumptions)
    warnings_md = "\n".join(f"- {item}" for item in calculation.warnings) or "- 暂无计算模块告警。"
    risks_md = "\n".join(f"- {item}" for item in risks)
    laminate_md = _laminate_markdown(laminate_result)
    scorecard = build_scorecard(
        material=material,
        part=part,
        calculation=calculation,
        evidence_cards=evidence_cards,
        risks=risks,
    )
    scorecard_md = _scorecard_markdown(scorecard)
    structured_report = build_structured_report(
        title=title,
        created_at=now,
        material=material,
        part=part,
        calculation=calculation,
        laminate_result=laminate_result,
        evidence_cards=evidence_cards,
        verdict=verdict,
        risks=risks,
    )
    claims_md = _claims_markdown(structured_report)

    markdown = f"""# {title}

生成时间：{now}

## 1. 研发结论

{verdict}

该报告为内部研发 MVP 初筛，不构成量产、认证、准入或客户承诺。

## 1.1 透明评分卡

{scorecard_md}

## 2. 材料输入

- 材料名称：{material.name}
- 材料类别：{material.category}
- 密度：{material.density_g_cm3:.4g} g/cm³
- 抗拉强度：{material.tensile_strength_mpa:.4g} MPa
- 弹性模量：{material.elastic_modulus_gpa:.4g} GPa
- 比强度：{material.specific_strength:.4g}
- 比模量：{material.specific_modulus:.4g}
- 备注：{material.notes or "无"}

## 3. 目标零部件与工况

- 应用领域：{part.domain}
- 零部件：{part.name}
- 拓扑：{part.topology}
- 约束摘要：{part.constraint}

几何输入：

{dims_md}

## 4. 工程初筛结果

| 指标 | 数值 | 单位 | 说明 |
| --- | ---: | --- | --- |
{metrics_md}

{laminate_md}

## 5. 证据来源

{evidence_md}

## 5.1 结构化结论追踪

{claims_md}

## 6. 计算假设

{assumptions_md}

## 7. 风险与缺口

{risks_md}

计算告警：

{warnings_md}

## 8. 建议下一步

- 补齐材料测试条件：温度、湿度、方向、应变率、样条尺寸、测试标准。
- 对当前目标零部件建立基准材料对照实验。
- 若初筛结果有价值，再进入复合铺层、疲劳、冲击或真实 FEA/显式动力学仿真。
"""

    report_json = {
        "title": title,
        "created_at": now,
        "material": material.__dict__,
        "part": {
            "domain": part.domain,
            "name": part.name,
            "topology": part.topology,
            "constraint": part.constraint,
        },
        "dimensions": dimensions,
        "calculation": {
            "version": calculation.version,
            "topology": calculation.topology,
            "metrics": [metric.__dict__ for metric in calculation.metrics],
            "assumptions": list(calculation.assumptions),
            "warnings": list(calculation.warnings),
        },
        "laminate": _laminate_json(laminate_result),
        "evidence": [card.__dict__ for card in evidence_cards],
        "verdict": verdict,
        "risks": risks,
        "scorecard": scorecard.model_dump(),
        "structured_report": structured_report.model_dump(),
    }
    return ReportDraft(
        title=title,
        filename=filename,
        markdown=markdown,
        report_json=report_json,
        structured_report=structured_report,
        scorecard=scorecard,
    )


def _verdict(calculation: CalculationResult, evidence_cards: list[EvidenceCard]) -> tuple[str, list[str]]:
    risks: list[str] = []
    if not evidence_cards:
        risks.append("当前没有可引用的内部资料，报告只能作为计算草案。")
    if calculation.warnings:
        risks.extend(calculation.warnings)
    if calculation.topology in {"STRAP", "CORRUGATED"}:
        risks.append("该拓扑的疲劳/冲击/吸能表现高度依赖实验或更高保真仿真。")

    blocking = any("Unsupported" in item for item in calculation.warnings)
    if blocking:
        verdict = "当前拓扑尚无可用计算模块，暂不建议进入方案判断。"
    elif risks:
        verdict = "可以进入内部研发初筛讨论，但必须补充关键实验和适用边界验证后再做项目决策。"
    else:
        verdict = "当前输入下具备继续内部初筛的基础，可进入基准材料对比和敏感性分析。"
    return verdict, risks or ["暂无阻断性风险；仍需通过实验或仿真确认关键工况。"]


def _laminate_markdown(laminate_result: LaminateResult | None) -> str:
    if laminate_result is None:
        return ""
    warnings = "\n".join(f"- {item}" for item in laminate_result.warnings) or "- 暂无铺层模块告警。"
    return f"""
### 4.1 复合铺层初筛

- 方法：{laminate_result.method}
- 总厚度：{laminate_result.total_thickness_mm:.4g} mm
- 等效 Ex：{laminate_result.ex_gpa:.4g} GPa
- 等效 Ey：{laminate_result.ey_gpa:.4g} GPa
- 等效 Gxy：{laminate_result.gxy_gpa:.4g} GPa
- 等效 νxy：{laminate_result.nuxy:.4g}

铺层告警：

{warnings}
"""


def _laminate_json(laminate_result: LaminateResult | None) -> dict | None:
    if laminate_result is None:
        return None
    return {
        "method": laminate_result.method,
        "total_thickness_mm": laminate_result.total_thickness_mm,
        "a_matrix": [list(row) for row in laminate_result.a_matrix],
        "ex_gpa": laminate_result.ex_gpa,
        "ey_gpa": laminate_result.ey_gpa,
        "gxy_gpa": laminate_result.gxy_gpa,
        "nuxy": laminate_result.nuxy,
        "warnings": list(laminate_result.warnings),
    }


def _claims_markdown(structured_report: StructuredReport) -> str:
    rows = [
        "| Claim | 类型 | 置信度 | 来源绑定 |",
        "| --- | --- | ---: | --- |",
    ]
    for claim in structured_report.claims:
        bindings = "；".join(f"{item.source_type}:{item.reference_label}" for item in claim.bindings)
        rows.append(f"| {claim.claim_id}: {claim.text} | {claim.claim_type} | {claim.confidence:.2f} | {bindings} |")
    return "\n".join(rows)


def _scorecard_markdown(scorecard: Scorecard) -> str:
    rows = [
        f"总分：**{scorecard.total_score:.2f}/100**。{scorecard.interpretation}",
        "",
        "| 维度 | 分数 | 权重 | 说明 |",
        "| --- | ---: | ---: | --- |",
    ]
    for dimension in scorecard.dimensions:
        rows.append(
            f"| {dimension.name} | {dimension.score:.2f} | {dimension.weight:.0%} | {dimension.rationale} |"
        )
    return "\n".join(rows)


def _safe_filename(value: str) -> str:
    cleaned = re.sub(r'[\\/:*?"<>|]+', "-", value).strip(" .")
    return cleaned or "材料可行性初筛报告.md"
