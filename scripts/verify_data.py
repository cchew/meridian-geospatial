#!/usr/bin/env python3
"""
Standalone checksum verification. Run before any demo.
Usage: python scripts/verify_data.py
"""
from pathlib import Path
from src.security import verify_checksums, ChecksumError

DATA_DIR = Path("data")
CHECKSUM_FILE = DATA_DIR / "checksums.sha256"

try:
    verify_checksums(DATA_DIR, CHECKSUM_FILE)
    print("All data files verified OK.")
except ChecksumError as e:
    print(f"ERROR: {e}")
    raise SystemExit(1)
