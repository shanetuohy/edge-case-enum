"""Text and JSON renderers for scanner results."""

from __future__ import annotations

import json
from collections import defaultdict

from .scanner import ScanResult


def to_text(result: ScanResult, top: int | None = None, category: str | None = None) -> str:
    """Render findings as human-readable text grouped by file then category."""
    findings = _filter(result, category)

    by_file: dict[str, dict[str, list[tuple[int, str]]]] = defaultdict(lambda: defaultdict(list))
    for f in findings:
        by_file[f.file][f.category].append((f.line, f.message))

    lines: list[str] = []
    count = 0
    for filename in sorted(by_file):
        lines.append(f"\n{filename}")
        lines.append("=" * len(filename))
        for cat in sorted(by_file[filename]):
            lines.append(f"  [{cat}]")
            for line_no, msg in sorted(by_file[filename][cat]):
                if top is not None and count >= top:
                    remaining = len(findings) - top
                    lines.append(f"\n... and {remaining} more finding(s) (use --top to see more)")
                    return "\n".join(lines) + "\n"
                lines.append(f"    line {line_no}: {msg}")
                count += 1

    if not lines:
        return "No findings.\n"

    total = len(findings)
    lines.insert(0, f"Found {total} potential edge case(s):")
    return "\n".join(lines) + "\n"


def to_json(result: ScanResult, top: int | None = None, category: str | None = None) -> str:
    """Render findings as JSON grouped by file and category."""
    findings = _filter(result, category)
    if top is not None:
        findings = findings[:top]

    by_file: dict[str, dict[str, list[dict]]] = defaultdict(lambda: defaultdict(list))
    for f in findings:
        by_file[f.file][f.category].append({"line": f.line, "message": f.message})

    output = {
        "total": len(findings),
        "files": {
            filename: dict(cats) for filename, cats in sorted(by_file.items())
        },
    }
    return json.dumps(output, indent=2) + "\n"


def _filter(result: ScanResult, category: str | None) -> list:
    if category:
        return [f for f in result.findings if f.category == category]
    return list(result.findings)
