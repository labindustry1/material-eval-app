"""Tests for material_eval.stress_analysis (Task 3 + Task 4)."""
from __future__ import annotations

import math
import unittest

from material_eval.catalog import PartTemplate, GeometryInput
from material_eval.conditions import Condition, Quantity
from material_eval.laminates import Lamina, LaminateStack
from material_eval.materials import MaterialCandidate
from material_eval.uncertainty import Interval


def _make_material() -> MaterialCandidate:
    return MaterialCandidate(
        name="Test",
        category="metal",
        density_g_cm3=Interval.point(2.7, "g/cm^3"),
        tensile_strength_mpa=Interval.point(300.0, "MPa"),
        elastic_modulus_gpa=Interval.point(70.0, "GPa"),
    )


def _make_part(topology: str) -> PartTemplate:
    return PartTemplate(
        domain="test",
        name="test_part",
        topology=topology,
        constraint="tensile",
        search_suffix="",
        geometry_inputs=(),
    )


def _make_stack_cross_ply() -> LaminateStack:
    """4-layer [0/90/90/0] symmetric cross-ply."""
    return LaminateStack.symmetric_cross_ply(
        e1_gpa=140.0,
        e2_gpa=10.0,
        g12_gpa=5.0,
        nu12=0.3,
        ply_thickness_mm=0.25,
    )


class TestIsotropicStressFieldStrap(unittest.TestCase):
    """Task 3: Test 1 – STRAP pure tension."""

    def test_strap_pure_tension(self) -> None:
        from material_eval.stress_analysis import isotropic_stress_field

        part = _make_part("STRAP")
        material = _make_material()
        condition = Condition(
            width=Quantity(value=30.0, unit="mm"),
            thickness=Quantity(value=2.0, unit="mm"),
            axial_force=Quantity(value=600.0, unit="N"),
        )
        stresses = isotropic_stress_field(part, material, condition)
        self.assertIn("section", stresses)
        # area = 30 * 2 = 60 mm², tensile = 600/60 = 10 MPa
        self.assertAlmostEqual(stresses["section"].typical, 10.0, places=2)
        self.assertEqual(stresses["section"].unit, "MPa")


class TestIsotropicStressFieldBeam(unittest.TestCase):
    """Task 3: Test 2 – BEAM axial only."""

    def test_beam_axial_only(self) -> None:
        from material_eval.stress_analysis import isotropic_stress_field

        part = _make_part("BEAM")
        material = _make_material()
        # diameter=20mm, thickness=2mm → inner=16mm, area=π*(400-256)/4 = π*144/4 ≈ 113.097 mm²
        condition = Condition(
            diameter=Quantity(value=20.0, unit="mm"),
            thickness=Quantity(value=2.0, unit="mm"),
            axial_force=Quantity(value=1000.0, unit="N"),
        )
        stresses = isotropic_stress_field(part, material, condition)
        self.assertIn("root_top", stresses)
        self.assertIn("root_bottom", stresses)
        # axial_stress = 1000/113.097 ≈ 8.84 MPa
        expected = 1000.0 / (math.pi / 4 * (20.0 ** 2 - 16.0 ** 2))
        self.assertAlmostEqual(stresses["root_top"].typical, expected, places=1)
        self.assertAlmostEqual(stresses["root_bottom"].typical, expected, places=1)

    def test_beam_pure_bending(self) -> None:
        """Task 3: Test 3 – BEAM pure bending, root_top > 0, root_bottom < 0."""
        from material_eval.stress_analysis import isotropic_stress_field

        part = _make_part("BEAM")
        material = _make_material()
        condition = Condition(
            diameter=Quantity(value=20.0, unit="mm"),
            thickness=Quantity(value=2.0, unit="mm"),
            bending_moment=Quantity(value=10.0, unit="N*m"),
        )
        stresses = isotropic_stress_field(part, material, condition)
        self.assertIn("root_top", stresses)
        self.assertIn("root_bottom", stresses)
        # bending_stress = M_Nmm * c / I
        # M = 10 N*m = 10000 N*mm, c = 10 mm, I = π*(20⁴-16⁴)/64
        d_o, d_i = 20.0, 16.0
        I = math.pi / 64 * (d_o ** 4 - d_i ** 4)
        expected_bending = 10000.0 * 10.0 / I
        self.assertGreater(stresses["root_top"].typical, 0.0)
        self.assertLess(stresses["root_bottom"].typical, 0.0)
        self.assertAlmostEqual(stresses["root_top"].typical, expected_bending, places=1)
        self.assertAlmostEqual(stresses["root_bottom"].typical, -expected_bending, places=1)


