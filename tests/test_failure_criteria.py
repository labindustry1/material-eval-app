"""Tests for material_eval.failure_criteria (Task 5: von_mises + Task 6: tsai_wu)."""
from __future__ import annotations

import math
import unittest

from material_eval.failure_criteria import (
    von_mises_safety_factor,
    tsai_wu_safety_factor,
    laminate_safety_factor,
)
from material_eval.laminates import Lamina, LaminateStack
from material_eval.materials import MaterialCandidate
from material_eval.strength import StrengthAllowables
from material_eval.stress_analysis import PlyStress
from material_eval.uncertainty import Interval


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_material(tensile_mpa: float = 300.0) -> MaterialCandidate:
    return MaterialCandidate(
        name="TestMaterial",
        category="metal",
        density_g_cm3=Interval.point(2.7, "g/cm^3"),
        tensile_strength_mpa=Interval.point(tensile_mpa, "MPa"),
        elastic_modulus_gpa=Interval.point(70.0, "GPa"),
    )


def _make_isotropic_allowables(yield_mpa: float | None, tensile_mpa: float | None = None) -> StrengthAllowables:
    return StrengthAllowables(
        yield_mpa=Interval.point(yield_mpa, "MPa") if yield_mpa is not None else None,
    )


def _make_orthotropic_allowables(
    Xt: float = 1500.0, Xc: float = 1200.0,
    Yt: float = 50.0,  Yc: float = 200.0,
    S: float = 70.0,   f12_star: float = 0.0,
    spread: float = 0.1,
) -> StrengthAllowables:
    def iv(v: float) -> Interval:
        return Interval(v * (1 - spread), v, v * (1 + spread), "MPa")

    return StrengthAllowables(
        Xt_mpa=iv(Xt),
        Xc_mpa=iv(Xc),
        Yt_mpa=iv(Yt),
        Yc_mpa=iv(Yc),
        S_mpa=iv(S),
        f12_star=f12_star,
    )


def _make_ply_stress(idx: int, s11: float, s22: float, t12: float) -> PlyStress:
    return PlyStress(
        ply_index=idx,
        sigma_11=Interval.point(s11, "MPa"),
        sigma_22=Interval.point(s22, "MPa"),
        tau_12=Interval.point(t12, "MPa"),
    )


# ---------------------------------------------------------------------------
# Task 5: von Mises tests
# ---------------------------------------------------------------------------

class TestVonMisesTypicalPass(unittest.TestCase):
    """SF > 1 when stress is well below yield."""

    def test_typical_pass(self) -> None:
        stresses = {"root_top": Interval.point(100.0, "MPa")}
        material = _make_material()
        allowables = _make_isotropic_allowables(yield_mpa=300.0)
        sf = von_mises_safety_factor(stresses, material, allowables)
        self.assertEqual(sf.criterion, "von_mises")
        self.assertEqual(sf.dominant_mode, "yield")
        self.assertAlmostEqual(sf.value.typical, 3.0, places=6)
        self.assertTrue(sf.pass_at_typical)


class TestVonMisesMarginal(unittest.TestCase):
    """SF typical >= 1 but low < 1.5 (marginal zone)."""

    def test_marginal(self) -> None:
        # stress = 200 MPa, yield = 250 MPa  → SF_typical = 1.25
        stresses = {"root_top": Interval.point(200.0, "MPa")}
        material = _make_material()
        allowables = _make_isotropic_allowables(yield_mpa=250.0)
        sf = von_mises_safety_factor(stresses, material, allowables)
        self.assertAlmostEqual(sf.value.typical, 1.25, places=6)
        self.assertTrue(sf.pass_at_typical)
        self.assertEqual(sf.dominant_mode, "yield")


class TestVonMisesFail(unittest.TestCase):
    """SF < 1 when stress exceeds yield."""

    def test_fail(self) -> None:
        # stress = 400 MPa > yield = 300 MPa
        stresses = {"root_top": Interval.point(400.0, "MPa")}
        material = _make_material()
        allowables = _make_isotropic_allowables(yield_mpa=300.0)
        sf = von_mises_safety_factor(stresses, material, allowables)
        self.assertAlmostEqual(sf.value.typical, 0.75, places=6)
        self.assertFalse(sf.pass_at_typical)


