#!/usr/bin/env python3
"""Lightweight Markdown project checks for book repositories."""

from __future__ import annotations

import re
import sys
from datetime import date, timedelta
from pathlib import Path
from urllib.parse import unquote, urlparse


ROOT = Path(__file__).resolve().parent
SKIP_DIRS = {
    ".agent",
    ".git",
    ".mdpress",
    "_book",
    "_site",
    "dist",
    "node_modules",
}
LINK_RE = re.compile(r"(!?)\[[^\]]*\]\(([^)\s]+(?:\s+\"[^\"]*\")?)\)")
FENCE_RE = re.compile(r"^\s*(`{3,}|~{3,})")
VOLATILE_METADATA_RE = re.compile(
    r"`verified_at`:\s*(?P<verified>\d{4}-\d{2}-\d{2})\s*·\s*"
    r"`expires_at`:\s*(?P<expires>\d{4}-\d{2}-\d{2})\s*·\s*"
    r"`ttl_days`:\s*(?P<ttl>\d+)"
)


def iter_markdown_files() -> list[Path]:
    files: list[Path] = []
    for path in ROOT.rglob("*.md"):
        if any(part in SKIP_DIRS for part in path.relative_to(ROOT).parts):
            continue
        files.append(path)
    return sorted(files)


def strip_fenced_blocks(text: str) -> str:
    output: list[str] = []
    in_fence = False
    fence_marker = ""
    fence_len = 0
    for line in text.splitlines():
        match = FENCE_RE.match(line)
        if match:
            marker = match.group(1)
            char = marker[0]
            length = len(marker)
            if not in_fence:
                in_fence = True
                fence_marker = char
                fence_len = length
            elif char == fence_marker and length >= fence_len:
                in_fence = False
            output.append("")
            continue
        output.append("" if in_fence else line)
    return "\n".join(output)


def check_fences(path: Path, text: str) -> list[str]:
    issues: list[str] = []
    stack: list[tuple[str, int, int]] = []
    for line_no, line in enumerate(text.splitlines(), 1):
        match = FENCE_RE.match(line)
        if not match:
            continue
        marker = match.group(1)
        char = marker[0]
        length = len(marker)
        if not stack:
            stack.append((char, length, line_no))
            continue
        open_char, open_len, _ = stack[-1]
        if char == open_char and length >= open_len:
            stack.pop()
        else:
            stack.append((char, length, line_no))
    for _, _, line_no in stack:
        issues.append(f"{path.relative_to(ROOT)}:{line_no}: unclosed fenced code block")
    return issues


def is_local_target(target: str) -> bool:
    parsed = urlparse(target)
    return not parsed.scheme and not parsed.netloc and not target.startswith("#")


def normalize_target(raw_target: str) -> str:
    target = raw_target.strip()
    if " " in target and target.count('"') >= 2:
        target = target.split(" ", 1)[0]
    return unquote(target.split("#", 1)[0])


def check_links(path: Path, text: str) -> list[str]:
    issues: list[str] = []
    body = strip_fenced_blocks(text)
    for match in LINK_RE.finditer(body):
        raw_target = match.group(2).strip()
        target = normalize_target(raw_target)
        if not target or not is_local_target(raw_target):
            continue
        target_path = (path.parent / target).resolve()
        try:
            target_path.relative_to(ROOT)
        except ValueError:
            continue
        if not target_path.exists():
            line_no = body[: match.start()].count("\n") + 1
            issues.append(
                f"{path.relative_to(ROOT)}:{line_no}: missing local link target: {raw_target}"
            )
    return issues


def check_summary_links() -> list[str]:
    summary = ROOT / "SUMMARY.md"
    if not summary.exists():
        return []
    return check_links(summary, summary.read_text(encoding="utf-8", errors="ignore"))


def check_volatile_facts(
    path: Path | None = None,
    today: date | None = None,
) -> list[str]:
    """Require the volatile-fact ledger to be reverified every 30 days."""
    ledger = path or ROOT / "appendices/appendix_f_volatile_facts.md"
    label = str(ledger)
    try:
        label = str(ledger.relative_to(ROOT))
    except ValueError:
        pass
    if not ledger.is_file():
        return [f"{label}: missing volatile-fact ledger"]

    match = VOLATILE_METADATA_RE.search(ledger.read_text(encoding="utf-8"))
    if match is None:
        return [
            f"{label}: missing verified_at/expires_at/ttl_days metadata for 30-day refresh"
        ]

    try:
        verified_at = date.fromisoformat(match.group("verified"))
        expires_at = date.fromisoformat(match.group("expires"))
    except ValueError as error:
        return [f"{label}: invalid volatile-fact date: {error}"]
    ttl_days = int(match.group("ttl"))
    issues: list[str] = []
    if ttl_days != 30:
        issues.append(f"{label}: volatile facts must use a TTL of exactly 30 days")
    if expires_at - verified_at != timedelta(days=ttl_days):
        issues.append(f"{label}: expires_at must equal verified_at plus ttl_days")

    current_date = today or date.today()
    if verified_at > current_date:
        issues.append(f"{label}: verified_at cannot be in the future")
    if current_date > expires_at:
        issues.append(
            f"{label}: volatile facts expired on {expires_at.isoformat()}; refresh official sources"
        )
    return issues


def main() -> int:
    issues: list[str] = []
    files = iter_markdown_files()
    for path in files:
        text = path.read_text(encoding="utf-8", errors="ignore")
        issues.extend(check_fences(path, text))
        issues.extend(check_links(path, text))
    issues.extend(check_summary_links())
    issues.extend(check_volatile_facts())

    if issues:
        print("\n".join(sorted(set(issues))))
        print(f"\n{len(set(issues))} issue(s) found across {len(files)} Markdown files.")
        return 1
    print(f"All {len(files)} Markdown files passed project checks.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
