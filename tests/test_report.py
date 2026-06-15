"""Tests for text and JSON output formatting."""

import json

from edge_case_enum.scanner import ScanResult
from edge_case_enum.report import to_text, to_json


def _sample_result():
    r = ScanResult()
    r.add("foo.py", 10, "division", "Division without zero-check on divisor")
    r.add("foo.py", 20, "bare-except", "Bare except catches all exceptions")
    r.add("bar.py", 5, "division", "Division without zero-check on divisor")
    return r


def test_text_output_groups_by_file():
    text = to_text(_sample_result())
    assert "foo.py" in text
    assert "bar.py" in text
    assert "3 potential edge case(s)" in text


def test_text_top_limits_output():
    text = to_text(_sample_result(), top=1)
    assert "1 potential edge case" not in text  # header shows filtered count
    assert "... and 2 more" in text


def test_text_category_filter():
    text = to_text(_sample_result(), category="bare-except")
    assert "[bare-except]" in text
    assert "[division]" not in text


def test_text_no_findings():
    text = to_text(ScanResult())
    assert "No findings" in text


def test_json_output_structure():
    output = to_json(_sample_result())
    data = json.loads(output)
    assert data["total"] == 3
    assert "foo.py" in data["files"]
    assert "bar.py" in data["files"]
    assert "division" in data["files"]["foo.py"]


def test_json_top_limits():
    output = to_json(_sample_result(), top=2)
    data = json.loads(output)
    assert data["total"] == 2


def test_json_category_filter():
    output = to_json(_sample_result(), category="division")
    data = json.loads(output)
    assert data["total"] == 2
    assert all(
        cat == "division"
        for cats in data["files"].values()
        for cat in cats
    )
