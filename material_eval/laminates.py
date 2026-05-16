from __future__ import annotations

# Phase 1 note: Lamina inputs are user-supplied floats (no uncertainty), so
# LaminateResult fields are zero-width Intervals.  Phase 2 failure-criteria
# will introduce non-zero widths when ply-property Intervals are available.

import math
from dataclasses import dataclass, field

from material_eval.uncertainty import Interval


@dataclass(frozen=True)
class Lamina:
    e1_gpa: float
    e2_gpa: float
    g12_gpa: float
    nu12: float
    thickness_mm: float
    angle_deg: float

    @property
    def nu21(self) -> float:
        return self.nu12 * self.e2_gpa / self.e1_gpa if self.e1_gpa else 0.0


@dataclass(frozen=True)
class LaminateStack:
    plies: tuple[Lamina, ...]

    @classmethod
    def symmetric_cross_ply(
        cls,
        *,
        e1_gpa: float,
        e2_gpa: float,
        g12_gpa: float,
        nu12: float,
        ply_thickness_mm: float,
    ) -> "LaminateStack":
        return cls(
            plies=(
                Lamina(e1_gpa, e2_gpa, g12_gpa, nu12, ply_thickness_mm, 0),
                Lamina(e1_gpa, e2_gpa, g12_gpa, nu12, ply_thickness_mm, 90),
                Lamina(e1_gpa, e2_gpa, g12_gpa, nu12, ply_thickness_mm, 90),
                Lamina(e1_gpa, e2_gpa, g12_gpa, nu12, ply_thickness_mm, 0),
            )
        )


@dataclass(frozen=True)
class LaminateResult:
    total_thickness_mm: Interval     # zero-width in Phase 1; Phase 2 will use ply-property Intervals
    a_matrix: tuple[tuple[float, float, float], tuple[float, float, float], tuple[float, float, float]]
    ex_gpa: Interval
    ey_gpa: Interval
    gxy_gpa: Interval
    nuxy: Interval                   # dimensionless → unit=""
    method: str = "classical-laminate-theory"
    warnings: tuple[str, ...] = field(default_factory=tuple)


def analyze_laminate(stack: LaminateStack) -> LaminateResult:
    if not stack.plies:
        raise ValueError("Laminate stack requires at least one ply")

    warnings: list[str] = []
    total_thickness = sum(ply.thickness_mm for ply in stack.plies)
    if total_thickness <= 0:
        raise ValueError("Laminate thickness must be positive")

    a_matrix = [[0.0, 0.0, 0.0] for _ in range(3)]
    for ply in stack.plies:
        if min(ply.e1_gpa, ply.e2_gpa, ply.g12_gpa, ply.thickness_mm) <= 0:
            raise ValueError("Ply stiffness and thickness must be positive")
        qbar = _transformed_reduced_stiffness(ply)
        for row in range(3):
            for col in range(3):
                a_matrix[row][col] += qbar[row][col] * ply.thickness_mm

    a_inverse = _inverse_3x3(a_matrix)
    ex = 1.0 / (a_inverse[0][0] * total_thickness) if a_inverse[0][0] else 0.0
    ey = 1.0 / (a_inverse[1][1] * total_thickness) if a_inverse[1][1] else 0.0
    gxy = 1.0 / (a_inverse[2][2] * total_thickness) if a_inverse[2][2] else 0.0
    nuxy = -a_inverse[0][1] / a_inverse[0][0] if a_inverse[0][0] else 0.0

    if not _is_balanced(stack):
        warnings.append("铺层不是平衡/对称配置，MVP 仅输出 A 矩阵初筛，不判断弯扭耦合。")

    return LaminateResult(
        total_thickness_mm=Interval.point(total_thickness, "mm"),
        a_matrix=tuple(tuple(float(item) for item in row) for row in a_matrix),  # type: ignore[arg-type]
        ex_gpa=Interval.point(ex, "GPa"),
        ey_gpa=Interval.point(ey, "GPa"),
        gxy_gpa=Interval.point(gxy, "GPa"),
        nuxy=Interval.point(nuxy, ""),
        warnings=tuple(warnings),
    )


def _reduced_stiffness(ply: Lamina) -> tuple[tuple[float, float, float], tuple[float, float, float], tuple[float, float, float]]:
    denominator = 1 - ply.nu12 * ply.nu21
    q11 = ply.e1_gpa / denominator
    q22 = ply.e2_gpa / denominator
    q12 = ply.nu12 * ply.e2_gpa / denominator
    q66 = ply.g12_gpa
    return ((q11, q12, 0.0), (q12, q22, 0.0), (0.0, 0.0, q66))


def _transformed_reduced_stiffness(
    ply: Lamina,
) -> tuple[tuple[float, float, float], tuple[float, float, float], tuple[float, float, float]]:
    q = _reduced_stiffness(ply)
    q11, q12, q22, q66 = q[0][0], q[0][1], q[1][1], q[2][2]
    theta = math.radians(ply.angle_deg)
    m = math.cos(theta)
    n = math.sin(theta)
    m2, n2 = m * m, n * n
    m4, n4 = m2 * m2, n2 * n2

    qbar11 = q11 * m4 + 2 * (q12 + 2 * q66) * m2 * n2 + q22 * n4
    qbar22 = q11 * n4 + 2 * (q12 + 2 * q66) * m2 * n2 + q22 * m4
    qbar12 = (q11 + q22 - 4 * q66) * m2 * n2 + q12 * (m4 + n4)
    qbar16 = (q11 - q12 - 2 * q66) * m * m2 * n - (q22 - q12 - 2 * q66) * m * n * n2
    qbar26 = (q11 - q12 - 2 * q66) * m * n * n2 - (q22 - q12 - 2 * q66) * m * m2 * n
    qbar66 = (q11 + q22 - 2 * q12 - 2 * q66) * m2 * n2 + q66 * (m4 + n4)
    return ((qbar11, qbar12, qbar16), (qbar12, qbar22, qbar26), (qbar16, qbar26, qbar66))


def _inverse_3x3(matrix: list[list[float]]) -> list[list[float]]:
    a, b, c = matrix[0]
    d, e, f = matrix[1]
    g, h, i = matrix[2]
    det = a * (e * i - f * h) - b * (d * i - f * g) + c * (d * h - e * g)
    if abs(det) < 1e-12:
        raise ValueError("Laminate A matrix is singular")
    return [
        [(e * i - f * h) / det, (c * h - b * i) / det, (b * f - c * e) / det],
        [(f * g - d * i) / det, (a * i - c * g) / det, (c * d - a * f) / det],
        [(d * h - e * g) / det, (b * g - a * h) / det, (a * e - b * d) / det],
    ]


def _is_balanced(stack: LaminateStack) -> bool:
    angles = [round(((ply.angle_deg % 180) + 180) % 180, 6) for ply in stack.plies]
    return angles == list(reversed(angles))
