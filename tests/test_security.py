import hashlib
import tempfile
from pathlib import Path

import pytest

from src.security import generate_checksums, verify_checksums, ChecksumError


def test_generate_and_verify_checksums():
    with tempfile.TemporaryDirectory() as tmpdir:
        data_dir = Path(tmpdir)
        # Create two fake data files
        (data_dir / "file_a.txt").write_text("hello")
        (data_dir / "file_b.txt").write_text("world")

        checksum_file = data_dir / "checksums.sha256"
        generate_checksums(data_dir, checksum_file, patterns=["*.txt"])
        # Should not raise
        verify_checksums(data_dir, checksum_file)


def test_verify_raises_on_tampered_file():
    with tempfile.TemporaryDirectory() as tmpdir:
        data_dir = Path(tmpdir)
        (data_dir / "file_a.txt").write_text("hello")
        checksum_file = data_dir / "checksums.sha256"
        generate_checksums(data_dir, checksum_file, patterns=["*.txt"])

        # Tamper with the file
        (data_dir / "file_a.txt").write_text("tampered")

        with pytest.raises(ChecksumError, match="file_a.txt"):
            verify_checksums(data_dir, checksum_file)


def test_verify_raises_on_missing_file():
    with tempfile.TemporaryDirectory() as tmpdir:
        data_dir = Path(tmpdir)
        (data_dir / "file_a.txt").write_text("hello")
        checksum_file = data_dir / "checksums.sha256"
        generate_checksums(data_dir, checksum_file, patterns=["*.txt"])

        # Remove the file
        (data_dir / "file_a.txt").unlink()

        with pytest.raises(ChecksumError, match="file_a.txt"):
            verify_checksums(data_dir, checksum_file)
