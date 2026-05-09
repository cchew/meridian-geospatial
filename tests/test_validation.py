# tests/test_validation.py — new file
import re
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
    # Find the Wilcannia (L) row in the markdown table and verify the regression anchor values appear in it
    m = re.search(r"\| Wilcannia[^|]*\|[^|]*\|[^|]*\|\s*(\d+\.\d+)\s*\|\s*(\d+\.\d+)\s*\|", body)
    assert m, "Wilcannia row not found in validation output"
    arcgis_min = float(m.group(1))
    fil_min = float(m.group(2))
    assert 115 <= arcgis_min <= 125, f"ArcGIS Wilcannia expected ~120 min, got {arcgis_min}"
    assert 60 <= fil_min <= 66, f"Filipcikova Wilcannia expected ~63 min, got {fil_min}"
