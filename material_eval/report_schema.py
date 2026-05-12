from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field

from material_eval.catalog import PartTemplate
from material_eval.computation import CalculationResult
from material_eval.evidence import EvidenceCard
from material_eval.laminates import LaminateResult
from material_eval.materials import MaterialCandidate


ClaimSourceType = Literal["calculation_metric", "evidence_card", "laminate_result", "manual_judgement"]
ClaimSupportLevel = Literal["direct", "context", "needs_review"]
ClaimType = Literal["verdict", "performance", "risk", "evidence", "assumption"]


class ClaimBinding(BaseModel):
    source_type: ClaimSourceType
    reference_id: str
    reference_label: str
    support_level: ClaimSupportLevel
    value: float | str | None = None
    unit: str | None = None
    note: str = ""


class ReportClaim(BaseModel):
    claim_id: str
    section: str
    claim_type: ClaimType
    text: str
    confidence: float = Field(ge=0.0, le=1.0)
    bindings: list[ClaimBinding] = Field(min_length=1)


class StructuredReport(BaseModel):
    title: str
    language: str = "zh-CN"
    audience: str = "内部研发"
    material_name: str
    part_name: str
    created_at: str
    claims: list[ReportClaim] = Field(min_length=1)
    open_questions: list[str] = Field(default_factory=list)

    def source_type_counts(self) -> dict[str, int]:
        counts: dict[str, int] = {}
        for claim in self.claims:
            for binding in claim.bindings:
                counts[binding.source_type] = counts.get(binding.source_type, 0) + 1
        return counts


def build_structured_report(
    *,
    title: str,
    created_at: str,
    material: MaterialCandidate,
    part: PartTemplate,
    calculation: CalculationResult,
    laminate_result: LaminateResult | None,
    evidence_cards: list[EvidenceCard],
    verdict: str,
    risks: list[str],
) -> StructuredReport:
    claims: list[ReportClaim] = []

    claims.append(
        ReportClaim(
            claim_id=_claim_id(len(claims) + 1),
            section="研发结论",
            claim_type="verdict",
            text=verdict,
            confidence=_verdict_confidence(calculation=calculation, evidence_cards=evidence_cards, risks=risks),
            bindings=[
                ClaimBinding(
                    source_type="manual_judgement",
                    reference_id="verdict_rule_v1",
                    reference_label="MVP 结论规则",
                    support_level="needs_review",
                    note="由计算告警、证据可用性和拓扑风险规则生成，必须经研发复核。",
                )
            ],
        )
    )

    for idx, metric in enumerate(calculation.metrics, start=1):
        claims.append(
            ReportClaim(
                claim_id=_claim_id(len(claims) + 1),
                section="工程初筛结果",
                claim_type="performance",
                text=f"{metric.name} 为 {metric.value.typical:.4g} {metric.unit}，用于 {part.name} 的 MVP 初筛。",
                confidence=0.72 if not calculation.warnings else 0.62,
                bindings=[
                    ClaimBinding(
                        source_type="calculation_metric",
                        reference_id=f"{calculation.version}:{calculation.topology}:metric:{idx}",
                        reference_label=metric.name,
                        support_level="direct",
                        value=metric.value.typical,
                        unit=metric.unit,
                        note=metric.description,
                    )
                ],
            )
        )

    if laminate_result is not None:
        claims.append(
            ReportClaim(
                claim_id=_claim_id(len(claims) + 1),
                section="复合铺层初筛",
                claim_type="performance",
                text=(
                    f"CLT 等效 Ex={laminate_result.ex_gpa.typical:.4g} GPa、"
                    f"Ey={laminate_result.ey_gpa.typical:.4g} GPa，可作为铺层刚度初筛输入。"
                ),
                confidence=0.58 if laminate_result.warnings else 0.66,
                bindings=[
                    ClaimBinding(
                        source_type="laminate_result",
                        reference_id=laminate_result.method,
                        reference_label="Classical Laminate Theory A matrix",
                        support_level="direct",
                        value=laminate_result.ex_gpa.typical,
                        unit="GPa",
                        note="当前未包含失效准则和环境衰减。",
                    )
                ],
            )
        )

    for idx, card in enumerate(evidence_cards[:3], start=1):
        claims.append(
            ReportClaim(
                claim_id=_claim_id(len(claims) + 1),
                section="证据来源",
                claim_type="evidence",
                text=f"内部资料 `{card.source}` 可为本次材料/应用判断提供上下文证据。",
                confidence=min(0.85, max(0.35, 0.45 + min(card.score, 3.0) / 10.0)),
                bindings=[
                    ClaimBinding(
                        source_type="evidence_card",
                        reference_id=str(card.chunk_id) if card.chunk_id is not None else f"evidence:{idx}",
                        reference_label=card.source,
                        support_level="context",
                        value=card.score,
                        unit="retrieval_score",
                        note=f"{card.source_type} / {card.retrieval_method}",
                    )
                ],
            )
        )

    for idx, risk in enumerate(risks, start=1):
        claims.append(
            ReportClaim(
                claim_id=_claim_id(len(claims) + 1),
                section="风险与缺口",
                claim_type="risk",
                text=risk,
                confidence=0.68,
                bindings=[
                    ClaimBinding(
                        source_type="manual_judgement",
                        reference_id=f"risk_rule_v1:{idx}",
                        reference_label="MVP 风险规则",
                        support_level="needs_review",
                        note="风险项需要研发、测试或仿真负责人确认。",
                    )
                ],
            )
        )

    open_questions = [
        "材料属性是否已有供应商批次数据、内部测试数据或标准测试条件？",
        "目标零部件的载荷谱、疲劳寿命、冲击/跌落、温湿度边界是否已定义？",
    ]
    if calculation.warnings:
        open_questions.append("计算告警是否需要修正几何、拓扑或进入更高保真仿真？")

    return StructuredReport(
        title=title,
        material_name=material.name,
        part_name=part.name,
        created_at=created_at,
        claims=claims,
        open_questions=open_questions,
    )


def _claim_id(index: int) -> str:
    return f"CLM-{index:03d}"


def _verdict_confidence(
    *,
    calculation: CalculationResult,
    evidence_cards: list[EvidenceCard],
    risks: list[str],
) -> float:
    confidence = 0.72
    if not evidence_cards:
        confidence -= 0.18
    if calculation.warnings:
        confidence -= 0.08
    if len(risks) > 2:
        confidence -= 0.06
    return max(0.25, min(0.85, confidence))
