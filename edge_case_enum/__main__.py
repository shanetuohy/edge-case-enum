"""CLI entry point for edge-case-enum."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from .scanner import scan_directory, scan_file
from .report import to_text, to_json

CATEGORIES = [
    "bare-except",
    "bare-index",
    "division",
    "file-io",
    "optional-param",
    "parse-error",
    "string-format",
    "unchecked-get",
]


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="edge-case-enum",
        description="Enumerate potential edge cases in Python source files via AST analysis.",
    )
    parser.add_argument("path", help="Python file or directory to scan")
    parser.add_argument(
        "--format",
        choices=["text", "json"],
        default="text",
        dest="output_format",
        help="Output format (default: text)",
    )
    parser.add_argument(
        "--top",
        type=int,
        default=None,
        help="Limit output to the first N findings",
    )
    parser.add_argument(
        "--category",
        choices=CATEGORIES,
        default=None,
        help="Show only findings of this category",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    target = Path(args.path)
    if not target.exists():
        print(f"Error: {target} does not exist", file=sys.stderr)
        return 1

    if target.is_file():
        result = scan_file(target)
    else:
        result = scan_directory(target)

    if args.output_format == "json":
        output = to_json(result, top=args.top, category=args.category)
    else:
        output = to_text(result, top=args.top, category=args.category)

    sys.stdout.write(output)
    return 0


if __name__ == "__main__":
    sys.exit(main())
