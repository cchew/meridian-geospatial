#!/usr/bin/env python3
"""
One-time script to download all public datasets for Meridian Geospatial.
Run from project root: python scripts/download_data.py

All four datasets are fully automated. After running, commit data/checksums.sha256 to git.
"""
import hashlib
import io
import json
import sys
import zipfile
from pathlib import Path

import requests

DATA_DIR = Path("data")

# --- Dataset URLs (confirmed direct downloads) ---

# 1. PHN boundaries — data.gov.au (NBRA, May 2017 V7, 31 PHNs, CC BY 2.5 AU)
PHN_URL = (
    "https://data.gov.au/data/dataset/ef2d28a4-1ed5-47d0-8e3a-46e25bc4f66b"
    "/resource/3fea565c-3b4e-4698-bd80-52396bb5bcd3/download/phn.geojson"
)

# 2. ABS localities — ASGS Edition 3 2021 (UCL/SUA boundaries, CC BY 4.0, ~270 MB zip)
ABS_URL = (
    "https://data.gov.au/data/dataset/3101b4cc-eff9-4ec7-af8e-ac9eb785ca64"
    "/resource/3db1ed70-fb0e-48b9-a7a3-0aad9d41a785"
    "/download/asgs_ed3_2021_sua_ucl_sos_sosr.zip"
)

# 3. GP locations — Geoscience Australia NHSD MapServer REST API (Layer 0: GENERAL_PRACTICE)
#    Max 2,000 records per request; ~8,082 total nationally. Paginate with resultOffset.
GA_MAPSERVER_URL = (
    "https://services.ga.gov.au/gis/rest/services"
    "/National_HealthDirect_Health_Facilities/MapServer/0/query"
)

# 4. DPA (Distribution Priority Areas for GPs) — data.gov.au (2025a, CC BY 2.5 AU)
DPA_URL = (
    "https://data.gov.au/data/dataset/7d889af7-9506-4eb5-930e-cefe6b5f39c1"
    "/resource/b08c23ce-5db4-4cc7-a473-d9db7d491464/download/dpa_gps_2025a.zip"
)

# 5. ABS 2021 Census GCP — UCL population (NSW only, ~9 MB zip)
#    Table G01 contains Tot_P_P (total persons) keyed by UCL_CODE_2021.
ABS_CENSUS_NSW_URL = (
    "https://www.abs.gov.au/census/find-census-data/datapacks/download"
    "/2021_GCP_UCL_for_NSW_short-header.zip"
)

# 6. Filipcikova et al. (2026) SA2 weighted travel times — Figshare (CC BY)
#    Pre-computed travel times to nearest GP and bulk-billing GP for all SA2s nationally.
FILIPCIKOVA_SA2_URL = "https://ndownloader.figshare.com/files/57536281"

# 7. ABS SA2 2021 boundaries — ArcGIS REST API (ASGS Edition 3, 2021, ~2,473 SA2s)
#    Paginated query; returns GeoJSON. Requires paging because national total exceeds server limit.
ABS_SA2_BASE = (
    "https://geo.abs.gov.au/arcgis/rest/services/ASGS2021/SA2/MapServer/0/query"
)

# 8. DHDA PHN 2023 ↔ SA2 (ASGS 2021) concordance (official; CC BY 4.0 implied via health.gov.au)
#    Confirmed URL: HEAD returns HTTP 200, content-type xlsx, 141 KB, last-modified 2024-03-21.
PHN_SA2_CONCORDANCE_URL = (
    "https://www.health.gov.au/sites/default/files/2024-03"
    "/primary-health-networks-phn-2023-statistical-area-level-2-2021.xlsx"
)


def _get(url: str, **kwargs) -> requests.Response:
    resp = requests.get(url, timeout=120, **kwargs)
    resp.raise_for_status()
    return resp


def download_phn() -> None:
    dest = DATA_DIR / "phn_boundaries.geojson"
    if dest.exists():
        print("  phn_boundaries.geojson already exists, skipping.")
        return
    print("Downloading PHN boundaries...")
    resp = _get(PHN_URL, stream=True)
    with open(dest, "wb") as f:
        for chunk in resp.iter_content(65536):
            f.write(chunk)
    print(f"  Saved {dest.stat().st_size // 1024} KB")


