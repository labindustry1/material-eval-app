"""Tests for material_eval.alternatives – TDD (Task 8)."""
from __future__ import annotations

import unittest

from material_eval.catalog import Catalog, PartTemplate
from material_eval.conditions import Condition, Quantity
from material_eval.material_property_library import MaterialPropertyLibrary, MaterialRecord
from material_eval.uncertainty import EnvelopeReport, EnvelopeSpec, Violation


class SuggestAlternativesForTest(unittest.TestCase):
    """Tests for suggest_alternatives_for() using the real Phase-1 seed library."""

    def setUp(self):
        self.library = MaterialPropertyLibrary()
        # Grab any PartTemplate from the catalog for call signature compliance
        catalog = Catalog()
        self.part = catalog.parts[0]

    def test_room_temperature_returns_at_least_one_suggestion(self):
        """Materials with envelope covering 25 °C should appear."""
        from material_eval.alternatives import suggest_alternatives_for

        condition = Condition(temperature=Quantity(value=25, unit="degC"))
        suggestions = suggest_alternatives_for(condition, self.part, self.library)

        self.assertIsInstance(suggestions, tuple)
        self.assertGreaterEqual(len(suggestions), 1)

    def test_extreme_temperature_returns_empty_tuple(self):
        """500 °C exceeds every material's temperature envelope – no suggestions."""
        from material_eval.alternatives import suggest_alternatives_for

        condition = Condition(temperature=Quantity(value=500, unit="degC"))
        suggestions = suggest_alternatives_for(condition, self.part, self.library)

        self.assertIsInstance(suggestions, tuple)
        self.assertEqual(len(suggestions), 0)

    def test_limit_parameter_is_respected(self):
        """Result must never exceed the requested limit."""
        from material_eval.alternatives import suggest_alternatives_for

        condition = Condition(temperature=Quantity(value=25, unit="degC"))
        suggestions = suggest_alternatives_for(condition, self.part, self.library, limit=2)

        self.assertLessEqual(len(suggestions), 2)

    def test_suggestion_fields_are_populated(self):
        """Each AlternativeSuggestion must carry id, name, category, envelope_source."""
        from material_eval.alternatives import AlternativeSuggestion, suggest_alternatives_for

        condition = Condition(temperature=Quantity(value=25, unit="degC"))
        suggestions = suggest_alternatives_for(condition, self.part, self.library)

        for s in suggestions:
            self.assertIsInstance(s, AlternativeSuggestion)
            self.assertTrue(s.material_id)
            self.assertTrue(s.material_name)
            self.assertTrue(s.category)
            # envelope_source may be None or a non-empty string
            if s.envelope_source is not None:
                self.assertIsInstance(s.envelope_source, str)


class MissingDataHintsTest(unittest.TestCase):
    """Tests for missing_data_hints()."""

    def _make_violation(self, axis: str, input_value: float, lo: float, hi: float) -> Violation:
        return Violation(axis=axis, input_value=input_value, allowed_range=(lo, hi))

    def test_temperature_violation_yields_hint_containing_chinese_label(self):
        """A temperature_C violation should produce a hint that contains '温度'."""
        from material_eval.alternatives import missing_data_hints

        violation = self._make_violation("temperature_C", 300.0, -50.0, 150.0)
        report = EnvelopeReport(violations=(violation,), has_declared_envelope=True)

        record = MaterialRecord(
            id="aluminum_7075_t6",
            name="7075-T6 铝合金",
            category="金属",
            form="",
            process="",
        )
        hints = missing_data_hints(record, report, None)

        self.assertIsInstance(hints, tuple)
        self.assertGreaterEqual(len(hints), 1)
        self.assertTrue(any("温度" in h for h in hints))

    def test_missing_strength_allowables_with_axial_force_yields_strength_hint(self):
        """No strength_allowables + axial_force condition → hint about strength data."""
        from material_eval.alternatives import missing_data_hints

        report = EnvelopeReport(violations=(), has_declared_envelope=True)
        condition = Condition(axial_force=Quantity(value=1000, unit="N"))
        record = MaterialRecord(
            id="test_mat",
            name="测试材料",
            category="金属",
            form="",
            process="",
        )
        # MaterialRecord has no strength_allowables field yet (Task 2); duck-typed via getattr
        hints = missing_data_hints(record, report, condition)

        self.assertIsInstance(hints, tuple)
        self.assertGreaterEqual(len(hints), 1)
        self.assertTrue(any("强度" in h for h in hints))

    def test_no_violations_no_force_yields_empty_hints(self):
        """Clean envelope report + no force fields → no hints."""
        from material_eval.alternatives import missing_data_hints

        report = EnvelopeReport(violations=(), has_declared_envelope=True)
        condition = Condition(temperature=Quantity(value=25, unit="degC"))
        record = MaterialRecord(
            id="test_mat",
            name="测试材料",
            category="金属",
            form="",
            process="",
        )
        hints = missing_data_hints(record, report, condition)

        self.assertEqual(hints, ())

    def test_deduplication_of_identical_hints(self):
        """Duplicate violations on same axis should yield deduplicated hints."""
        from material_eval.alternatives import missing_data_hints

        v1 = self._make_violation("temperature_C", 300.0, -50.0, 150.0)
        v2 = self._make_violation("temperature_C", 300.0, -50.0, 150.0)
        report = EnvelopeReport(violations=(v1, v2), has_declared_envelope=True)

        record = MaterialRecord(
            id="test_mat",
            name="测试材料",
            category="金属",
            form="",
            process="",
        )
        hints = missing_data_hints(record, report, None)

        # All hints should be unique
        self.assertEqual(len(hints), len(set(hints)))


if __name__ == "__main__":
    unittest.main()
