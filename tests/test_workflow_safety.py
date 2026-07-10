from __future__ import annotations

import hashlib
import importlib.util
import json
import os
import re
import subprocess
import sys
import tempfile
import textwrap
import unittest
from pathlib import Path
from unittest.mock import patch


ROOT = Path(__file__).resolve().parents[1]
WORKFLOW_DIR = ROOT / ".github/workflows"
WORKFLOWS = tuple(sorted((*WORKFLOW_DIR.glob("*.yml"), *WORKFLOW_DIR.glob("*.yaml"))))
BUILD_WORKFLOWS = (
    ROOT / ".github/workflows/ci.yaml",
    ROOT / ".github/workflows/auto-release.yml",
)
MDPRESS_WORKFLOWS = BUILD_WORKFLOWS + (ROOT / ".github/workflows/preview-pdf.yml",)
VERIFIER = ROOT / "tools/verify_artifacts.py"
ACTION_PINS = {
    "actions/checkout": ("df4cb1c069e1874edd31b4311f1884172cec0e10", "v6.0.3"),
    "actions/download-artifact": ("3e5f45b2cfb9172054b4087a40e8e0b5a5461e7c", "v8.0.1"),
    "actions/upload-artifact": ("043fb46d1a93c77aae656e7c1c64a875d1fc6a0a", "v7.0.1"),
    "browser-actions/setup-chrome": ("2e1d749697dd1612b833dba4a722266286fbefcd", "v2.1.2"),
    "dependabot/fetch-metadata": ("25dd0e34f4fe68f24cc83900b1fe3fe149efef98", "v3.1.0"),
    "softprops/action-gh-release": ("3bb12739c298aeb8a4eeaf626c5b8d85266b0e65", "v2.6.2"),
}

FAKE_GH = r'''#!/usr/bin/env python3
import json
import os
import sys

args = sys.argv[1:]
with open(os.environ["GH_LOG"], "a", encoding="utf-8") as stream:
    stream.write(json.dumps(args) + "\n")

scenario = os.environ["GH_SCENARIO"]
reasons = {
    "401": "Unauthorized",
    "403": "Forbidden",
    "404": "Not Found",
    "429": "Too Many Requests",
    "503": "Service Unavailable",
}

def fail_http(code):
    print(f"HTTP/2.0 {code} {reasons[code]}")
    print(f"fake gh HTTP {code}", file=sys.stderr)
    raise SystemExit(1)

if args and args[0] == "api":
    endpoint = next((arg for arg in args if arg.startswith("repos/")), "")
    if "/git/ref/tags/preview-pdf" in endpoint:
        if scenario.startswith("ref_network"):
            print("fake gh network failure", file=sys.stderr)
            raise SystemExit(1)
        for code in reasons:
            if scenario.startswith(f"ref_{code}"):
                fail_http(code)
        print("HTTP/2.0 200 OK")
        print('Content-Type: application/json\n\n{"ref":"refs/tags/preview-pdf"}')
    raise SystemExit(0)

if args[:3] == ["release", "view", "preview-pdf"]:
    if "release_missing" in scenario:
        print("release not found", file=sys.stderr)
        raise SystemExit(1)
    if "release_network" in scenario:
        print("fake release network failure", file=sys.stderr)
        raise SystemExit(1)
    for code in reasons:
        if f"release_{code}" in scenario:
            print(f"fake release HTTP {code}", file=sys.stderr)
            raise SystemExit(1)
    raise SystemExit(0)

raise SystemExit(0)
'''


def workflow_step_script(workflow_text, step_name):
    marker = f"      - name: {step_name}\n"
    start = workflow_text.index(marker) + len(marker)
    run_marker = "        run: |\n"
    script_start = workflow_text.index(run_marker, start) + len(run_marker)
    script_end = workflow_text.find("\n      - name:", script_start)
    if script_end < 0:
        script_end = len(workflow_text)
    return textwrap.dedent(workflow_text[script_start:script_end])


def load_verifier():
    if not VERIFIER.exists():
        raise AssertionError("tools/verify_artifacts.py must exist")
    spec = importlib.util.spec_from_file_location("verify_artifacts", VERIFIER)
    if spec is None or spec.loader is None:
        raise AssertionError("tools/verify_artifacts.py must be importable")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def job_block(workflow_text: str, job_name: str) -> str:
    match = re.search(
        rf"(?ms)^  {re.escape(job_name)}:\n.*?(?=^  [A-Za-z0-9_-]+:\n|\Z)",
        workflow_text,
    )
    if match is None:
        raise AssertionError(f"workflow must define the {job_name!r} job")
    return match.group(0)


