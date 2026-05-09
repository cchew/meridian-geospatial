# tests/test_validation.py — new file
import subprocess
import sys
from pathlib import Path


def test_validate_script_runs_and_writes_output():
    repo = Path(__file__).resolve().parents[1]
    out = repo / "docs" / "figures" / "validation-output.md"
    if out.exists():
        out.unlink()
    result = subprocess.run(
        [sys.executable, "scripts/validate_sa2_vs_ucl.py"],
        cwd=repo, capture_output=True, text=True, timeout=120,
    )
    assert result.returncode == 0, result.stderr
    assert out.exists()
    body = out.read_text()
    # Regression on the 2026-05-08 numbers
    assert "Wilcannia" in body
    assert "120" in body  # ArcGIS Wilcannia
    assert "63" in body   # Filipcikova Wilcannia (rounded)
