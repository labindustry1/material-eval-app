"""Failure criteria: von Mises (isotropic) and Tsai-Wu (composite).

Task 5: von_mises_safety_factor – isotropic yielding / ultimate check.
Task 6: tsai_wu_safety_factor + laminate_safety_factor – composite ply failure.
"""
from __future__ import annotations

import math
from typing import TYPE_CHECKING

from material_eval.materials import MaterialCandidate
from material_eval.strength import SafetyFactor, StrengthAllowables
from material_eval.uncertainty import Interval

if TYPE_CHECKING:
    from material_eval.laminates import LaminateStack
    from material_eval.conditions import Condition
    from material_eval.stress_analysis import PlyStress


# ---------------------------------------------------------------------------
# Task 5: von Mises safety factor (isotropic)
# ---------------------------------------------------------------------------

def von_mises_safety_factor(
    stresses: dict[str, Interval],
    material: MaterialCandidate,
    allowables: StrengthAllowables,
    *,
    location_label: str | None = None,
) -> SafetyFactor:
    """Compute a von Mises safety factor from a stress field dict.

    The governing location is the one whose ``typical`` absolute value is
    largest.  The allowable is taken from ``allowables.yield_mpa`` when
    present; otherwise ``material.tensile_strength_mpa`` is used.
    """
    if not stresses:
        raise ValueError("stresses dict must not be empty")

    # 1. Governing key (largest |typical|)
    governing_key = max(stresses, key=lambda k: abs(stresses[k].typical))
    sigma = stresses[governing_key]
    location = location_label or governing_key

    # 2. Zero-stress shortcut
    if abs(sigma.typical) < 1e-9:
        return SafetyFactor(
            value=Interval.point(999.0, ""),
            pass_at_typical=True,
            dominant_mode="no_load",
            criterion="von_mises",
            location=location,
            notes=("零应力工况，返回 SF=999 占位",),
        )

    # 3. Allowable and mode
    if allowables.yield_mpa is not None:
        allowable: Interval = allowables.yield_mpa
        dominant_mode = "yield"
    else:
        allowable = material.tensile_strength_mpa
        dominant_mode = "ultimate"

    # 4. Build magnitude interval (avoid zero-crossing → division by zero)
    abs_lo = abs(sigma.low)
    abs_hi = abs(sigma.high)
    mag_typical = abs(sigma.typical)

    # If interval spans zero the true magnitude low is 0 → treat as zero-stress
    if sigma.low <= 0.0 <= sigma.high and sigma.low < 0.0 and sigma.high > 0.0:
        return SafetyFactor(
            value=Interval.point(999.0, ""),
            pass_at_typical=True,
            dominant_mode="no_load",
            criterion="von_mises",
            location=location,
            notes=("应力区间穿零，按零应力工况处理，返回 SF=999 占位",),
        )

    mag_low = min(abs_lo, abs_hi, mag_typical)
    mag_high = max(abs_lo, abs_hi, mag_typical)

    # Guard against numerically-zero mag_low (should not happen post zero-check,
    # but defensive programming)
    if mag_low < 1e-12:
        mag_low = mag_typical

    magnitude = Interval(mag_low, mag_typical, mag_high, "MPa")

    # 5. Safety factor = allowable / magnitude  (units cancel → "")
    # Ensure allowable has unit "MPa" for division compatibility
    if allowable.unit != "MPa":
        allowable = Interval(allowable.low, allowable.typical, allowable.high, "MPa")

    sf = allowable / magnitude

    return SafetyFactor(
        value=sf,
        pass_at_typical=sf.typical >= 1.0,
        dominant_mode=dominant_mode,
        criterion="von_mises",
        location=location,
    )


# ---------------------------------------------------------------------------
# Task 6: Tsai-Wu safety factor (composite ply)
# ---------------------------------------------------------------------------

