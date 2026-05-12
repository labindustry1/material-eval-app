import tempfile
import unittest
from pathlib import Path

from material_eval.artifacts import write_markdown_report


class ArtifactTest(unittest.TestCase):
    def test_write_markdown_report_creates_directory_and_file(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = write_markdown_report(
                filename="测试/报告?.md",
                markdown="# 报告",
                root=Path(tmp) / "reports",
            )

            self.assertTrue(path.exists())
            self.assertEqual(path.read_text(encoding="utf-8"), "# 报告")
            self.assertEqual(path.name, "测试-报告-.md")


if __name__ == "__main__":
    unittest.main()
