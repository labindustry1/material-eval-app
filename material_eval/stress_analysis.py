"""Stress analysis for isotropic parts and composite laminates.

Task 3: isotropic_stress_field – maps part topology + loads → stress Intervals (MPa).
Task 4: PlyStress + ply_stress_field – CLT back-calculation of ply-level stresses.
"""
from __future__ import annotations

import math
from dataclasses import dataclass

from material_eval.catalog import PartTemplate
from material_eval.conditions import Condition
from material_eval.laminates import LaminateStack, analyze_laminate, _reduced_stiffness, _inverse_3x3
from material_eval.materials import MaterialCandidate
from material_eval.section_analysis import (
    analyze_hollow_circular_section,
    analyze_i_section,
    analyze_rectangular_section,
)
from material_eval.uncertainty import Interval
from material_eval.units import normalize_quantity


def _axial_force_N(condition: Condition) -> float:
    """Return axial force in Newtons (0.0 if absent)."""
    q = condition.axial_force
    if q is None:
        return 0.0
    value, _ = normalize_quantity(q.value, q.unit, "force")
    return value


def _bending_moment_Nm(condition: Condition) -> float:
    """Return bending moment in N·m (0.0 if absent)."""
    q = condition.bending_moment
    if q is None:
        return 0.0
    value, _ = normalize_quantity(q.value, q.unit, "moment")
    return value


def isotropic_stress_field(
    part: PartTemplate,
    material: MaterialCandidate,
    condition: Condition,
) -> dict[str, Interval]:
    """Return stress Intervals (MPa) at evaluation points for the given part topology.

    Supports topologies: BEAM, I_BEAM, PLATE, STRAP.
    Returns an empty dict for unrecognised topologies (e.g. CORRUGATED).
    """
    topology = part.topology.upper()
    F_N = _axial_force_N(condition)
    M_Nm = _bending_moment_Nm(condition)
    # Convert moment to N·mm for section calculations (all geometry in mm)
    M_Nmm = M_Nm * 1000.0

    geom = condition.geometry_mm()

    zero = Interval.point(0.0, "MPa")

    if topology in ("BEAM",):
        diameter = geom.get("diameter", 0.0)
        thickness = geom.get("thickness", 0.0)
        if diameter <= 0 or thickness <= 0:
            return {"root_top": zero, "root_bottom": zero}
        section = analyze_hollow_circular_section(diameter, thickness)
        area = section.area_mm2          # Interval mm²
        inertia = section.inertia_x_mm4  # Interval mm⁴
        c_mm = diameter / 2.0

        axial_stress = Interval.point(F_N, "N") / area      # N/mm² = MPa
        # Fix unit label to MPa
        axial_stress = Interval.point(axial_stress.typical, "MPa")

        bending_stress_val = M_Nmm * c_mm / inertia.typical if inertia.typical else 0.0
        bending_stress = Interval.point(bending_stress_val, "MPa")

        root_top = Interval.point(axial_stress.typical + bending_stress.typical, "MPa")
        root_bottom = Interval.point(axial_stress.typical - bending_stress.typical, "MPa")
        return {"root_top": root_top, "root_bottom": root_bottom}

    elif topology == "I_BEAM":
        height = geom.get("height", 0.0)
        width = geom.get("width", 0.0)
        thickness = geom.get("thickness", 0.0)
        if height <= 0 or width <= 0 or thickness <= 0:
            return {"root_top": zero, "root_bottom": zero}
        section = analyze_i_section(depth=height, width=width,
                                    flange_thickness=thickness, web_thickness=thickness)
        area = section.area_mm2
        inertia = section.inertia_x_mm4
        c_mm = height / 2.0

        axial_stress_val = F_N / area.typical if area.typical else 0.0
        bending_stress_val = M_Nmm * c_mm / inertia.typical if inertia.typical else 0.0
        root_top = Interval.point(axial_stress_val + bending_stress_val, "MPa")
        root_bottom = Interval.point(axial_stress_val - bending_stress_val, "MPa")
        return {"root_top": root_top, "root_bottom": root_bottom}

    elif topology == "PLATE":
        width = geom.get("width", 0.0)
        thickness = geom.get("thickness", 0.0)
        if width <= 0 or thickness <= 0:
            return {"center": zero}
        area_mm2 = width * thickness
        membrane_val = F_N / area_mm2 if area_mm2 else 0.0

        # Bending: section modulus W = w * t² / 6
        bending_section_modulus = width * thickness ** 2 / 6.0
        bending_val = M_Nmm / bending_section_modulus if bending_section_modulus else 0.0

        center = Interval.point(membrane_val + bending_val, "MPa")
        return {"center": center}

    elif topology == "STRAP":
        width = geom.get("width", 0.0)
        thickness = geom.get("thickness", 0.0)
        if width <= 0 or thickness <= 0:
            return {"section": zero}
        area_mm2 = width * thickness
        tensile_val = F_N / area_mm2 if area_mm2 else 0.0
        return {"section": Interval.point(tensile_val, "MPa")}

    # Unrecognised topology (CORRUGATED, etc.)
    return {}


