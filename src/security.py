from __future__ import annotations
import hashlib
from pathlib import Path


class ChecksumError(RuntimeError):
    pass


def _sha256(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()


def generate_checksums(
    data_dir: Path,
    checksum_file: Path,
    patterns: list[str] | None = None,
) -> None:
    """Generate SHA-256 checksums for data files. Run once after download."""
    if patterns is None:
        patterns = ["*.geojson", "*.gpkg", "*.shp", "*.csv"]

    lines = []
    for pattern in patterns:
        for path in sorted(data_dir.glob(pattern)):
            digest = _sha256(path)
            lines.append(f"{digest}  {path.name}\n")

    checksum_file.write_text("".join(lines))


def verify_checksums(data_dir: Path, checksum_file: Path) -> None:
    """Verify all files listed in checksum_file. Raises ChecksumError on failure."""
    if not checksum_file.exists():
        raise ChecksumError(f"Checksum file not found: {checksum_file}")

    for line in checksum_file.read_text().splitlines():
        line = line.strip()
        if not line:
            continue
        expected_hash, filename = line.split("  ", 1)
        filepath = data_dir / filename
        if not filepath.exists():
            raise ChecksumError(f"Data file missing: {filename}")
        actual_hash = _sha256(filepath)
        if actual_hash != expected_hash:
            raise ChecksumError(
                f"Checksum mismatch for {filename}: "
                f"expected {expected_hash[:8]}..., got {actual_hash[:8]}..."
            )
