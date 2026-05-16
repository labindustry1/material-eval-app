import json
import tempfile
import unittest
from pathlib import Path

from material_eval.storage import append_refusal_log
from material_eval.uncertainty import EnvelopeReport, Violation


class RefusalLogTest(unittest.TestCase):
    def test_append_creates_jsonl_record(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            log = Path(tmpdir) / "refusal.jsonl"
            class _Mat: name = "PA66"
            class _Part: name = "外壳"
            class _Refusal:
                material = _Mat()
                part = _Part()
                envelope_report = EnvelopeReport(
                    violations=(Violation(axis="temperature_C", input_value=150.0,
                                          allowed_range=(-40.0, 120.0), source="seed"),),
                    has_declared_envelope=True,
                )
            append_refusal_log(_Refusal(), log_path=log)
            content = log.read_text(encoding="utf-8").strip()
            data = json.loads(content)
            self.assertEqual(data["material"], "PA66")
            self.assertEqual(data["part"], "外壳")
            self.assertEqual(data["violations"][0]["axis"], "temperature_C")
            self.assertEqual(data["violations"][0]["input"], 150.0)
            self.assertEqual(data["violations"][0]["allowed"], [-40.0, 120.0])

    def test_append_multiple_lines(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            log = Path(tmpdir) / "refusal.jsonl"
            class _Mat: name = "X"
            class _Part: name = "Y"
            class _Refusal:
                material = _Mat()
                part = _Part()
                envelope_report = EnvelopeReport(violations=(), has_declared_envelope=False)
            append_refusal_log(_Refusal(), log_path=log)
            append_refusal_log(_Refusal(), log_path=log)
            lines = log.read_text(encoding="utf-8").strip().split("\n")
            self.assertEqual(len(lines), 2)
            for line in lines:
                json.loads(line)  # valid JSON
