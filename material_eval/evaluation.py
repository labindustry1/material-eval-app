from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from material_eval.catalog import PartTemplate
from material_eval.computation import CalculationResult, calculate_part
from material_eval.evidence import EvidenceCard, search_evidence
from material_eval.laminates import LaminateResult, LaminateStack, analyze_laminate
from material_eval.materials import MaterialCandidate
from material_eval.reporting import ReportDraft, build_internal_report
from material_eval.storage import DEFAULT_DB_PATH, save_run


@dataclass(frozen=True)
class EvaluationRequest:
    material: MaterialCandidate
    part: PartTemplate
    dimensions: dict[str, float]
    evidence_query: str | None = None
    retrieval_mode: str = "bm25"
    laminate_stack: LaminateStack | None = None


@dataclass(frozen=True)
class EvaluationDraft:
    material: MaterialCandidate
    part: PartTemplate
    dimensions: dict[str, float]
    calculation: CalculationResult
    laminate_result: LaminateResult | None
    evidence_cards: list[EvidenceCard]
    report: ReportDraft


def run_evaluation(request: EvaluationRequest) -> EvaluationDraft:
    calculation = calculate_part(request.part, request.material, request.dimensions)
    laminate_result = analyze_laminate(request.laminate_stack) if request.laminate_stack else None
    evidence_cards = search_evidence(
        request.evidence_query or _default_evidence_query(request),
        retrieval_mode=request.retrieval_mode,
    )
    report = build_internal_report(
        material=request.material,
        part=request.part,
        dimensions=request.dimensions,
        calculation=calculation,
        laminate_result=laminate_result,
        evidence_cards=evidence_cards,
    )
    return EvaluationDraft(
        material=request.material,
        part=request.part,
        dimensions=request.dimensions,
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


def _default_evidence_query(request: EvaluationRequest) -> str:
    return (
        f"{request.material.name} {request.material.category} {request.part.domain} "
        f"{request.part.name} {request.part.constraint} {request.part.search_suffix}"
    )