class TestVonMisesZeroStress(unittest.TestCase):
    """Zero stress returns SF=999 placeholder."""

    def test_zero_stress_single_location(self) -> None:
        stresses = {"root_top": Interval.point(0.0, "MPa")}
        material = _make_material()
        allowables = _make_isotropic_allowables(yield_mpa=300.0)
        sf = von_mises_safety_factor(stresses, material, allowables)
        self.assertAlmostEqual(sf.value.typical, 999.0)
        self.assertEqual(sf.dominant_mode, "no_load")
        self.assertTrue(sf.pass_at_typical)

    def test_zero_stress_multiple_locations(self) -> None:
        stresses = {
            "root_top": Interval.point(0.0, "MPa"),
            "root_bottom": Interval.point(0.0, "MPa"),
        }
        material = _make_material()
        allowables = _make_isotropic_allowables(yield_mpa=300.0)
        sf = von_mises_safety_factor(stresses, material, allowables)
        self.assertAlmostEqual(sf.value.typical, 999.0)


class TestVonMisesYieldFallbackToTensile(unittest.TestCase):
    """When yield_mpa is None, fall back to material.tensile_strength_mpa."""

    def test_fallback_uses_tensile(self) -> None:
        # No yield in allowables; material tensile = 300 MPa
        stresses = {"section": Interval.point(150.0, "MPa")}
        material = _make_material(tensile_mpa=300.0)
        allowables = _make_isotropic_allowables(yield_mpa=None)
        sf = von_mises_safety_factor(stresses, material, allowables)
        self.assertEqual(sf.dominant_mode, "ultimate")
        self.assertAlmostEqual(sf.value.typical, 2.0, places=6)
        self.assertTrue(sf.pass_at_typical)


class TestVonMisesGoverningLocation(unittest.TestCase):
    """The governing location is chosen by |typical| maximum."""

    def test_governing_key_selection(self) -> None:
        stresses = {
            "root_top": Interval.point(50.0, "MPa"),
            "root_bottom": Interval.point(-200.0, "MPa"),
        }
        material = _make_material()
        allowables = _make_isotropic_allowables(yield_mpa=400.0)
        sf = von_mises_safety_factor(stresses, material, allowables)
        # |−200| > |50|; allowable/200 = 2.0
        self.assertAlmostEqual(sf.value.typical, 2.0, places=6)
        self.assertEqual(sf.location, "root_bottom")

    def test_location_label_override(self) -> None:
        stresses = {"center": Interval.point(100.0, "MPa")}
        material = _make_material()
        allowables = _make_isotropic_allowables(yield_mpa=300.0)
        sf = von_mises_safety_factor(stresses, material, allowables,
                                     location_label="BEAM/mid_span")
        self.assertEqual(sf.location, "BEAM/mid_span")


# ---------------------------------------------------------------------------
# Task 6: Tsai-Wu tests
# ---------------------------------------------------------------------------

class TestTsaiWuTypicalPass(unittest.TestCase):
    """Low stresses relative to allowables → SF >> 1."""

    def test_pass(self) -> None:
        ps = _make_ply_stress(0, s11=100.0, s22=5.0, t12=5.0)
        allowables = _make_orthotropic_allowables()
        sf = tsai_wu_safety_factor(ps, allowables)
        self.assertEqual(sf.criterion, "tsai_wu")
        self.assertEqual(sf.dominant_mode, "tsai_wu")
        self.assertTrue(sf.pass_at_typical)
        self.assertGreater(sf.value.typical, 1.0)
        self.assertEqual(sf.location, "ply_0")


class TestTsaiWuFail(unittest.TestCase):
    """Stresses near/above allowables → SF < 1."""

    def test_fail_high_transverse(self) -> None:
        # Transverse tensile = 50 MPa; apply 80 MPa transverse
        ps = _make_ply_stress(0, s11=0.0, s22=80.0, t12=0.0)
        allowables = _make_orthotropic_allowables(Yt=50.0, spread=0.0)
        sf = tsai_wu_safety_factor(ps, allowables)
        self.assertFalse(sf.pass_at_typical)
        self.assertLess(sf.value.typical, 1.0)


