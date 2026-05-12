from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class MaterialCandidate:
    name: str
    category: str
    density_g_cm3: float
    tensile_strength_mpa: float
    elastic_modulus_gpa: float
    notes: str = ""

    @property
    def specific_strength(self) -> float:
        return self.tensile_strength_mpa / self.density_g_cm3 if self.density_g_cm3 else 0.0

    @property
    def specific_modulus(self) -> float:
        return self.elastic_modulus_gpa / self.density_g_cm3 if self.density_g_cm3 else 0.0


def build_single_material(
    *,
    name: str,
    category: str,
    density_g_cm3: float,
    tensile_strength_mpa: float,
    elastic_modulus_gpa: float,
) -> MaterialCandidate:
    return MaterialCandidate(
        name=name.strip() or "候选均质材料",
        category=category,
        density_g_cm3=float(density_g_cm3),
        tensile_strength_mpa=float(tensile_strength_mpa),
        elastic_modulus_gpa=float(elastic_modulus_gpa),
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
        density_g_cm3=density,
        tensile_strength_mpa=strength,
        elastic_modulus_gpa=modulus,
        notes=(
            "基于线性混合定律的 MVP 初筛估算；尚未考虑铺层方向、界面、孔隙率、"
            "成型缺陷、疲劳和环境衰减。"
        ),
    )
