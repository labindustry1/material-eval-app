"""Strength allowables and safety factor data types.

Provides:
  - StrengthAllowables  – material strength limits (isotropic or orthotropic)
  - SafetyFactor        – single safety factor at one location / mode
  - SafetyReport        – collection of factors with status roll-up
"""

from __future__ import annotations

from dataclasses import dataclass

from material_eval.uncertainty import Interval


@dataclass(frozen=True)
class StrengthAllowables:
    """Strength allowable values for a material.

    Isotropic materials use ``yield_mpa``.
    Orthotropic (composite) materials use the five laminate-direction fields.
    ``f12_star`` is the Tsai–Wu interaction parameter (dimensionless).
    """

    yield_mpa: Interval | None = None
    Xt_mpa: Interval | None = None   # Longitudinal tensile strength
    Xc_mpa: Interval | None = None   # Longitudinal compressive strength
    Yt_mpa: Interval | None = None   # Transverse tensile strength
    Yc_mpa: Interval | None = None   # Transverse compressive strength
    S_mpa: Interval | None = None    # In-plane shear strength
    f12_star: float = 0.0            # Tsai–Wu coupling coefficient
    source: str | None = None

    def has_isotropic(self) -> bool:
        """Return True if isotropic yield strength is defined."""
        return self.yield_mpa is not None

    def has_orthotropic(self) -> bool:
        """Return True if all five orthotropic allowables are defined."""
        return all(
            getattr(self, k) is not None
            for k in ("Xt_mpa", "Xc_mpa", "Yt_mpa", "Yc_mpa", "S_mpa")
        )


@dataclass(frozen=True)
class SafetyFactor:
    """A single safety factor result at one location / failure mode.

    Attributes:
        value:           Safety factor as an ``Interval`` (unitless).
        pass_at_typical: Whether the typical value alone satisfies SF >= 1.5.
        dominant_mode:   The controlling failure mode string,
                         e.g. ``"yield"``, ``"ultimate"``, ``"tsai_wu"``, ``"no_load"``.
        criterion:       Analysis method: ``"von_mises"`` or ``"tsai_wu"``.
        location:        Identifier for the structural location,
                         e.g. ``"BEAM/root_top"`` or ``"ply_0"``.
        notes:           Optional supplementary remarks.
    """

    value: Interval
    pass_at_typical: bool
    dominant_mode: str
    criterion: str
    location: str
    notes: tuple[str, ...] = ()


@dataclass(frozen=True)
class SafetyReport:
    """Aggregated safety factor report across multiple locations/modes.

    Attributes:
        factors:          All computed safety factors.
        governing_index:  Index into ``factors`` of the worst (governing) factor.
        method:           Overall analysis method used,
                          e.g. ``"von_mises"``, ``"tsai_wu"``,
                          or ``"skipped_no_matching_allowables"``.
    """

    factors: tuple[SafetyFactor, ...]
    governing_index: int
    method: str

    @property
    def governing(self) -> SafetyFactor:
        """Return the governing (worst-case) safety factor."""
        return self.factors[self.governing_index]

    @property
    def status(self) -> str:
        """Three-tier assessment of the governing safety factor.

        Returns:
            ``'pass'``     if ``SF.value.low >= 1.5``
            ``'marginal'`` if ``SF.value.typical >= 1.0``
            ``'fail'``     otherwise
        """
        sf = self.governing.value
        if sf.low >= 1.5:
            return "pass"
        if sf.typical >= 1.0:
            return "marginal"
        return "fail"

    @property
    def passed(self) -> bool:
        """Return True only when status is ``'pass'``."""
        return self.status == "pass"
