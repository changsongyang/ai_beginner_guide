#!/usr/bin/env python3
"""Verify that built book artifacts still represent this repository's book."""

from __future__ import annotations

import argparse
import hashlib
import html
import shutil
import subprocess
from pathlib import Path


DEFAULT_TITLE = "零基础学 AI"
REQUIRED_BOOK_MARKERS = ("第一章",)
FORBIDDEN_MDPRESS_MARKERS = (
    "Why Teams Use mdPress",
    "Get Started In 60 Seconds",
    "Three Ways To Use It",
)


class ArtifactVerificationError(ValueError):
    """Raised when a source or built artifact fails an integrity check."""


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def verify_readme(path: Path, expected_sha256: str) -> None:
    if not path.is_file():
        raise ArtifactVerificationError(f"README is missing: {path}")
    actual = sha256_file(path)
    if actual.lower() != expected_sha256.strip().lower():
        raise ArtifactVerificationError(
            f"README integrity changed during the build: expected {expected_sha256}, got {actual}"
        )


def validate_book_text(text: str, expected_title: str = DEFAULT_TITLE) -> None:
    normalized = html.unescape(text)
    if expected_title not in normalized:
        raise ArtifactVerificationError(f"artifact is missing the book title: {expected_title}")
    missing = [marker for marker in REQUIRED_BOOK_MARKERS if marker not in normalized]
    if missing:
        raise ArtifactVerificationError(
            "artifact is missing expected book content: " + ", ".join(missing)
        )
    polluted = [marker for marker in FORBIDDEN_MDPRESS_MARKERS if marker in normalized]
    if polluted:
        raise ArtifactVerificationError(
            "artifact contains mdPress package documentation: " + ", ".join(polluted)
        )


def extract_pdf_text(path: Path) -> str:
    if not path.is_file() or path.stat().st_size == 0:
        raise ArtifactVerificationError(f"PDF is missing or empty: {path}")
    if not path.read_bytes().startswith(b"%PDF-"):
        raise ArtifactVerificationError(f"file does not have a PDF header: {path}")
    executable = shutil.which("pdftotext")
    if executable is None:
        raise ArtifactVerificationError("pdftotext is required for PDF content verification")
    completed = subprocess.run(
        [executable, "-f", "1", "-l", "8", str(path), "-"],
        check=False,
        capture_output=True,
        text=True,
    )
    if completed.returncode != 0:
        raise ArtifactVerificationError(
            f"pdftotext failed for {path}: {completed.stderr.strip()}"
        )
    return completed.stdout


def verify_pdf(path: Path, expected_title: str = DEFAULT_TITLE) -> None:
    validate_book_text(extract_pdf_text(path), expected_title=expected_title)


def verify_html(path: Path, expected_title: str = DEFAULT_TITLE) -> None:
    if not path.is_file() or path.stat().st_size == 0:
        raise ArtifactVerificationError(f"HTML is missing or empty: {path}")
    validate_book_text(path.read_text(encoding="utf-8"), expected_title=expected_title)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--readme", type=Path, required=True)
    parser.add_argument("--expected-readme-sha", required=True)
    parser.add_argument("--pdf", type=Path, required=True)
    parser.add_argument("--html", type=Path)
    parser.add_argument("--expected-title", default=DEFAULT_TITLE)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    verify_readme(args.readme, args.expected_readme_sha)
    verify_pdf(args.pdf, expected_title=args.expected_title)
    verified = [str(args.pdf)]
    if args.html is not None:
        verify_html(args.html, expected_title=args.expected_title)
        verified.append(str(args.html))
    print("Verified source integrity and artifacts: " + ", ".join(verified))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
