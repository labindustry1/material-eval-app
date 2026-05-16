from __future__ import annotations

from dataclasses import dataclass

from material_eval.uncertainty import Interval


def _as_interval(value: Interval | float, unit: str) -> Interval:
    """Return value as-is if already an Interval; otherwise wrap as a point Interval."""
    if isinstance(value, Interval):
        return value
    return Interval.point(float(value), unit)


@dataclass(frozen=True)
class MaterialCandidate:
    name: str
    category: str
    density_g_cm3: Interval
    tensile_strength_mpa: Interval
    elastic_modulus_gpa: Interval
    notes: str = ""

    @property
    def specific_strength_typical(self) -> float:
        d = self.density_g_cm3.typical
        return self.tensile_strength_mpa.typical / d if d else 0.0

    @property
    def specific_modulus_typical(self) -> float:
        d = self.density_g_cm3.typical
        return self.elastic_modulus_gpa.typical / d if d else 0.0


def build_single_material(
    *,
    name: str,
    category: str,
    density_g_cm3: Interval | float,
    tensile_strength_mpa: Interval | float,
    elastic_modulus_gpa: Interval | float,
) -> MaterialCandidate:
    return MaterialCandidate(
        name=name.strip() or "候选均质材料",
        category=category,
        density_g_cm3=_as_interval(density_g_cm3, "g/cm^3"),
        tensile_strength_mpa=_as_interval(tensile_strength_mpa, "MPa"),
        elastic_modulus_gpa=_as_interval(elastic_modulus_gpa, "GPa"),
        notes="用户输入的单一均质材料参数。",
    )


def build_composite_material(
    *,
    matrix_name: str,
    fiber_name: str,
    fiber_volume_fraction: float,
    matrix_density: float,
    matrix_strength: float,
    matrix_modulus: float,
    fiber_density: float,
    fiber_strength: float,
    fiber_modulus: float,
) -> MaterialCandidate:
    """Rule-of-mixtures estimate for MVP screening.

    This is intentionally marked as a preliminary estimate. It does not model
    ply orientation, interface failure, voids, fatigue, or processing defects.
    """

    vf = max(0.0, min(1.0, float(fiber_volume_fraction)))
    vm = 1.0 - vf
    density = matrix_density * vm + fiber_density * vf
    strength = matrix_strength * vm + fiber_strength * vf
    modulus = matrix_modulus * vm + fiber_modulus * vf
    return MaterialCandidate(
        name=f"{fiber_name}增强{matrix_name}",
        category="复合/杂化材料体系",
        density_g_cm3=Interval.point(density, "g/cm^3"),
        tensile_strength_mpa=Interval.point(strength, "MPa"),
        elastic_modulus_gpa=Interval.point(modulus, "GPa"),
        notes=(
            "基于线性混合定律的 MVP 初筛估算；尚未考虑铺层方向、界面、孔隙率、"
            "成型缺陷、疲劳和环境衰减。"
        ),
    )
