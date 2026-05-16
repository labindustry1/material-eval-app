import math
import unittest

from material_eval.section_analysis import analyze_hollow_circular_section, analyze_rectangular_section
from material_eval.uncertainty import Interval


class SectionAnalysisTest(unittest.TestCase):
    def test_hollow_circular_section_uses_sectionproperties_backend(self):
        properties = analyze_hollow_circular_section(outer_diameter=30, thickness=3)

        exact_area = math.pi / 4 * (30**2 - 24**2)
        exact_inertia = math.pi / 64 * (30**4 - 24**4)

        self.assertEqual(properties.method, "sectionproperties")
        # area_mm2 and inertia_x_mm4 are now Interval (zero-width for exact geometry input)
        self.assertIsInstance(properties.area_mm2, Interval)
        self.assertIsInstance(properties.inertia_x_mm4, Interval)
        self.assertAlmostEqual(properties.area_mm2.typical, exact_area, delta=exact_area * 0.03)
        self.assertAlmostEqual(properties.inertia_x_mm4.typical, exact_inertia, delta=exact_inertia * 0.03)

    def test_rectangular_section_reports_major_and_minor_inertia(self):
        properties = analyze_rectangular_section(width=35, depth=1.2)

        self.assertEqual(properties.method, "sectionproperties")
        self.assertIsInstance(properties.area_mm2, Interval)
        self.assertIsInstance(properties.inertia_x_mm4, Interval)
        self.assertAlmostEqual(properties.area_mm2.typical, 42.0, places=6)
        self.assertAlmostEqual(properties.inertia_x_mm4.typical, 35 * 1.2**3 / 12, places=6)
        self.assertGreater(properties.inertia_y_mm4, properties.inertia_x_mm4.typical)


if __name__ == "__main__":
    unittest.main()
