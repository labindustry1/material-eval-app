from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from material_eval.materials import MaterialCandidate
from material_eval.strength import StrengthAllowables
from material_eval.uncertainty import EnvelopeSpec, Interval
from material_eval.units import normalize_material_property


DEFAULT_MATERIAL_LIBRARY_PATH = Path(__file__).resolve().parents[1] / "data" / "seed" / "material_property_library.json"


@dataclass(frozen=True)
class MaterialRecord:
    id: str
    name: str
    category: str
    form: str
    process: str
    envelope: EnvelopeSpec | None = None
    strength_allowables: StrengthAllowables | None = None


@dataclass(frozen=True)
class MaterialPropertyObservation:
    material_id: str
    property_name: str
    value: float
    unit: str
    canonical_value: float
    canonical_unit: str
    test_condition: str
    source_type: str
    source_label: str
    confidence: float
    interval: Interval = field(default=None)  # type: ignore[assignment]


@dataclass(frozen=True)
class MaterialPropertyConflict:
    material_id: str
    property_name: str
    values: tuple[float, ...]
    relative_spread: float
    observation_count: int


class MaterialPropertyLibrary:
    def __init__(self, path: Path | str = DEFAULT_MATERIAL_LIBRARY_PATH) -> None:
        self.path = Path(path)
        raw = self._load()
        self.version = raw.get("version", "unknown")
        self.notes = raw.get("notes", "")
        self.materials = {
            item["id"]: MaterialRecord(
                id=item["id"],
                name=item["name"],
                category=item["category"],
                form=item.get("form", ""),
                process=item.get("process", ""),
                envelope=self._build_envelope(item.get("envelope")),
                strength_allowables=self._build_allowables(item.get("strength_allowables")),
            )
            for item in raw.get("materials", [])
        }
        self.observations = [self._build_observation(item) for item in raw.get("observations", [])]

    def observations_for(
        self,
        *,
        material_id: str,
        property_name: str | None = None,
    ) -> list[MaterialPropertyObservation]:
        return [
            item
            for item in self.observations
            if item.material_id == material_id and (property_name is None or item.property_name == property_name)
        ]

    def best_observation(self, material_id: str, property_name: str) -> MaterialPropertyObservation:
        candidates = self.observations_for(material_id=material_id, property_name=property_name)
        if not candidates:
            raise KeyError(f"Property observation not found: {material_id} / {property_name}")
        return sorted(candidates, key=lambda item: (item.confidence, item.source_label), reverse=True)[0]

    def build_candidate(self, material_id: str) -> MaterialCandidate:
        material = self.materials.get(material_id)
        if material is None:
            raise KeyError(f"Material not found: {material_id}")

        density = self.best_observation(material_id, "density_g_cm3")
        strength = self.best_observation(material_id, "tensile_strength_mpa")
        modulus = self.best_observation(material_id, "elastic_modulus_gpa")
        return MaterialCandidate(
            name=material.name,
            category=material.category,
            density_g_cm3=density.interval,
            tensile_strength_mpa=strength.interval,
            elastic_modulus_gpa=modulus.interval,
            notes=(
                f"来自材料属性库 {self.version}；属性为典型工程参考值，需按供应商/实验/标准复核。"
                f" 来源：{density.source_label}；{strength.source_label}；{modulus.source_label}。"
            ),
        )

    def detect_conflicts(
        self,
        *,
        material_id: str | None = None,
        property_name: str | None = None,
        relative_threshold: float = 0.15,
    ) -> list[MaterialPropertyConflict]:
        groups: dict[tuple[str, str], list[float]] = {}
        for observation in self.observations:
            if material_id is not None and observation.material_id != material_id:
                continue
            if property_name is not None and observation.property_name != property_name:
                continue
            groups.setdefault((observation.material_id, observation.property_name), []).append(
                observation.canonical_value
            )

        conflicts: list[MaterialPropertyConflict] = []
        for (group_material_id, group_property_name), values in groups.items():
            if len(values) < 2:
                continue
            mean_value = sum(values) / len(values)
            if mean_value == 0:
                continue
            relative_spread = (max(values) - min(values)) / abs(mean_value)
            if relative_spread >= relative_threshold:
                conflicts.append(
                    MaterialPropertyConflict(
                        material_id=group_material_id,
                        property_name=group_property_name,
                        values=tuple(sorted(values)),
                        relative_spread=relative_spread,
                        observation_count=len(values),
                    )
                )
        return sorted(conflicts, key=lambda item: (item.material_id, item.property_name))

    def property_interval(self, material_id: str, property_name: str) -> Interval | None:
        """Aggregate all observations of (material_id, property_name) into a single Interval.

        Single observation -> its own Interval.
        Multi observation -> Interval(low=min(all.low), typical=highest-confidence.typical, high=max(all.high))
        Returns None if no observations found.
        """
        candidates = self.observations_for(material_id=material_id, property_name=property_name)
        if not candidates:
            return None
        if len(candidates) == 1:
            return candidates[0].interval
        best = sorted(candidates, key=lambda o: (o.confidence, o.source_label), reverse=True)[0]
        agg_low = min(o.interval.low for o in candidates)
        agg_high = max(o.interval.high for o in candidates)
        return Interval(low=agg_low, typical=best.interval.typical, high=agg_high, unit=best.interval.unit)

    def envelope_for(self, material_id: str) -> EnvelopeSpec | None:
        """Return envelope of material if declared, else None."""
        record = self.materials.get(material_id)
        if record is None:
            return None
        return record.envelope

    def allowables_for(self, material_id: str) -> StrengthAllowables | None:
        """Return strength allowables of material if declared, else None."""
        return self.materials[material_id].strength_allowables if material_id in self.materials else None

    def _load(self) -> dict[str, Any]:
        if not self.path.exists():
            raise FileNotFoundError(f"Material property library seed not found: {self.path}")
        return json.loads(self.path.read_text(encoding="utf-8"))

    @staticmethod
    def _build_envelope(raw_envelope: dict[str, Any] | None) -> EnvelopeSpec | None:
        if raw_envelope is None:
            return None
        _ENVELOPE_AXES = (
            "temperature_C",
            "humidity_pct",
            "stress_MPa",
            "strain_rate_1_per_s",
            "fatigue_cycles",
            "thickness_mm",
        )
        kwargs: dict[str, Any] = {}
        for axis in _ENVELOPE_AXES:
            raw_val = raw_envelope.get(axis)
            if raw_val is not None:
                lo, hi = raw_val
                kwargs[axis] = (float(lo), float(hi))
        source = raw_envelope.get("source")
        if source is not None:
            kwargs["source"] = source
        return EnvelopeSpec(**kwargs)

    @staticmethod
    def _build_allowables(payload: dict[str, Any] | None) -> StrengthAllowables | None:
        if payload is None:
            return None

        _ALLOWABLE_FIELDS = ("yield_mpa", "Xt_mpa", "Xc_mpa", "Yt_mpa", "Yc_mpa", "S_mpa")

        def _parse_interval(raw: Any) -> Interval | None:
            if raw is None:
                return None
            if isinstance(raw, dict):
                return Interval(
                    low=float(raw["low"]),
                    typical=float(raw["typical"]),
                    high=float(raw["high"]),
                    unit="MPa",
                )
            # Legacy single-point number: use confidence=0.5 → medium spread ±15%
            return Interval.from_confidence(float(raw), "MPa", confidence=0.5)

        kwargs: dict[str, Any] = {}
        for field_name in _ALLOWABLE_FIELDS:
            raw_val = payload.get(field_name)
            kwargs[field_name] = _parse_interval(raw_val)

        kwargs["f12_star"] = float(payload.get("f12_star", 0.0))
        kwargs["source"] = payload.get("source")

        return StrengthAllowables(**kwargs)

    def _build_observation(self, item: dict[str, Any]) -> MaterialPropertyObservation:
        raw_value = item["value"]
        confidence = max(0.0, min(1.0, float(item.get("confidence", 0.0))))

        if isinstance(raw_value, dict):
            # Three-point format: {"low": ..., "typical": ..., "high": ...}
            raw_low = raw_value["low"]
            raw_typical = raw_value["typical"]
            raw_high = raw_value["high"]
            norm_low = normalize_material_property(item["property_name"], raw_low, item["unit"])
            norm_typical = normalize_material_property(item["property_name"], raw_typical, item["unit"])
            norm_high = normalize_material_property(item["property_name"], raw_high, item["unit"])
            canonical_value = norm_typical.value
            canonical_unit = norm_typical.unit
            interval = Interval(
                low=norm_low.value,
                typical=norm_typical.value,
                high=norm_high.value,
                unit=canonical_unit,
            )
            scalar_value = float(raw_typical)
        else:
            # Single-point format
            normalized = normalize_material_property(item["property_name"], raw_value, item["unit"])
            canonical_value = normalized.value
            canonical_unit = normalized.unit
            interval = Interval.from_confidence(canonical_value, canonical_unit, confidence)
            scalar_value = float(raw_value)

        return MaterialPropertyObservation(
            material_id=item["material_id"],
            property_name=item["property_name"],
            value=scalar_value,
            unit=item["unit"],
            canonical_value=canonical_value,
            canonical_unit=canonical_unit,
            test_condition=item.get("test_condition", ""),
            source_type=item.get("source_type", ""),
            source_label=item.get("source_label", ""),
            confidence=confidence,
            interval=interval,
        )
