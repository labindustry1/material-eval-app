import unittest

from material_eval.reporting import build_refusal_report, build_internal_report
from material_eval.uncertainty import EnvelopeReport, Violation


class RefusalReportTest(unittest.TestCase):
    def test_refusal_lists_violation(self):
        report = EnvelopeReport(
            violations=(Violation(axis="temperature_C", input_value=150.0,
                                  allowed_range=(-40.0, 120.0), source="supplier"),),
            has_declared_envelope=True,
        )

        class _M:
            name = "PA66-GF30"

        class _P:
            name = "外壳"

        result = build_refusal_report(
            material=_M(), part=_P(), condition=None,
            envelope_report=report,
            suggested_alternatives=("PEEK-CF30",),
            missing_data_hints=("补充 150°C 拉伸数据",),
        )
        self.assertIn("未出具评估", result.markdown)
        self.assertIn("temperature_C", result.markdown)
        self.assertIn("150.0", result.markdown)
        self.assertIn("[-40.0, 120.0]", result.markdown)
        self.assertIn("supplier", result.markdown)
        self.assertIn("PEEK-CF30", result.markdown)
        self.assertIn("补充 150°C 拉伸数据", result.markdown)

    def test_refusal_without_optional_sections(self):
        report = EnvelopeReport(
            violations=(Violation(axis="stress_MPa", input_value=500.0,
                                  allowed_range=(0.0, 200.0), source=None),),
            has_declared_envelope=True,
        )

        class _M:
            name = "x"

        class _P:
            name = "y"

        result = build_refusal_report(
            material=_M(), part=_P(), condition=None, envelope_report=report,
        )
        self.assertIn("未出具评估", result.markdown)
        self.assertIn("未声明", result.markdown)
        self.assertNotIn("同类材料", result.markdown)

    def test_refusal_violations_tuple_stored(self):
        violation = Violation(axis="humidity_pct", input_value=95.0,
                              allowed_range=(0.0, 80.0), source="internal")
        report = EnvelopeReport(violations=(violation,), has_declared_envelope=True)

        class _M:
            name = "m"

        class _P:
            name = "p"

        result = build_refusal_report(
            material=_M(), part=_P(), condition=None,
            envelope_report=report,
            suggested_alternatives=("AltMat",),
            missing_data_hints=("补充湿度数据",),
        )
        self.assertEqual(result.violations, (violation,))
        self.assertEqual(result.suggested_alternatives, ("AltMat",))
        self.assertEqual(result.missing_data_hints, ("补充湿度数据",))


class InternalReportEnvelopeSectionTest(unittest.TestCase):
    def _make_request(self):
        from material_eval.catalog import Catalog
        from material_eval.computation import calculate_part
        from material_eval.evidence import search_evidence
        from material_eval.materials import build_single_material
        from material_eval.conditions import Condition, Quantity
        from material_eval.uncertainty import EnvelopeSpec

        catalog = Catalog()
        part = catalog.get_part("人形机器人核心骨架", "下肢大扭矩管状连杆")
        material = build_single_material(
            name="测试材料",
            category="合成蛋白/生物基大分子",
            density_g_cm3=1.3,
            tensile_strength_mpa=9600,
            elastic_modulus_gpa=100,
        )
        dimensions = {"diameter": 30, "length": 350, "thickness": 3}
        calculation = calculate_part(part, material, dimensions)
        evidence = search_evidence("机器人 连杆")
        condition = Condition.from_dimensions(
            dimensions,
            temperature=Quantity(value=25.0, unit="degC"),
        )
        envelope_spec = EnvelopeSpec(temperature_C=(-40.0, 120.0), source="supplier")
        envelope_report = envelope_spec.check(condition)
        return material, part, dimensions, calculation, evidence, envelope_report, condition

    def test_envelope_section_present_when_in_range(self):
        material, part, dimensions, calculation, evidence, envelope_report, condition = self._make_request()
        report = build_internal_report(
            material=material,
            part=part,
            dimensions=dimensions,
            calculation=calculation,
            evidence_cards=evidence,
            envelope_report=envelope_report,
            condition=condition,
        )
        self.assertIn("工况包络校验", report.markdown)
        self.assertIn("temperature_C", report.markdown)
        self.assertIn("✓", report.markdown)

    def test_envelope_section_absent_when_not_provided(self):
        material, part, dimensions, calculation, evidence, _, _ = self._make_request()
        report = build_internal_report(
            material=material,
            part=part,
            dimensions=dimensions,
            calculation=calculation,
            evidence_cards=evidence,
        )
        self.assertNotIn("工况包络校验", report.markdown)

    def test_uncertainty_section_always_present(self):
        material, part, dimensions, calculation, evidence, _, _ = self._make_request()
        report = build_internal_report(
            material=material,
            part=part,
            dimensions=dimensions,
            calculation=calculation,
            evidence_cards=evidence,
        )
        self.assertIn("不确定度说明", report.markdown)
        self.assertIn("low / typical / high", report.markdown)

    def test_metrics_table_uses_interval_header(self):
        material, part, dimensions, calculation, evidence, _, _ = self._make_request()
        report = build_internal_report(
            material=material,
            part=part,
            dimensions=dimensions,
            calculation=calculation,
            evidence_cards=evidence,
        )
        self.assertIn("区间", report.markdown)
        # old "数值" header should no longer appear in the metrics table context
        # (we check the new header is present)
        self.assertNotIn("| 数值 |", report.markdown)


