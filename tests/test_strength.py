"""Tests for material_eval.strength – TDD red phase.

Covers:
  - StrengthAllowables.has_isotropic() true/false
  - StrengthAllowables.has_orthotropic() all-five-fields vs partial
  - StrengthAllowables.f12_star default 0
  - SafetyFactor construction and field access
  - SafetyReport.governing returns the correct factor
  - SafetyReport.status three-tier boundaries
  - SafetyReport.passed = (status == 'pass')
"""

import unittest

from material_eval.strength import SafetyFactor, SafetyReport, StrengthAllowables
from material_eval.uncertainty import Interval


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _interval(low: float, typical: float, high: float, unit: str = "") -> Interval:
    return Interval(low=low, typical=typical, high=high, unit=unit)


# ---------------------------------------------------------------------------
# StrengthAllowables
# ---------------------------------------------------------------------------

class TestStrengthAllowables(unittest.TestCase):
    def test_has_isotropic_true_when_yield_set(self):
        sa = StrengthAllowables(yield_mpa=_interval(200, 250, 300, "MPa"))
        assert sa.has_isotropic() is True

    def test_has_isotropic_false_when_yield_none(self):
        sa = StrengthAllowables()
        assert sa.has_isotropic() is False

    def test_has_orthotropic_true_when_all_five_set(self):
        iv = _interval(100, 120, 140, "MPa")
        sa = StrengthAllowables(
            Xt_mpa=iv,
            Xc_mpa=iv,
            Yt_mpa=iv,
            Yc_mpa=iv,
            S_mpa=iv,
        )
        assert sa.has_orthotropic() is True

    def test_has_orthotropic_false_when_one_field_missing(self):
        iv = _interval(100, 120, 140, "MPa")
        # Missing S_mpa
        sa = StrengthAllowables(
            Xt_mpa=iv,
            Xc_mpa=iv,
            Yt_mpa=iv,
            Yc_mpa=iv,
        )
        assert sa.has_orthotropic() is False

    def test_f12_star_defaults_to_zero(self):
        sa = StrengthAllowables()
        assert sa.f12_star == 0.0

    def test_source_defaults_to_none(self):
        sa = StrengthAllowables()
        assert sa.source is None


# ---------------------------------------------------------------------------
# SafetyFactor
# ---------------------------------------------------------------------------

class TestSafetyFactor(unittest.TestCase):
    def test_construction_and_fields(self):
        sf_val = _interval(1.6, 1.8, 2.0)
        sf = SafetyFactor(
            value=sf_val,
            pass_at_typical=True,
            dominant_mode="yield",
            criterion="von_mises",
            location="BEAM/root_top",
        )
        assert sf.value is sf_val
        assert sf.pass_at_typical is True
        assert sf.dominant_mode == "yield"
        assert sf.criterion == "von_mises"
        assert sf.location == "BEAM/root_top"
        assert sf.notes == ()

    def test_notes_stored_as_tuple(self):
        sf = SafetyFactor(
            value=_interval(1.0, 1.2, 1.4),
            pass_at_typical=False,
            dominant_mode="tsai_wu",
            criterion="tsai_wu",
            location="ply_0",
            notes=("note_a", "note_b"),
        )
        assert sf.notes == ("note_a", "note_b")


# ---------------------------------------------------------------------------
# SafetyReport
# ---------------------------------------------------------------------------

def _make_factor(low: float, typical: float, high: float) -> SafetyFactor:
    return SafetyFactor(
        value=_interval(low, typical, high),
        pass_at_typical=typical >= 1.0,
        dominant_mode="yield",
        criterion="von_mises",
        location="test_loc",
    )


class TestSafetyReport(unittest.TestCase):
    def test_governing_returns_correct_factor(self):
        f0 = _make_factor(1.6, 1.8, 2.0)
        f1 = _make_factor(0.8, 1.0, 1.2)
        report = SafetyReport(
            factors=(f0, f1),
            governing_index=1,
            method="von_mises",
        )
        assert report.governing is f1

    def test_status_pass_when_low_ge_1_5(self):
        report = SafetyReport(
            factors=(_make_factor(1.5, 1.7, 1.9),),
            governing_index=0,
            method="von_mises",
        )
        assert report.status == "pass"

    def test_status_marginal_when_low_lt_1_5_and_typical_ge_1_0(self):
        # low=1.0, typical=1.49, high=1.6  →  low < 1.5 but typical >= 1.0 → "marginal"
        report = SafetyReport(
            factors=(_make_factor(1.0, 1.49, 1.6),),
            governing_index=0,
            method="von_mises",
        )
        assert report.status == "marginal"

    def test_status_fail_when_typical_lt_1_0(self):
        report = SafetyReport(
            factors=(_make_factor(0.5, 0.99, 1.2),),
            governing_index=0,
            method="von_mises",
        )
        assert report.status == "fail"

    def test_passed_true_when_status_pass(self):
        report = SafetyReport(
            factors=(_make_factor(1.5, 1.7, 1.9),),
            governing_index=0,
            method="von_mises",
        )
        assert report.passed is True

    def test_passed_false_when_status_marginal(self):
        # low=1.2, typical=1.49, high=1.6  →  marginal → passed is False
        report = SafetyReport(
            factors=(_make_factor(1.2, 1.49, 1.6),),
            governing_index=0,
            method="von_mises",
        )
        assert report.passed is False


if __name__ == "__main__":
    unittest.main()
