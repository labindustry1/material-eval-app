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
from material_eval.strength import SafetyReport
from material_eval.uncertainty import EnvelopeReport


@dataclass(frozen=True)
class RefusalReport:
    markdown: str
    violations: tuple   # of Violation
    suggested_alternatives: tuple[str, ...]
    missing_data_hints: tuple[str, ...]


def build_refusal_report(
    *,
    material,
    part,
    condition,
    envelope_report: EnvelopeReport,
    suggested_alternatives: tuple[str, ...] = (),
    missing_data_hints: tuple[str, ...] = (),
) -> RefusalReport:
    lines = [
        f"# 未出具评估：{material.name} 用于 {part.name}",
        "",
        "## 拒绝原因",
        "",
        "本次评估未出具数值结论，因为以下工况输入超出材料适用域：",
        "",
        "| 工况轴 | 输入值 | 允许范围 | 数据来源 |",
        "| --- | --- | --- | --- |",
    ]
    for v in envelope_report.violations:
        lines.append(
            f"| {v.axis} | {v.input_value} | [{v.allowed_range[0]}, {v.allowed_range[1]}] | {v.source or '未声明'} |"
        )
    if suggested_alternatives:
        lines += ["", "## 已知适用该工况的同类材料", ""]
        lines += [f"- {name}" for name in suggested_alternatives]
    if missing_data_hints:
        lines += ["", "## 若要继续评估需要补充的数据", ""]
        lines += [f"- {hint}" for hint in missing_data_hints]
    lines += ["", "*本工具拒绝在材料适用域之外出具数值结论，以避免误导内部研发判断。*"]
    return RefusalReport(
        markdown="\n".join(lines),
        violations=envelope_report.violations,
        suggested_alternatives=tuple(suggested_alternatives),
        missing_data_hints=tuple(missing_data_hints),
    )


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
    envelope_report: EnvelopeReport | None = None,
    condition=None,
    safety_report: SafetyReport | None = None,
) -> ReportDraft:
    now = datetime.now().strftime("%Y-%m-%d %H:%M")
    title = f"{material.name}在{part.name}中的可行性初筛报告"
    filename = _safe_filename(f"{material.name}-{part.name}-初筛报告.md")

    verdict, risks = _verdict(calculation, evidence_cards)
    metrics_md = "\n".join(
        f"| {metric.name} | {metric.value.format()} | {metric.unit} | {metric.description} |"
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
    envelope_section_md = _envelope_section_markdown(envelope_report, condition)
    safety_section_md = _safety_section_markdown(safety_report)
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
- 密度：{material.density_g_cm3.typical:.4g} g/cm³
- 抗拉强度：{material.tensile_strength_mpa.typical:.4g} MPa
- 弹性模量：{material.elastic_modulus_gpa.typical:.4g} GPa
- 比强度：{material.specific_strength_typical:.4g}
- 比模量：{material.specific_modulus_typical:.4g}
- 备注：{material.notes or "无"}

## 3. 目标零部件与工况

- 应用领域：{part.domain}
- 零部件：{part.name}
- 拓扑：{part.topology}
- 约束摘要：{part.constraint}

几何输入：

{dims_md}

## 4. 工程初筛结果

| 指标 | 区间 | 单位 | 说明 |
| --- | ---: | --- | --- |
{metrics_md}

{laminate_md}
{safety_section_md}
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
{envelope_section_md}
## 不确定度说明

本报告所有数值以三点区间 (low / typical / high) 表达。
- 来源单点观察的属性按 confidence 自动展开（high=±5%, medium=±15%, low=±30%）
- 来源多点观察聚合 (min / 最高置信度 / max)
- 若需收窄某项区间，请补充供应商数据表、内部实验记录或行业标准引用，并在材料属性库 seed 中升级到三点区间。
"""

    report_json = {
        "title": title,
        "created_at": now,
        "material": {
            "name": material.name,
            "category": material.category,
            "density_g_cm3": material.density_g_cm3.typical,
            "tensile_strength_mpa": material.tensile_strength_mpa.typical,
            "elastic_modulus_gpa": material.elastic_modulus_gpa.typical,
            "notes": material.notes,
        },
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
            "metrics": [
                {
                    "name": metric.name,
                    "value": metric.value.typical,
                    "unit": metric.unit,
                    "description": metric.description,
                }
                for metric in calculation.metrics
            ],
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
- 总厚度：{laminate_result.total_thickness_mm.format()} mm
- 等效 Ex：{laminate_result.ex_gpa.format()} GPa
- 等效 Ey：{laminate_result.ey_gpa.format()} GPa
- 等效 Gxy：{laminate_result.gxy_gpa.format()} GPa
- 等效 νxy：{laminate_result.nuxy.format()}

铺层告警：

{warnings}
"""


def _laminate_json(laminate_result: LaminateResult | None) -> dict | None:
    if laminate_result is None:
        return None
    return {
        "method": laminate_result.method,
        "total_thickness_mm": laminate_result.total_thickness_mm.typical,
        "a_matrix": [list(row) for row in laminate_result.a_matrix],
        "ex_gpa": laminate_result.ex_gpa.typical,
        "ey_gpa": laminate_result.ey_gpa.typical,
        "gxy_gpa": laminate_result.gxy_gpa.typical,
        "nuxy": laminate_result.nuxy.typical,
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


def _envelope_section_markdown(envelope_report: EnvelopeReport | None, condition) -> str:
    """Build the '工况包络校验' section markdown.

    Returns an empty string when envelope_report is None (caller has not provided
    envelope information).  When envelope_report.has_declared_envelope is False
    a one-line notice is rendered instead of a table.
    """
    if envelope_report is None:
        return ""

    from material_eval.uncertainty import _ENVELOPE_AXES  # local import to avoid circular

    header = "\n## 工况包络校验\n"
    source_label = envelope_report.violations[0].source if envelope_report.violations else "未声明"
    # Try to extract a single source label from violations or a generic note.
    sources = {v.source for v in envelope_report.violations if v.source}
    source_display = "；".join(sorted(sources)) if sources else "未声明"
    header += f"\n数据来源：{source_display}\n"

    if not envelope_report.has_declared_envelope:
        return header + "\n该材料未声明适用域，工况校验跳过\n"

    # Build a set of violating axes for quick lookup
    violation_axes = {v.axis: v for v in envelope_report.violations}

    # Collect allowed ranges from violations (all we have without the spec object)
    # and gather all input values from condition
    axes_inputs: dict[str, float | None] = {}
    if condition is not None:
        raw = condition.envelope_axes()
        for axis in _ENVELOPE_AXES:
            val = raw.get(axis)
            if val is not None:
                axes_inputs[axis] = val
    # Also include axes from violations (in case condition is None)
    for v in envelope_report.violations:
        if v.axis not in axes_inputs:
            axes_inputs[v.axis] = v.input_value

    if not axes_inputs:
        return header + "\n（无可用工况轴输入）\n"

    rows = [
        "| 工况轴 | 输入值 | 允许范围 | 状态 |",
        "| --- | --- | --- | --- |",
    ]
    for axis, input_val in axes_inputs.items():
        if axis in violation_axes:
            v = violation_axes[axis]
            lo, hi = v.allowed_range
            rows.append(f"| {axis} | {input_val} | [{lo}, {hi}] | ✗ |")
        else:
            # Passed — we don't have the spec range stored here, show "—" for range
            rows.append(f"| {axis} | {input_val} | — | ✓ |")

    return header + "\n" + "\n".join(rows) + "\n"


def _safety_section_markdown(safety_report: SafetyReport | None) -> str:
    """Build the '安全性评估' markdown section.

    Returns an empty string when safety_report is None.
    """
    if safety_report is None:
        return ""

    _METHOD_LABELS = {
        "von_mises": "von Mises 屈服",
        "tsai_wu": "Tsai-Wu 复合材料失效",
    }
    method_label = _METHOD_LABELS.get(safety_report.method, "未知")

    def _status_icon(factor) -> str:
        sf = factor.value
        if sf.low >= 1.5:
            return "✓ pass"
        if sf.typical >= 1.0:
            return "⚠ marginal"
        return "✗ fail"

    rows = [
        f"## 安全性评估（方法：{method_label}）",
        "",
        "| 评估位置 | 安全系数（low / typical / high） | 主导模式 | 状态 |",
        "| --- | --- | --- | --- |",
    ]
    for factor in safety_report.factors:
        sf = factor.value
        icon = _status_icon(factor)
        rows.append(
            f"| {factor.location} | {sf.low:.2f} / {sf.typical:.2f} / {sf.high:.2f}"
            f" | {factor.dominant_mode} | {icon} |"
        )

    gov = safety_report.governing
    rows.append("")
    rows.append(
        f"**控制层**：`{gov.location}`，最低 SF.value.low = {gov.value.low:.2f}"
    )

    if safety_report.method == "tsai_wu":
        rows.append("")
        rows.append(
            "*Tsai-Wu F12 耦合系数采用 seed 中指定的 f12_star（默认 0，即 Tsai-Hill 退化）*"
        )

    return "\n".join(rows) + "\n"


def _safe_filename(value: str) -> str:
    cleaned = re.sub(r'[\\/:*?"<>|]+', "-", value).strip(" .")
    return cleaned or "材料可行性初筛报告.md"
