from __future__ import annotations

from pydantic import BaseModel, Field

from material_eval.catalog import PartTemplate
from material_eval.computation import CalculationResult
from material_eval.evidence import EvidenceCard
from material_eval.materials import MaterialCandidate


class ScoreDimension(BaseModel):
    dimension_id: str
    name: str
    score: float = Field(ge=0.0, le=100.0)
    weight: float = Field(gt=0.0, le=1.0)
    rationale: str


class Scorecard(BaseModel):
    version: str = "mvp_scorecard_v1"
    total_score: float = Field(ge=0.0, le=100.0)
    dimensions: list[ScoreDimension] = Field(min_length=1)
    interpretation: str

    def dimension(self, dimension_id: str) -> ScoreDimension:
        for dimension in self.dimensions:
            if dimension.dimension_id == dimension_id:
                return dimension
        raise KeyError(f"Score dimension not found: {dimension_id}")


def build_scorecard(
    *,
    material: MaterialCandidate,
    part: PartTemplate,
    calculation: CalculationResult,
    evidence_cards: list[EvidenceCard],
    risks: list[str],
) -> Scorecard:
    dimensions = [
        _dimension(
            "data_confidence",
            "数据可信度",
            _data_confidence_score(evidence_cards, material),
            0.20,
            f"检索到 {len(evidence_cards)} 条证据卡；材料备注为：{material.notes or '无'}。",
        ),
        _dimension(
            "intrinsic_performance",
            "本征性能潜力",
            _intrinsic_performance_score(material),
            0.20,
            f"比强度 {material.specific_strength_typical:.4g}，比模量 {material.specific_modulus_typical:.4g}。",
        ),
        _dimension(
            "structural_fit",
            "结构适配度",
            _structural_fit_score(part, calculation),
            0.20,
            f"拓扑 {part.topology}，计算指标 {len(calculation.metrics)} 项，告警 {len(calculation.warnings)} 项。",
        ),
        _dimension(
            "operating_risk",
            "工况风险可控性",
            _operating_risk_score(part, calculation, risks),
            0.15,
            f"风险项 {len(risks)} 项；告警 {len(calculation.warnings)} 项。",
        ),
        _dimension(
            "process_maturity",
            "工艺成熟度",
            _process_maturity_score(material),
            0.15,
            f"材料类别：{material.category}。",
        ),
        _dimension(
            "compliance_risk",
            "合规/准入风险",
            _compliance_risk_score(part),
            0.10,
            f"应用领域：{part.domain}；约束摘要：{part.constraint[:60]}。",
        ),
    ]
    total = sum(item.score * item.weight for item in dimensions)
    return Scorecard(
        total_score=round(total, 2),
        dimensions=dimensions,
        interpretation=_interpret_total(total),
    )


def _dimension(dimension_id: str, name: str, score: float, weight: float, rationale: str) -> ScoreDimension:
    return ScoreDimension(
        dimension_id=dimension_id,
        name=name,
        score=round(_clamp(score), 2),
        weight=weight,
        rationale=rationale,
    )


def _data_confidence_score(evidence_cards: list[EvidenceCard], material: MaterialCandidate) -> float:
    score = 42 + min(len(evidence_cards), 5) * 8
    if "用户输入" in material.notes:
        score -= 8
    if "需" in material.notes and "复核" in material.notes:
        score -= 6
    if evidence_cards:
        score += min(max(card.score for card in evidence_cards), 3.0) * 3
    return score


def _intrinsic_performance_score(material: MaterialCandidate) -> float:
    strength_component = min(material.specific_strength_typical / 3500, 1.0) * 55
    modulus_component = min(material.specific_modulus_typical / 120, 1.0) * 35
    density_bonus = 10 if material.density_g_cm3.typical <= 1.6 else 0
    return strength_component + modulus_component + density_bonus


def _structural_fit_score(part: PartTemplate, calculation: CalculationResult) -> float:
    supported_topologies = {"BEAM", "I_BEAM", "PLATE", "CORRUGATED", "STRAP"}
    score = 55
    if part.topology in supported_topologies and calculation.metrics:
        score += 22
    if "sectionproperties" in " ".join(calculation.assumptions):
        score += 8
    score -= len(calculation.warnings) * 7
    if part.topology in {"CORRUGATED", "STRAP"}:
        score -= 8
    return score


def _operating_risk_score(part: PartTemplate, calculation: CalculationResult, risks: list[str]) -> float:
    score = 86
    score -= len(calculation.warnings) * 18
    score -= max(0, len(risks) - 1) * 7
    if part.topology in {"STRAP", "CORRUGATED"}:
        score -= 18
    if any(token in part.constraint for token in ["疲劳", "冲击", "舒适", "准入"]):
        score -= 8
    return score


def _process_maturity_score(material: MaterialCandidate) -> float:
    category = material.category
    if any(token in category for token in ["金属", "铝", "钛", "不锈钢"]):
        return 82
    if any(token in category for token in ["碳纤维", "玻纤", "工程塑料", "PEEK", "尼龙"]):
        return 66
    if any(token in category for token in ["生物基", "蛋白"]):
        return 42
    return 55


def _compliance_risk_score(part: PartTemplate) -> float:
    score = 72
    if any(token in part.domain for token in ["军工", "医疗", "航空"]):
        score -= 18
    if any(token in part.constraint for token in ["人体", "舒适", "准入", "防弹", "认证"]):
        score -= 10
    return score


def _interpret_total(total: float) -> str:
    if total >= 75:
        return "适合进入下一轮内部研发对比，但仍需实验/仿真验证关键工况。"
    if total >= 55:
        return "具备讨论价值，但存在明显数据、工况或工艺缺口。"
    return "当前只能作为概念探索，不建议直接进入工程决策。"


def _clamp(value: float, lower: float = 0.0, upper: float = 100.0) -> float:
    return max(lower, min(upper, value))