def download_localities() -> None:
    dest = DATA_DIR / "localities.gpkg"
    if dest.exists():
        print("  localities.gpkg already exists, skipping.")
        return
    print("Downloading ABS localities (~270 MB zip)...")
    resp = _get(ABS_URL, stream=True)
    raw = b""
    for chunk in resp.iter_content(65536):
        raw += chunk
    print("  Extracting GeoPackage...")
    with zipfile.ZipFile(io.BytesIO(raw)) as zf:
        gpkg_names = [n for n in zf.namelist() if n.endswith(".gpkg")]
        if not gpkg_names:
            print("  ERROR: no .gpkg found in zip.", file=sys.stderr)
            sys.exit(1)
        # Take the first (and likely only) GeoPackage
        with zf.open(gpkg_names[0]) as src, open(dest, "wb") as dst:
            dst.write(src.read())
    print(f"  Saved {dest.stat().st_size // (1024 * 1024)} MB as localities.gpkg")
    print(f"  Note: GeoPackage may contain multiple layers. Spatial layer used: UCL_2021_AUST")


def download_gp_locations() -> None:
    dest = DATA_DIR / "gp_locations.geojson"
    if dest.exists():
        print("  gp_locations.geojson already exists, skipping.")
        return
    print("Downloading GP locations via GA MapServer REST API...")
    features = []
    offset = 0
    page_size = 2000
    while True:
        params = {
            "where": "1=1",
            "outFields": "*",
            "f": "geojson",
            "resultOffset": offset,
            "resultRecordCount": page_size,
        }
        resp = _get(GA_MAPSERVER_URL, params=params)
        page = resp.json()
        batch = page.get("features", [])
        features.extend(batch)
        print(f"  Fetched {len(features)} records...")
        # ArcGIS returns exceededTransferLimit=True when more pages remain
        if not page.get("exceededTransferLimit", False) or len(batch) < page_size:
            break
        offset += page_size

    geojson = {
        "type": "FeatureCollection",
        "features": features,
    }
    dest.write_text(json.dumps(geojson))
    print(f"  Saved {len(features)} GP locations to gp_locations.geojson")


def download_dpa() -> None:
    dest = DATA_DIR / "dpa.shp"
    if dest.exists():
        print("  dpa.shp already exists, skipping.")
        return
    print("Downloading DPA shapefiles (2025a)...")
    resp = _get(DPA_URL, stream=True)
    raw = b""
    for chunk in resp.iter_content(65536):
        raw += chunk
    print("  Extracting shapefiles...")
    # Shapefile sidecar extensions to extract
    sidecar_exts = {".shp", ".shx", ".dbf", ".prj", ".cpg", ".qpj"}
    with zipfile.ZipFile(io.BytesIO(raw)) as zf:
        extracted = 0
        for name in zf.namelist():
            suffix = Path(name).suffix.lower()
            if suffix in sidecar_exts:
                # Rename dpa_gps_2025a.* → dpa.*
                out_name = "dpa" + suffix
                with zf.open(name) as src, open(DATA_DIR / out_name, "wb") as dst:
                    dst.write(src.read())
                extracted += 1
        if extracted == 0:
            print("  ERROR: no shapefile components found in zip.", file=sys.stderr)
            sys.exit(1)
    print(f"  Saved dpa.shp + {extracted - 1} sidecar files")


def download_population() -> None:
    dest = DATA_DIR / "ucl_population_nsw.csv"
    if dest.exists():
        print("  ucl_population_nsw.csv already exists, skipping.")
        return
    print("Downloading ABS 2021 Census UCL population (NSW, ~9 MB)...")
    resp = _get(ABS_CENSUS_NSW_URL, stream=True)
    raw = b""
    for chunk in resp.iter_content(65536):
        raw += chunk
    print("  Extracting G01 population table...")
    with zipfile.ZipFile(io.BytesIO(raw)) as zf:
        g01_names = [n for n in zf.namelist() if "G01" in n and n.endswith(".csv")]
        if not g01_names:
            print("  ERROR: G01 CSV not found in zip.", file=sys.stderr)
            print("  Files in zip:", zf.namelist()[:20], file=sys.stderr)
            sys.exit(1)
        with zf.open(g01_names[0]) as src:
            dest.write_bytes(src.read())
    print(f"  Saved {dest.stat().st_size // 1024} KB as ucl_population_nsw.csv")


