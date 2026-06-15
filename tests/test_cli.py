"""Integration tests for the CLI entry point."""

import json
import tempfile
from pathlib import Path

from edge_case_enum.__main__ import main


def _run(argv, capsys):
    ret = main(argv)
    out = capsys.readouterr()
    return ret, out.out, out.err


def test_scan_file_text(capsys, tmp_path):
    p = tmp_path / "sample.py"
    p.write_text("x = a / b\n")
    ret, out, _ = _run([str(p)], capsys)
    assert ret == 0
    assert "division" in out


def test_scan_file_json(capsys, tmp_path):
    p = tmp_path / "sample.py"
    p.write_text("x = a / b\n")
    ret, out, _ = _run([str(p), "--format", "json"], capsys)
    assert ret == 0
    data = json.loads(out)
    assert data["total"] >= 1


def test_scan_directory(capsys, tmp_path):
    (tmp_path / "a.py").write_text("x = a / b\n")
    (tmp_path / "b.py").write_text("try:\n pass\nexcept:\n pass\n")
    ret, out, _ = _run([str(tmp_path)], capsys)
    assert ret == 0
    assert "division" in out
    assert "bare-except" in out


def test_nonexistent_path(capsys):
    ret, _, err = _run(["/no/such/path"], capsys)
    assert ret == 1
    assert "does not exist" in err


def test_top_flag(capsys, tmp_path):
    p = tmp_path / "sample.py"
    p.write_text("x = a / b\ny = c / d\nz = e / f\n")
    ret, out, _ = _run([str(p), "--top", "1"], capsys)
    assert ret == 0
    assert "more" in out


def test_category_filter(capsys, tmp_path):
    p = tmp_path / "sample.py"
    p.write_text("x = a / b\ntry:\n pass\nexcept:\n pass\n")
    ret, out, _ = _run([str(p), "--category", "bare-except"], capsys)
    assert ret == 0
    assert "bare-except" in out
    assert "division" not in out