class SafetyReportSectionTest(unittest.TestCase):
    """Tests for the 安全性评估 section in build_internal_report."""

    def _make_base_args(self):
        from material_eval.catalog import Catalog
        from material_eval.computation import calculate_part
        from material_eval.evidence import search_evidence
        from material_eval.materials import build_single_material

        catalog = Catalog()
        part = catalog.get_part("人形机器人核心骨架", "下肢大扭矩管状连杆")
        material = build_single_material(
            name="测试材料",
            category="合成蛋白/生物基大分子",
            density_g_cm3=1.3,
            tensile_strength_mpa=9600,
            elastic_modulus_gpa=100,
        )
        dimensions = {"diameter": 30, "length": 350, "thickness": 3}
        calculation = calculate_part(part, material, dimensions)
        evidence = search_evidence("机器人 连杆")
        return dict(
            material=material,
            part=part,
            dimensions=dimensions,
            calculation=calculation,
            evidence_cards=evidence,
        )

    def _make_safety_report(self, low, typical, high, method="von_mises", location="BEAM/root_top"):
        from material_eval.strength import SafetyFactor, SafetyReport
        from material_eval.uncertainty import Interval

        factor = SafetyFactor(
            value=Interval(low, typical, high, ""),
            pass_at_typical=typical >= 1.5,
            dominant_mode="yield",
            criterion=method,
            location=location,
        )
        return SafetyReport(factors=(factor,), governing_index=0, method=method)

    def test_no_safety_report_no_section(self):
        args = self._make_base_args()
        report = build_internal_report(**args)
        self.assertNotIn("安全性评估", report.markdown)

    def test_pass_status_shows_pass_icon(self):
        from material_eval.strength import SafetyFactor, SafetyReport
        from material_eval.uncertainty import Interval

        factor = SafetyFactor(
            value=Interval(1.6, 1.8, 2.0, ""),
            pass_at_typical=True,
            dominant_mode="yield",
            criterion="von_mises",
            location="BEAM/root_top",
        )
        safety_report = SafetyReport(factors=(factor,), governing_index=0, method="von_mises")
        args = self._make_base_args()
        report = build_internal_report(**args, safety_report=safety_report)
        self.assertIn("安全性评估", report.markdown)
        self.assertIn("✓ pass", report.markdown)

    def test_marginal_and_fail_icons(self):
        from material_eval.strength import SafetyFactor, SafetyReport
        from material_eval.uncertainty import Interval

        marginal_factor = SafetyFactor(
            value=Interval(1.2, 1.4, 1.6, ""),
            pass_at_typical=False,
            dominant_mode="tsai_wu",
            criterion="tsai_wu",
            location="ply_0",
        )
        fail_factor = SafetyFactor(
            value=Interval(0.5, 0.9, 1.2, ""),
            pass_at_typical=False,
            dominant_mode="tsai_wu",
            criterion="tsai_wu",
            location="ply_1",
        )
        # governing_index=1 (fail factor is worst)
        safety_report = SafetyReport(
            factors=(marginal_factor, fail_factor),
            governing_index=1,
            method="tsai_wu",
        )
        args = self._make_base_args()
        report = build_internal_report(**args, safety_report=safety_report)
        self.assertIn("⚠ marginal", report.markdown)
        self.assertIn("✗ fail", report.markdown)


if __name__ == "__main__":
    unittest.main()