# ---------------------------------------------------------------------------
# Task 4: CLT ply-stress back-calculation
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class PlyStress:
    ply_index: int
    sigma_11: Interval   # MPa, along fibre
    sigma_22: Interval   # MPa, transverse to fibre
    tau_12: Interval     # MPa, in-plane shear


def ply_stress_field(
    stack: LaminateStack,
    condition: Condition,
) -> tuple[PlyStress, ...]:
    """CLT back-calculation of ply-level principal-axis stresses.

    Handles in-plane axial loading only (spec §3.2 scope).
    N_x = F / w  [N/mm]
    """
    # 1. Geometry: width in mm
    geom = condition.geometry_mm()
    width_mm = geom.get("width", 1.0)
    if width_mm <= 0:
        width_mm = 1.0

    # 2. Axial force in N
    F_N = _axial_force_N(condition)

    # 3. Line load N_x [N/mm]
    N_x = F_N / width_mm

    # Zero load → return zero stresses immediately
    if F_N == 0.0:
        return tuple(
            PlyStress(
                ply_index=i,
                sigma_11=Interval.point(0.0, "MPa"),
                sigma_22=Interval.point(0.0, "MPa"),
                tau_12=Interval.point(0.0, "MPa"),
            )
            for i in range(len(stack.plies))
        )

    # 4. A matrix from CLT
    result = analyze_laminate(stack)
    A = [list(row) for row in result.a_matrix]  # 3×3 list[list[float]], units: GPa·mm

    # 5. Invert A matrix
    A_inv = _inverse_3x3(A)  # units: 1 / (GPa·mm)

    # 6. Mid-plane strains: ε = A⁻¹ · [N_x, 0, 0]
    # N_x is in N/mm; A is in GPa·mm = 10³ MPa·mm = 10³ N/mm
    # So A_inv has units mm/(10³ N) → ε = A_inv * N_x needs unit adjustment
    # A_inv[i][j] is in 1/(GPa·mm); N_x is in N/mm
    # 1 GPa·mm = 1000 MPa·mm = 1000 N/mm
    # So: ε = A_inv [1/(GPa·mm)] × N_x [N/mm] = N_x/(1000) × A_inv [dimensionless if GPa·mm = 1000 N/mm]
    # Actually: ε_x = A_inv[0][0] * N_x / 1000  (dividing by 1000 converts GPa to MPa)
    scale = 1.0 / 1000.0  # GPa→MPa conversion factor so A_inv * N_x gives dimensionless strain

    eps_x = (A_inv[0][0] * N_x + A_inv[0][1] * 0.0 + A_inv[0][2] * 0.0) * scale
    eps_y = (A_inv[1][0] * N_x + A_inv[1][1] * 0.0 + A_inv[1][2] * 0.0) * scale
    gamma_xy = (A_inv[2][0] * N_x + A_inv[2][1] * 0.0 + A_inv[2][2] * 0.0) * scale

    # 7. Per-ply stress transformation
    ply_stresses: list[PlyStress] = []
    for i, ply in enumerate(stack.plies):
        theta = math.radians(ply.angle_deg)
        m = math.cos(theta)
        n = math.sin(theta)

        # Strain transformation (Reddy convention)
        eps_1 = m**2 * eps_x + n**2 * eps_y + m * n * gamma_xy
        eps_2 = n**2 * eps_x + m**2 * eps_y - m * n * gamma_xy
        gamma_12 = -2 * m * n * eps_x + 2 * m * n * eps_y + (m**2 - n**2) * gamma_xy

        # Reduced stiffness Q (GPa values)
        Q = _reduced_stiffness(ply)
        # σ = Q [GPa] × ε [dimensionless] → result in GPa; convert to MPa × 1000
        sigma_1_gpa = Q[0][0] * eps_1 + Q[0][1] * eps_2
        sigma_2_gpa = Q[0][1] * eps_1 + Q[1][1] * eps_2
        tau_12_gpa = Q[2][2] * gamma_12

        # Convert GPa → MPa
        sigma_1_mpa = sigma_1_gpa * 1000.0
        sigma_2_mpa = sigma_2_gpa * 1000.0
        tau_12_mpa = tau_12_gpa * 1000.0

        ply_stresses.append(PlyStress(
            ply_index=i,
            sigma_11=Interval.point(sigma_1_mpa, "MPa"),
            sigma_22=Interval.point(sigma_2_mpa, "MPa"),
            tau_12=Interval.point(tau_12_mpa, "MPa"),
        ))

    return tuple(ply_stresses)