def _evaluate_tsai_wu(
    s1: float,
    s2: float,
    t12: float,
    Xt: float,
    Xc: float,
    Yt: float,
    Yc: float,
    S: float,
    f12_star: float,
) -> float:
    """Scalar Tsai-Wu SF evaluation.  Returns 999.0 for trivial / degenerate cases."""
    # Strength index coefficients
    F1 = 1.0 / Xt - 1.0 / Xc
    F2 = 1.0 / Yt - 1.0 / Yc
    F11 = 1.0 / (Xt * Xc)
    F22 = 1.0 / (Yt * Yc)
    F66 = 1.0 / (S * S)
    denom_f12 = 2.0 * math.sqrt(Xt * Xc * Yt * Yc)
    F12 = f12_star / denom_f12 if denom_f12 > 0.0 else 0.0

    # Quadratic coefficients in SF: a*SF² + b*SF - 1 = 0
    a = F11 * s1 ** 2 + F22 * s2 ** 2 + F66 * t12 ** 2 + 2.0 * F12 * s1 * s2
    b = F1 * s1 + F2 * s2

    if abs(a) < 1e-12:
        # Linear case: b*SF = 1
        if abs(b) < 1e-12:
            return 999.0
        sf = 1.0 / b
        return abs(sf) if sf > 0.0 else 999.0

    disc = b ** 2 + 4.0 * a
    if disc < 0.0:
        return 999.0

    sf = (-b + math.sqrt(disc)) / (2.0 * a)
    return abs(sf) if sf > 0.0 else 999.0


def tsai_wu_safety_factor(
    ply_stress: "PlyStress",
    allowables: StrengthAllowables,
) -> SafetyFactor:
    """Compute the Tsai-Wu safety factor for a single composite ply.

    The interval bounds on SF are obtained by evaluating the scalar function
    at the low and high ends of each strength allowable simultaneously:
    - SF_typical: all strengths at typical values
    - SF_low:     all strengths at low values   (weakest material → lowest SF)
    - SF_high:    all strengths at high values  (strongest material → highest SF)
    """
    s1 = ply_stress.sigma_11.typical
    s2 = ply_stress.sigma_22.typical
    t12 = ply_stress.tau_12.typical
    location = f"ply_{ply_stress.ply_index}"

    # Zero-stress shortcut
    if max(abs(s1), abs(s2), abs(t12)) < 1e-9:
        return SafetyFactor(
            value=Interval.point(999.0, ""),
            pass_at_typical=True,
            dominant_mode="no_load",
            criterion="tsai_wu",
            location=location,
        )

    # Helper to pull scalar from an Interval or plain float
    def _typ(iv: Interval | None) -> float:
        return iv.typical if iv is not None else 0.0

    def _lo(iv: Interval | None) -> float:
        return iv.low if iv is not None else 0.0

    def _hi(iv: Interval | None) -> float:
        return iv.high if iv is not None else 0.0

    sf_typ = _evaluate_tsai_wu(
        s1, s2, t12,
        _typ(allowables.Xt_mpa), _typ(allowables.Xc_mpa),
        _typ(allowables.Yt_mpa), _typ(allowables.Yc_mpa),
        _typ(allowables.S_mpa), allowables.f12_star,
    )
    sf_lo = _evaluate_tsai_wu(
        s1, s2, t12,
        _lo(allowables.Xt_mpa), _lo(allowables.Xc_mpa),
        _lo(allowables.Yt_mpa), _lo(allowables.Yc_mpa),
        _lo(allowables.S_mpa), allowables.f12_star,
    )
    sf_hi = _evaluate_tsai_wu(
        s1, s2, t12,
        _hi(allowables.Xt_mpa), _hi(allowables.Xc_mpa),
        _hi(allowables.Yt_mpa), _hi(allowables.Yc_mpa),
        _hi(allowables.S_mpa), allowables.f12_star,
    )

    sf_low = min(sf_lo, sf_hi, sf_typ)
    sf_high = max(sf_lo, sf_hi, sf_typ)

    return SafetyFactor(
        value=Interval(sf_low, sf_typ, sf_high, ""),
        pass_at_typical=sf_typ >= 1.0,
        dominant_mode="tsai_wu",
        criterion="tsai_wu",
        location=location,
    )


def laminate_safety_factor(
    stack: "LaminateStack",
    condition: "Condition",
    allowables: StrengthAllowables,
) -> tuple[SafetyFactor, ...]:
    """Return a Tsai-Wu safety factor for every ply in the laminate."""
    from material_eval.stress_analysis import ply_stress_field

    ply_stresses = ply_stress_field(stack, condition)
    return tuple(tsai_wu_safety_factor(ps, allowables) for ps in ply_stresses)