class TestTsaiWuZeroStress(unittest.TestCase):
    """Zero ply stress returns SF=999."""

    def test_zero_ply_stress(self) -> None:
        ps = _make_ply_stress(2, s11=0.0, s22=0.0, t12=0.0)
        allowables = _make_orthotropic_allowables()
        sf = tsai_wu_safety_factor(ps, allowables)
        self.assertAlmostEqual(sf.value.typical, 999.0)
        self.assertEqual(sf.dominant_mode, "no_load")
        self.assertEqual(sf.location, "ply_2")


class TestTsaiWuF12StarEffect(unittest.TestCase):
    """f12_star != 0 changes the coupling term and hence SF."""

    def test_f12_star_zero_vs_nonzero(self) -> None:
        # Mixed s11 + s22 loading – coupling affects SF
        ps = _make_ply_stress(0, s11=200.0, s22=30.0, t12=0.0)
        all_zero = _make_orthotropic_allowables(f12_star=0.0)
        all_half = _make_orthotropic_allowables(f12_star=0.5)
        sf_zero = tsai_wu_safety_factor(ps, all_zero)
        sf_half = tsai_wu_safety_factor(ps, all_half)
        # With coupling, SF should differ
        self.assertNotAlmostEqual(sf_zero.value.typical, sf_half.value.typical, places=3)

    def test_f12_star_zero_no_coupling_shear(self) -> None:
        # Pure shear: with f12_star=0, the coupling term is zero
        ps = _make_ply_stress(0, s11=0.0, s22=0.0, t12=50.0)
        allowables = _make_orthotropic_allowables(S=70.0, spread=0.0, f12_star=1.0)
        sf = tsai_wu_safety_factor(ps, allowables)
        # SF_typical = 1/(F66*t12^2)^0.5 ~ S/t12 = 70/50 = 1.4
        self.assertGreater(sf.value.typical, 1.0)
        self.assertEqual(sf.criterion, "tsai_wu")


class TestLaminateSafetyFactor(unittest.TestCase):
    """laminate_safety_factor wraps tsai_wu per ply."""

    def _make_stack(self) -> LaminateStack:
        return LaminateStack.symmetric_cross_ply(
            e1_gpa=140.0,
            e2_gpa=10.0,
            g12_gpa=5.0,
            nu12=0.3,
            ply_thickness_mm=0.25,
        )

    def _make_condition(self):
        from material_eval.conditions import Condition, Quantity
        return Condition(
            name="test",
            axial_force=Quantity(value=10000.0, unit="N"),
            geometry={"width": Quantity(value=100.0, unit="mm")},
        )

    def test_returns_tuple_of_safety_factors(self) -> None:
        stack = self._make_stack()
        condition = self._make_condition()
        allowables = _make_orthotropic_allowables()
        sfs = laminate_safety_factor(stack, condition, allowables)
        self.assertIsInstance(sfs, tuple)
        self.assertEqual(len(sfs), len(stack.plies))

    def test_all_safety_factors_have_correct_criterion(self) -> None:
        stack = self._make_stack()
        condition = self._make_condition()
        allowables = _make_orthotropic_allowables()
        sfs = laminate_safety_factor(stack, condition, allowables)
        for i, sf in enumerate(sfs):
            self.assertEqual(sf.criterion, "tsai_wu")
            self.assertEqual(sf.location, f"ply_{i}")

    def test_sf_interval_ordering(self) -> None:
        """Interval must satisfy low <= typical <= high for every ply."""
        stack = self._make_stack()
        condition = self._make_condition()
        allowables = _make_orthotropic_allowables()
        sfs = laminate_safety_factor(stack, condition, allowables)
        for sf in sfs:
            self.assertLessEqual(sf.value.low, sf.value.typical)
            self.assertLessEqual(sf.value.typical, sf.value.high)


if __name__ == "__main__":
    unittest.main()
