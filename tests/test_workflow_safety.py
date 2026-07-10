from __future__ import annotations

import hashlib
import importlib.util
import re
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
WORKFLOWS = (
    ROOT / ".github/workflows/ci.yaml",
    ROOT / ".github/workflows/auto-release.yml",
)
VERIFIER = ROOT / "tools/verify_artifacts.py"


def load_verifier():
    if not VERIFIER.exists():
        raise AssertionError("tools/verify_artifacts.py must exist")
    spec = importlib.util.spec_from_file_location("verify_artifacts", VERIFIER)
    if spec is None or spec.loader is None:
        raise AssertionError("tools/verify_artifacts.py must be importable")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class WorkflowSafetyTests(unittest.TestCase):
    def test_mdpress_is_extracted_to_an_isolated_directory(self) -> None:
        for workflow in WORKFLOWS:
            with self.subTest(workflow=workflow.name):
                text = workflow.read_text(encoding="utf-8")
                self.assertNotRegex(
                    text,
                    r'(?m)^\s*tar\s+xzf\s+"\$archive"\s*$',
                    "extracting the full mdPress archive in the repository root overwrites README.md",
                )
                self.assertIn('extract_dir="$(mktemp -d)"', text)
                self.assertRegex(
                    text,
                    r'tar\s+--extract\s+--gzip\s+--file\s+"\$archive"\s+'
                    r'--directory\s+"\$extract_dir"\s+mdpress',
                )

    def test_third_party_actions_are_pinned_and_checkout_drops_credentials(self) -> None:
        for workflow in WORKFLOWS:
            with self.subTest(workflow=workflow.name):
                text = workflow.read_text(encoding="utf-8")
                uses_lines = [line.strip() for line in text.splitlines() if "uses:" in line]
                self.assertGreater(len(uses_lines), 2)
                for line in uses_lines:
                    self.assertRegex(
                        line,
                        r"uses:\s+[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+@[0-9a-f]{40}\s+#\s+v\d",
                    )
                checkout_index = text.index("actions/checkout@")
                checkout_window = text[checkout_index : checkout_index + 240]
                self.assertIn("persist-credentials: false", checkout_window)

    def test_builds_require_verified_pdf_html_and_source_integrity(self) -> None:
        for workflow in WORKFLOWS:
            with self.subTest(workflow=workflow.name):
                text = workflow.read_text(encoding="utf-8")
                self.assertIn("EXPECTED_README_SHA", text)
                self.assertIn("sha256sum README.md", text)
                self.assertIn("tools/verify_artifacts.py", text)
                self.assertIn("--expected-readme-sha", text)
                self.assertRegex(text, r"mdpress build --format pdf --output dist/[^\s]+\.pdf")
                self.assertIn("tools/build_html_reader.py", text)
                self.assertIn("timeout --signal=TERM 8m python3 tools/render_mermaid.py", text)
                self.assertIn("using source fallback", text)
                self.assertIn("--pdf", text)
                self.assertIn("--html", text)
                self.assertIn("SHA256SUMS", text)
                self.assertIn("python3 -m unittest discover -s tests -v", text)

    def test_release_does_not_treat_html_as_optional(self) -> None:
        text = (ROOT / ".github/workflows/auto-release.yml").read_text(encoding="utf-8")
        self.assertNotIn("continue-on-error: true", text)
        for suffix in (".pdf", ".html", "SHA256SUMS"):
            self.assertIn(suffix, text)


class ArtifactVerifierTests(unittest.TestCase):
    def test_released_v130_symptom_is_rejected(self) -> None:
        verifier = load_verifier()
        released_text = (ROOT / "tests/fixtures/v1.3.0-released-pages.txt").read_text(
            encoding="utf-8"
        )
        with self.assertRaises(verifier.ArtifactVerificationError):
            verifier.validate_book_text(released_text, expected_title="零基础学 AI")

    def test_clean_book_text_is_accepted(self) -> None:
        verifier = load_verifier()
        verifier.validate_book_text(
            "零基础学 AI\n第一章 走进人工智能世界\n第二章 AI 核心概念速览",
            expected_title="零基础学 AI",
        )

    def test_readme_hash_detects_source_mutation(self) -> None:
        verifier = load_verifier()
        original = ROOT / "README.md"
        expected = hashlib.sha256(original.read_bytes()).hexdigest()
        verifier.verify_readme(original, expected)

        with tempfile.TemporaryDirectory() as temp_dir:
            changed = Path(temp_dir) / "README.md"
            changed.write_text(original.read_text(encoding="utf-8") + "\nchanged\n", encoding="utf-8")
            with self.assertRaises(verifier.ArtifactVerificationError):
                verifier.verify_readme(changed, expected)

    def test_html_smoke_check_rejects_polluted_content(self) -> None:
        verifier = load_verifier()
        with tempfile.TemporaryDirectory() as temp_dir:
            html_path = Path(temp_dir) / "book.html"
            html_path.write_text(
                "<html><head><title>零基础学 AI</title></head>"
                "<body><h1>Why Teams Use mdPress</h1></body></html>",
                encoding="utf-8",
            )
            with self.assertRaises(verifier.ArtifactVerificationError):
                verifier.verify_html(html_path, expected_title="零基础学 AI")


if __name__ == "__main__":
    unittest.main()
