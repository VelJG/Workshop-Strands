import unittest
from pathlib import Path
from tempfile import TemporaryDirectory
from types import SimpleNamespace
from unittest.mock import patch

from workshop.tools import chunk_policy_page, load_policy_pdf


class PolicyCorpusTest(unittest.TestCase):
    def test_chunks_are_bounded_overlapping_and_keep_page_metadata(self):
        text = "Alpha bravo charlie delta echo foxtrot golf hotel india juliet kilo lima mike november oscar."
        chunks = chunk_policy_page(text, page_number=4, max_chars=36, overlap=10)

        self.assertGreater(len(chunks), 1)
        self.assertTrue(all(len(chunk["text"]) <= 36 for chunk in chunks))
        self.assertTrue(all("page 4" in chunk["source"].lower() for chunk in chunks))
        self.assertTrue(set(chunks[0]["text"].split()) & set(chunks[1]["text"].split()))
        self.assertEqual(chunks[0]["text"], "Alpha bravo charlie delta echo")

    def test_empty_page_produces_no_chunks(self):
        self.assertEqual(chunk_policy_page("  \n  ", page_number=1), [])

    def test_pdf_loader_preserves_source_page_and_chunks_text(self):
        with TemporaryDirectory() as directory:
            pdf = Path(directory) / "policy.pdf"
            pdf.write_bytes(b"mock pdf")
            reader = SimpleNamespace(pages=[SimpleNamespace(extract_text=lambda: "Access rules " * 100)])
            with patch("pypdf.PdfReader", return_value=reader):
                chunks = load_policy_pdf(pdf)
        self.assertGreater(len(chunks), 1)
        self.assertTrue(all("page 1" in chunk["source"].lower() for chunk in chunks))


if __name__ == "__main__":
    unittest.main()
