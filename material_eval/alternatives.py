from __future__ import annotations

from dataclasses import dataclass

from material_eval.catalog import PartTemplate
from material_eval.conditions import Condition
from material_eval.material_property_library import MaterialPropertyLibrary, MaterialRecord
from material_eval.uncertainty import EnvelopeReport


@dataclass(frozen=True)
class AlternativeSuggestion:
    material_id: str
    material_name: str
    category: str
    envelope_source: str | None


_AXIS_LABEL_CN = {
    "temperature_C": "温度",
    "humidity_pct": "湿度",
    "stress_MPa": "应力",
    "strain_rate_1_per_s": "应变率",
    "fatigue_cycles": "疲劳循环数",
    "thickness_mm": "厚度",
}


def suggest_alternatives_for(
    condition: Condition,
    part: PartTemplate,
    library: MaterialPropertyLibrary,
    *,
    limit: int = 5,
) -> tuple[AlternativeSuggestion, ...]:
    """Reverse-lookup materials whose envelope fully contains the current condition."""
    suggestions: list[AlternativeSuggestion] = []
    for material_id, record in library.materials.items():
        envelope = library.envelope_for(material_id)
        if envelope is None or not envelope.has_any_axis():
            continue
        report = envelope.check(condition)
        if report.violations:
            continue
        suggestions.append(AlternativeSuggestion(
            material_id=material_id,
            material_name=record.name,
            category=record.category,
            envelope_source=envelope.source,
        ))
    # 排序：非 engineering-default 优先
    suggestions.sort(key=lambda s: (
        s.envelope_source is None or "engineering default" in (s.envelope_source or "").lower(),
        s.material_id,
    ))
    return tuple(suggestions[:limit])


def missing_data_hints(
    material_entry,  # MaterialRecord | None (duck typed to avoid hard import circular)
    envelope_report: EnvelopeReport,
    condition: Condition,
) -> tuple[str, ...]:
    """Generate Chinese hints listing what data is needed to evaluate the rejected material."""
    hints: list[str] = []
    for v in envelope_report.violations:
        axis_label = _AXIS_LABEL_CN.get(v.axis, v.axis)
        material_name = material_entry.name if material_entry else "该材料"
        hints.append(
            f"补充 {material_name} 在 {axis_label}={v.input_value} 下的实验/标准数据"
            f"（当前适用域 [{v.allowed_range[0]}, {v.allowed_range[1]}]）"
        )
    if material_entry is not None and getattr(material_entry, "strength_allowables", None) is None:
        if condition is not None and (
            getattr(condition, "axial_force", None) is not None
            or getattr(condition, "bending_moment", None) is not None
        ):
            hints.append(
                f"补充 {material_entry.name} 的强度许用值"
                f"（yield_mpa 或 Xt/Xc/Yt/Yc/S）以启用失效分析"
            )
    # 去重保序
    seen = set()
    deduped = []
    for h in hints:
        if h not in seen:
            deduped.append(h)
            seen.add(h)
    return tuple(deduped)