def download_filipcikova_sa2(out_path: Path) -> None:
    """Download Filipcikova et al. (2026) SA2 weighted travel times. CC BY."""
    out_path.parent.mkdir(parents=True, exist_ok=True)
    resp = requests.get(FILIPCIKOVA_SA2_URL, timeout=120, allow_redirects=True)
    resp.raise_for_status()
    out_path.write_bytes(resp.content)


def download_sa2_boundaries(out_path: Path) -> None:
    """Download national SA2 2021 boundaries from ABS hosted ArcGIS, paged."""
    out_path.parent.mkdir(parents=True, exist_ok=True)
    fields = "sa2_code_2021,sa2_name_2021,sa3_code_2021,state_code_2021,state_name_2021"
    page_size = 1000
    offset = 0
    features: list[dict] = []
    while True:
        params = {
            "where": "1=1",
            "outFields": fields,
            "f": "geojson",
            "returnGeometry": "true",
            "resultOffset": offset,
            "resultRecordCount": page_size,
        }
        resp = _get(ABS_SA2_BASE, params=params)
        page = resp.json()
        page_features = page.get("features", [])
        if not page_features:
            break
        features.extend(page_features)
        if len(page_features) < page_size:
            break
        offset += page_size

    # Normalise field names to upper-snake to match Filipcikova
    for f in features:
        props = f["properties"]
        f["properties"] = {
            "SA2_CODE21": str(props["sa2_code_2021"]),
            "SA2_NAME21": props["sa2_name_2021"],
            "SA3_CODE21": str(props.get("sa3_code_2021", "")),
            "STE_CODE21": str(props.get("state_code_2021", "")),
            "STE_NAME21": props.get("state_name_2021", ""),
        }
    out = {"type": "FeatureCollection", "features": features}
    out_path.write_text(json.dumps(out))


def download_phn_sa2_concordance(out_path: Path) -> None:
    """Download DHDA's official PHN 2023 ↔ SA2 (ASGS 2021) concordance."""
    import pandas as pd

    out_path.parent.mkdir(parents=True, exist_ok=True)
    resp = requests.get(PHN_SA2_CONCORDANCE_URL, timeout=120, allow_redirects=True)
    resp.raise_for_status()
    raw = out_path.with_suffix(".raw")
    raw.write_bytes(resp.content)

    if PHN_SA2_CONCORDANCE_URL.endswith(".xlsx"):
        df = pd.read_excel(raw)
    else:
        df = pd.read_csv(raw)

    rename = {
        "SA2_CODE_2021": "SA2_CODE21",
        "SA2_MAINCODE_2021": "SA2_CODE21",
        "PHN_CODE_2023": "PHN_CODE",
        "PHN_NAME_2023": "PHN_NAME",
    }
    df = df.rename(columns={k: v for k, v in rename.items() if k in df.columns})
    required = {"SA2_CODE21", "PHN_CODE", "PHN_NAME"}
    missing = required - set(df.columns)
    if missing:
        raise RuntimeError(
            f"Concordance file missing columns {missing}. Got: {list(df.columns)}"
        )
    df["SA2_CODE21"] = df["SA2_CODE21"].astype(str)
    df[["SA2_CODE21", "PHN_CODE", "PHN_NAME"]].to_csv(out_path, index=False)
    raw.unlink()


def _generate_checksums(data_dir: Path, checksum_file: Path) -> None:
    patterns = ["*.geojson", "*.gpkg", "*.shp", "*.csv"]
    lines = []
    for pattern in patterns:
        for path in sorted(data_dir.glob(pattern)):
            h = hashlib.sha256()
            with open(path, "rb") as f:
                for chunk in iter(lambda: f.read(65536), b""):
                    h.update(chunk)
            lines.append(f"{h.hexdigest()}  {path.name}\n")
    checksum_file.write_text("".join(lines))


def main() -> None:
    DATA_DIR.mkdir(exist_ok=True)
    print("=== Meridian Data Download ===\n")

    download_phn()
    download_localities()
    download_gp_locations()
    download_dpa()
    download_population()
    download_filipcikova_sa2(DATA_DIR / "health_access_sa2.csv")
    download_sa2_boundaries(DATA_DIR / "sa2_2021_aust.geojson")
    download_phn_sa2_concordance(DATA_DIR / "phn_sa2_concordance.csv")

    print()
    checksum_file = DATA_DIR / "checksums.sha256"
    _generate_checksums(DATA_DIR, checksum_file)
    print(f"Checksums written to {checksum_file}")
    print("Commit data/checksums.sha256 to git.")


if __name__ == "__main__":
    main()