class TestIsotropicStressFieldPlate(unittest.TestCase):
    """Task 3: Test 4 – PLATE membrane only."""

    def test_plate_membrane_only(self) -> None:
        from material_eval.stress_analysis import isotropic_stress_field

        part = _make_part("PLATE")
        material = _make_material()
        condition = Condition(
            length=Quantity(value=200.0, unit="mm"),
            width=Quantity(value=80.0, unit="mm"),
            thickness=Quantity(value=3.0, unit="mm"),
            axial_force=Quantity(value=1000.0, unit="N"),
        )
        stresses = isotropic_stress_field(part, material, condition)
        self.assertIn("center", stresses)
        # area = 80 * 3 = 240 mm², membrane = 1000/240 ≈ 4.167 MPa
        self.assertAlmostEqual(stresses["center"].typical, 1000.0 / 240.0, places=2)
        self.assertEqual(stresses["center"].unit, "MPa")


class TestIsotropicStressFieldZeroLoad(unittest.TestCase):
    """Task 3: Test 5 – Zero load returns zero-width Intervals."""

    def test_zero_load(self) -> None:
        from material_eval.stress_analysis import isotropic_stress_field

        for topology in ("STRAP", "BEAM", "PLATE"):
            part = _make_part(topology)
            material = _make_material()
            condition = Condition(
                diameter=Quantity(value=20.0, unit="mm"),
                thickness=Quantity(value=2.0, unit="mm"),
                width=Quantity(value=30.0, unit="mm"),
                length=Quantity(value=100.0, unit="mm"),
            )
            stresses = isotropic_stress_field(part, material, condition)
            for key, interval in stresses.items():
                with self.subTest(topology=topology, key=key):
                    self.assertAlmostEqual(interval.typical, 0.0, places=8,
                                           msg=f"{topology}/{key} should be zero under zero load")
                    self.assertEqual(interval.unit, "MPa")


class TestPlyStressZeroLoad(unittest.TestCase):
    """Task 4: Test 6 – Zero axial force → all ply stresses zero."""

    def test_ply_stress_zero_load(self) -> None:
        from material_eval.stress_analysis import ply_stress_field

        stack = _make_stack_cross_ply()
        condition = Condition(
            width=Quantity(value=10.0, unit="mm"),
        )
        result = ply_stress_field(stack, condition)
        self.assertEqual(len(result), 4)
        for ps in result:
            self.assertAlmostEqual(ps.sigma_11.typical, 0.0, places=8)
            self.assertAlmostEqual(ps.sigma_22.typical, 0.0, places=8)
            self.assertAlmostEqual(ps.tau_12.typical, 0.0, places=8)


class TestPlyStressAxialOrients(unittest.TestCase):
    """Task 4: Test 7 – 0° ply: sigma_11 > sigma_22; 90° ply: sigma_22 > sigma_11 (abs)."""

    def test_ply_stress_axial_orients(self) -> None:
        from material_eval.stress_analysis import ply_stress_field

        stack = _make_stack_cross_ply()
        condition = Condition(
            width=Quantity(value=10.0, unit="mm"),
            axial_force=Quantity(value=10000.0, unit="N"),
        )
        result = ply_stress_field(stack, condition)
        self.assertEqual(len(result), 4)

        # ply 0 and 3 are 0° → axial load → high sigma_11
        ply_0 = result[0]
        self.assertGreater(abs(ply_0.sigma_11.typical), abs(ply_0.sigma_22.typical))

        # ply 1 and 2 are 90° → transverse → sigma_22 dominant
        ply_1 = result[1]
        self.assertGreater(abs(ply_1.sigma_22.typical), abs(ply_1.sigma_11.typical))


class TestPlyStressLength(unittest.TestCase):
    """Task 4: Test 8 – 3-layer stack → length 3, ply_index 0/1/2."""

    def test_ply_stress_returns_tuple_with_correct_length(self) -> None:
        from material_eval.stress_analysis import ply_stress_field

        stack = LaminateStack(plies=(
            Lamina(e1_gpa=140.0, e2_gpa=10.0, g12_gpa=5.0, nu12=0.3, thickness_mm=0.25, angle_deg=0),
            Lamina(e1_gpa=140.0, e2_gpa=10.0, g12_gpa=5.0, nu12=0.3, thickness_mm=0.25, angle_deg=45),
            Lamina(e1_gpa=140.0, e2_gpa=10.0, g12_gpa=5.0, nu12=0.3, thickness_mm=0.25, angle_deg=90),
        ))
        condition = Condition(
            width=Quantity(value=10.0, unit="mm"),
            axial_force=Quantity(value=5000.0, unit="N"),
        )
        result = ply_stress_field(stack, condition)
        self.assertIsInstance(result, tuple)
        self.assertEqual(len(result), 3)
        for i, ps in enumerate(result):
            self.assertEqual(ps.ply_index, i)


if __name__ == "__main__":
    unittest.main()
