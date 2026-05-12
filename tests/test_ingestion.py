import tempfile
import unittest
from pathlib import Path

from material_eval.ingestion import ingest_knowledge_base, parse_document


class IngestionTest(unittest.TestCase):
    def test_parse_txt_document_uses_plain_parser(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "note.txt"
            path.write_text("机器人 连杆 轻量化", encoding="utf-8")

            parsed = parse_document(path)

        self.assertEqual(parsed.source, "note.txt")
        self.assertEqual(parsed.parser, "plain-text")
        self.assertIn("机器人", parsed.markdown)

    def test_parse_markdown_document_uses_docling(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "paper.md"
            path.write_text("# 标题\n\n机器人连杆材料。", encoding="utf-8")

            parsed = parse_document(path)

        self.assertEqual(parsed.source, "paper.md")
        self.assertEqual(parsed.parser, "docling")
        self.assertIn("机器人连杆材料", parsed.markdown)

    def test_ingest_knowledge_base_collects_supported_documents(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "a.txt").write_text("文本材料", encoding="utf-8")
            (root / "b.md").write_text("# Markdown材料", encoding="utf-8")
            (root / "ignore.bin").write_bytes(b"ignored")

            parsed = ingest_knowledge_base(root)

        self.assertEqual([doc.source for doc in parsed], ["a.txt", "b.md"])

    def test_ingest_knowledge_base_returns_fresh_list_from_cache(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "a.txt").write_text("文本材料", encoding="utf-8")

            first = ingest_knowledge_base(root)
            second = ingest_knowledge_base(root)

        self.assertIsNot(first, second)
        self.assertEqual(first, second)


if __name__ == "__main__":
    unittest.main()
