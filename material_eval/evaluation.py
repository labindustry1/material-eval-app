from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from material_eval.catalog import PartTemplate
from material_eval.computation import CalculationResult, calculate_part
from material_eval.conditions import Condition
from material_eval.evidence import EvidenceCard, search_evidence
from material_eval.laminates import LaminateResult, LaminateStack, analyze_laminate
from material_eval.materials import MaterialCandidate
from material_eval.reporting import ReportDraft, build_internal_report, build_refusal_report
from material_eval.storage import DEFAULT_DB_PATH, save_run
from material_eval.uncertainty import EnvelopeReport, EnvelopeSpec


@dataclass(frozen=True)
class EvaluationRequest:
    material: MaterialCandidate
    part: PartTemplate
    dimensions: dict[str, float]         # 保留，旧调用方继续用
    evidence_query: str | None = None
    retrieval_mode: str = "bm25"
    laminate_stack: LaminateStack | None = None
    # 新增：若提供 condition，则优先于 dimensions；若提供 material_envelope 且越界则短路
    condition: Condition | None = None
    material_envelope: EnvelopeSpec | None = None


@dataclass(frozen=True)
class EnvelopeRefusal:
    """Returned by run_evaluation when the operating condition falls outside the material envelope."""
    material: MaterialCandidate
    part: PartTemplate
    condition: Condition
    envelope_report: EnvelopeReport
    refusal_markdown: str


@dataclass(frozen=True)
class EvaluationDraft:
    material: MaterialCandidate
    part: PartTemplate
    dimensions: dict[str, float]
    calculation: CalculationResult
    laminate_result: LaminateResult | None
    evidence_cards: list[EvidenceCard]
    report: ReportDraft


def run_evaluation(request: EvaluationRequest) -> EvaluationDraft | EnvelopeRefusal:
    # 1. 统一构造 condition 及向下兼容的 dims（mm 字典）
    if request.condition is not None:
        condition = request.condition
        geom = condition.geometry_mm()
        dims = geom if geom else request.dimensions
    else:
        condition = Condition.from_dimensions(request.dimensions)
        dims = request.dimensions

    # 2. envelope 校验 —— 越界则短路，不进行后续计算
    if request.material_envelope is not None:
        envelope_report = request.material_envelope.check(condition)
        if envelope_report.violations:
            refusal = build_refusal_report(
                material=request.material,
                part=request.part,
                condition=condition,
                envelope_report=envelope_report,
            )
            return EnvelopeRefusal(
                material=request.material,
                part=request.part,
                condition=condition,
                envelope_report=envelope_report,
                refusal_markdown=refusal.markdown,
            )

    # 3. 原有计算流程（保持 dims 给 calculate_part 兼容）
    calculation = calculate_part(request.part, request.material, dims)
    laminate_result = analyze_laminate(request.laminate_stack) if request.laminate_stack else None
    evidence_cards = search_evidence(
        request.evidence_query or _default_evidence_query(request),
        retrieval_mode=request.retrieval_mode,
    )
    # If an envelope was provided and passed, include its report in the draft
    # so the 工况包络校验 section appears in the report markdown.
    passed_envelope_report = None
    if request.material_envelope is not None:
        passed_envelope_report = request.material_envelope.check(condition)
    report = build_internal_report(
        material=request.material,
        part=request.part,
        dimensions=dims,
        calculation=calculation,
        laminate_result=laminate_result,
        evidence_cards=evidence_cards,
        envelope_report=passed_envelope_report,
        condition=condition,
    )
    return EvaluationDraft(
        material=request.material,
        part=request.part,
        dimensions=dims,
        calculation=calculation,
        laminate_result=laminate_result,
        evidence_cards=evidence_cards,
        report=report,
    )


def save_evaluation(
    draft: EvaluationDraft,
    *,
    report_markdown: str | None = None,
    db_path: Path | str = DEFAULT_DB_PATH,
) -> int:
    return save_run(
        material_name=draft.material.name,
        domain=draft.part.domain,
        part_name=draft.part.name,
        topology=draft.part.topology,
        payload=draft.report.report_json,
        report_markdown=report_markdown or draft.report.markdown,
        db_path=db_path,
    )


def _basic_refusal_markdown(
    material: MaterialCandidate,
    part: PartTemplate,
    envelope_report: EnvelopeReport,
) -> str:
    """Minimal stub markdown for EnvelopeRefusal.

    Task 12 will replace this with reporting.build_refusal_report once that
    function is implemented.  This version simply lists each violation so that
    callers already have a human-readable summary.
    """
    lines: list[str] = [
        f"# 材料包络越界 — 未出具评估",
        f"",
        f"**材料**：{material.name}（{material.category}）",
        f"**零件**：{part.domain} / {part.name}",
        f"",
        f"## 越界项",
    ]
    for v in envelope_report.violations:
        lo, hi = v.allowed_range
        source_note = f"（来源：{v.source}）" if v.source else ""
        lines.append(
            f"- **{v.axis}**：输入值 {v.input_value:.4g}，"
            f"允许范围 [{lo:.4g}, {hi:.4g}]{source_note}"
        )
    lines += [
        "",
        "> 由于工况超出材料声明包络，本次评估已终止，未出具评估报告。",
        "> 请调整工况参数或选用适用范围更宽的材料后重新评估。",
    ]
    return "\n".join(lines)


def _default_evidence_query(request: EvaluationRequest) -> str:
    return (
        f"{request.material.name} {request.material.category} {request.part.domain} "
        f"{request.part.name} {request.part.constraint} {request.part.search_suffix}"
    )