class WorkflowSafetyTests(unittest.TestCase):
    def test_mdpress_is_extracted_to_an_isolated_directory(self) -> None:
        for workflow in MDPRESS_WORKFLOWS:
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
        self.assertEqual(
            {workflow.name for workflow in WORKFLOWS},
            {"auto-release.yml", "ci.yaml", "dependabot-automerge.yml", "preview-pdf.yml"},
        )
        for workflow in WORKFLOWS:
            with self.subTest(workflow=workflow.name):
                text = workflow.read_text(encoding="utf-8")
                uses_lines = [line.strip() for line in text.splitlines() if "uses:" in line]
                self.assertGreater(len(uses_lines), 0)
                for line in uses_lines:
                    match = re.search(
                        r"uses:\s+(?P<action>[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+)@"
                        r"(?P<sha>[0-9a-f]{40})\s+#\s+(?P<version>v\d+\.\d+\.\d+)\s*$",
                        line,
                    )
                    self.assertIsNotNone(match, line)
                    action = match.group("action")
                    self.assertIn(action, ACTION_PINS)
                    self.assertEqual((match.group("sha"), match.group("version")), ACTION_PINS[action])
                self.assertIn("permissions:", text)
                if "actions/checkout@" in text:
                    checkout_index = text.index("actions/checkout@")
                    checkout_window = text[checkout_index : checkout_index + 240]
                    self.assertIn("persist-credentials: false", checkout_window)

    def test_builds_require_verified_pdf_html_and_source_integrity(self) -> None:
        for workflow in BUILD_WORKFLOWS:
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

        preview = (ROOT / ".github/workflows/preview-pdf.yml").read_text(encoding="utf-8")
        self.assertIn("EXPECTED_README_SHA", preview)
        self.assertIn("sha256sum README.md", preview)
        self.assertIn("python3 tools/verify_artifacts.py", preview)
        self.assertIn("--expected-readme-sha", preview)
        self.assertIn("--pdf dist/ai_beginner_guide.pdf", preview)
        self.assertIn("sha256sum ai_beginner_guide.pdf > SHA256SUMS", preview)
        self.assertIn("sha256sum -c SHA256SUMS", preview)
        self.assertIn("dist/SHA256SUMS", preview)
        self.assertLess(
            preview.index("python3 tools/verify_artifacts.py"),
            preview.index("gh release upload preview-pdf"),
        )

    def test_release_does_not_treat_html_as_optional(self) -> None:
        auto_release = (ROOT / ".github/workflows/auto-release.yml").read_text(encoding="utf-8")
        preview = (ROOT / ".github/workflows/preview-pdf.yml").read_text(encoding="utf-8")
        self.assertNotIn("continue-on-error: true", auto_release)
        for suffix in (".pdf", ".html", "SHA256SUMS"):
            self.assertIn(suffix, auto_release)

        workflows = (
            (auto_release, "release", "ai_beginner_guide-editions"),
            (preview, "publish", "ai_beginner_guide-preview"),
        )
        for text, publish_job_name, artifact_name in workflows:
            with self.subTest(publish_job=publish_job_name):
                global_permissions = text[: text.index("jobs:")]
                build = job_block(text, "build")
                publish = job_block(text, publish_job_name)

                self.assertNotIn("contents: write", global_permissions)
                self.assertIn("permissions:\n      contents: read", build)
                self.assertNotIn("contents: write", build)
                self.assertIn("actions/upload-artifact@", build)
                self.assertIn(f"name: {artifact_name}", build)

                self.assertIn("needs: build", publish)
                self.assertIn("permissions:\n      contents: write", publish)
                self.assertIn("actions/download-artifact@", publish)
                self.assertIn(f"name: {artifact_name}", publish)
                self.assertIn("sha256sum -c SHA256SUMS", publish)
                for forbidden in (
                    "actions/checkout@",
                    "mdpress",
                    "npm install",
                    "curl ",
                    "sudo ",
                    "python3 ",
                    "tools/",
                ):
                    self.assertNotIn(forbidden, publish)

        preview_build = job_block(preview, "build")
        preview_publish = job_block(preview, "publish")
        self.assertNotIn("GH_TOKEN", preview_build)
        self.assertNotIn("github.token", preview_build)
        self.assertIn("GH_TOKEN", preview_publish)
        self.assertIn("github.token", preview_publish)

    def run_preview_scripts(self, scenario):
        preview = (ROOT / ".github/workflows/preview-pdf.yml").read_text(encoding="utf-8")
        scripts = (
            workflow_step_script(preview, "Synchronize mutable preview tag"),
            workflow_step_script(preview, "Create or update preview release"),
        )
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            fake_gh = root / "gh"
            fake_gh.write_text(FAKE_GH, encoding="utf-8")
            fake_gh.chmod(0o755)
            log = root / "commands.jsonl"
            env = os.environ.copy()
            env.update(
                {
                    "PATH": f"{root}:{env.get('PATH', '')}",
                    "GH_LOG": str(log),
                    "GH_SCENARIO": scenario,
                    "GH_TOKEN": "test-token",
                    "GH_REPO": "owner/repo",
                    "GITHUB_REPOSITORY": "owner/repo",
                    "GITHUB_SHA": "a" * 40,
                }
            )
            result = None
            for script in scripts:
                result = subprocess.run(
                    ["/bin/bash", "-c", script],
                    cwd=ROOT,
                    env=env,
                    capture_output=True,
                    text=True,
                )
                if result.returncode != 0:
                    break
            commands = [
                json.loads(line)
                for line in log.read_text(encoding="utf-8").splitlines()
            ]
            return result, commands

    def test_mutable_preview_updates_existing_tag_and_release(self) -> None:
        result, commands = self.run_preview_scripts("ref_200_release_exists")

        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertTrue(any("PATCH" in command for command in commands), commands)
        self.assertFalse(any("POST" in command for command in commands), commands)
        self.assertTrue(
            any(command[:3] == ["release", "edit", "preview-pdf"] for command in commands),
            commands,
        )

    def test_mutable_preview_creates_only_on_explicit_not_found(self) -> None:
        result, commands = self.run_preview_scripts("ref_404_release_missing")

        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertTrue(any("POST" in command for command in commands), commands)
        self.assertFalse(any("PATCH" in command for command in commands), commands)
        self.assertTrue(
            any(command[:3] == ["release", "create", "preview-pdf"] for command in commands),
            commands,
        )

    def test_preview_tag_lookup_fails_closed_on_non_404_errors(self) -> None:
        for scenario in ("ref_401", "ref_403", "ref_429", "ref_503", "ref_network"):
            with self.subTest(scenario=scenario):
                result, commands = self.run_preview_scripts(scenario)
                self.assertNotEqual(result.returncode, 0)
                self.assertEqual(len(commands), 1, commands)
                self.assertEqual(commands[0][0], "api")
                expected = "network failure" if scenario.endswith("network") else scenario.removeprefix("ref_")
                self.assertIn(expected, result.stderr)

    def test_preview_release_lookup_fails_closed_except_exact_not_found(self) -> None:
        scenarios = (
            "ref_200_release_401",
            "ref_200_release_403",
            "ref_200_release_404",
            "ref_200_release_429",
            "ref_200_release_503",
            "ref_200_release_network",
        )
        for scenario in scenarios:
            with self.subTest(scenario=scenario):
                result, commands = self.run_preview_scripts(scenario)
                self.assertNotEqual(result.returncode, 0)
                self.assertTrue(any("PATCH" in command for command in commands), commands)
                self.assertTrue(
                    any(command[:3] == ["release", "view", "preview-pdf"] for command in commands),
                    commands,
                )
                self.assertFalse(
                    any(command[:2] in (["release", "create"], ["release", "edit"]) for command in commands),
                    commands,
                )
                expected = "network failure" if scenario.endswith("network") else scenario.rsplit("release_", 1)[1]
                self.assertIn(expected, result.stderr)

    def test_preview_publish_has_explicit_repo_context_only_in_write_job(self) -> None:
        preview = (ROOT / ".github/workflows/preview-pdf.yml").read_text(encoding="utf-8")
        build = job_block(preview, "build")
        publish = job_block(preview, "publish")

        self.assertNotIn("GH_REPO", build)
        self.assertIn("GH_REPO: ${{ github.repository }}", publish)


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
        with patch.object(
            sys,
            "argv",
            [
                "verify_artifacts.py",
                "--readme",
                "README.md",
                "--expected-readme-sha",
                "0" * 64,
                "--pdf",
                "preview.pdf",
            ],
        ):
            try:
                args = verifier.parse_args()
            except SystemExit as error:
                self.fail(f"PDF-only artifact verification must be supported: {error}")
        self.assertIsNone(args.html)

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
