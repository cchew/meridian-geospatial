# scripts/precompute_land_cover_clusters.py
"""One-off: cluster Western NSW PHN's SA2s by AlphaEarth embedding, label the
lowest-density cluster "non-built-up". Writes
data/land_cover_clusters_western_nsw.parquet for src/land_cover.py to read
at runtime.

See docs/superpowers/specs/2026-09-20-meridian-alphaearth-land-cover-design.md.

This applies Stage 2 of the geo-ai learning path's method (cluster AlphaEarth
embeddings, density-rank the clusters -- see
docs/research/geo-ai/stage2_act_sa1_clustering.py) to a new region (Western
NSW PHN, not ACT) and a coarser areal unit (SA2, not SA1). That transfer is
untested, not re-validated here -- see stage3-notes.md.

One-time setup: same as docs/research/geo-ai/stage1_alphaearth_embeddings.py
(earthengine authenticate, EE_PROJECT env var).

Run (from projects/meridian-geospatial/repo/): python3 scripts/precompute_land_cover_clusters.py
"""
from __future__ import annotations
import json
import os
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import ee
import geopandas as gpd
import pandas as pd
from sklearn.cluster import KMeans
from sklearn.decomposition import PCA
from sklearn.preprocessing import StandardScaler

from src.spatial import load_sa2_access, load_sa2_geometries

EE_PROJECT = os.environ.get("EE_PROJECT")
if not EE_PROJECT:
    raise SystemExit("Set the EE_PROJECT environment variable to your Earth Engine Cloud project ID.")

PHN_NAME = "Western NSW"
EMBEDDING_COLLECTION = "GOOGLE/SATELLITE_EMBEDDING/V1/ANNUAL"
EMBEDDING_BANDS = [f"A{i:02d}" for i in range(64)]
# GDA2020 / Australian Albers -- a genuine equal-area projection, verified via
# pyproj during planning. Not EPSG:7855 (a UTM zone, fine for the
# distance/buffer math elsewhere in this repo but wrong for area across a
# PHN spanning multiple UTM zones) and not EPSG:7845 (GDA2020 / GA LCC,
# conformal, not equal-area -- an easy and checked-for mistake).
EQUAL_AREA_CRS = "EPSG:9473"
OUT_PATH = "data/land_cover_clusters_western_nsw.parquet"


def get_embedding_image(aoi: ee.Geometry, year: int = 2024) -> ee.Image:
    start = f"{year}-01-01"
    end = f"{year + 1}-01-01"
    collection = ee.ImageCollection(EMBEDDING_COLLECTION).filterDate(start, end).filterBounds(aoi)
    return collection.mosaic().toFloat().clip(aoi)


def pull_sa2_embeddings(sa2: gpd.GeoDataFrame, batch_size: int = 1) -> pd.DataFrame:
    """One 64-dim AlphaEarth 2024 annual-embedding zonal mean per SA2, via
    server-side reduceRegions (same pattern as
    docs/research/geo-ai/stage2_act_sa1_clustering.py::pull_sa1_embeddings,
    reimplemented here rather than imported across repos).

    Reduced at scale=200 with tileScale=8, not at AlphaEarth's native 10m.
    Western NSW's SA2s range up to 146,684 km^2 (tested at both a small,
    94 km^2, SA2 and the largest in the dataset); at 10m the largest is
    ~1.5 trillion pixels, which is intractable for Earth Engine's synchronous
    compute budget no matter how the work is batched or tiled -- it times out
    consistently, not intermittently. scale=200 cuts the pixel count ~400x
    while staying far finer than the SA2 polygons themselves (~10km-140km
    across), which is ample for the coarse 3-cluster land-use signal this
    script produces (not fine-detail mapping). tileScale=8 tells EE to use
    smaller internal compute tiles, giving each request extra headroom.
    Verified live at both size extremes: SA2 103011059 (94 km^2) in 6.24s and
    SA2 105021098 (146,684 km^2) in 32.28s, both returning band means in the
    expected -1 to 1 range.

    batch_size=1 (one SA2 per getInfo() call) and the retry/backoff loop below
    remain as complementary defence: smaller per-call AOIs and a retry on
    genuine transient EE load still help, they just were not the fix for the
    timeouts above.
    """
    all_rows = []
    for start in range(0, len(sa2), batch_size):
        batch = sa2.iloc[start:start + batch_size]
        fc = ee.FeatureCollection(json.loads(batch[["SA2_CODE21", "geometry"]].to_json()))
        image = get_embedding_image(fc.geometry().bounds(), year=2024)
        reduced = image.reduceRegions(collection=fc, reducer=ee.Reducer.mean(), scale=200, tileScale=8)
        for attempt in range(1, 4):
            try:
                info = reduced.getInfo()
                break
            except ee.ee_exception.EEException as e:
                if attempt == 3:
                    raise
                sleep_s = 10 if attempt == 1 else 30
                print(f"  retry {attempt} (of 2) for SA2 batch after EEException: {e}")
                time.sleep(sleep_s)
        for feat in info["features"]:
            props = feat["properties"]
            row = {"SA2_CODE21": props["SA2_CODE21"]}
            row.update({band: props.get(band) for band in EMBEDDING_BANDS})
            all_rows.append(row)
    return pd.DataFrame(all_rows)


def main():
    os.makedirs("data", exist_ok=True)
    ee.Initialize(project=EE_PROJECT)

    access = load_sa2_access()
    sa2 = load_sa2_geometries()

    phn_access = access[access["PHN_NAME"] == PHN_NAME].drop_duplicates(subset=["SA2_CODE21"])
    sa2_phn = sa2.merge(phn_access[["SA2_CODE21", "Person"]], on="SA2_CODE21", how="inner")
    sa2_phn = sa2_phn[sa2_phn.geometry.notna() & ~sa2_phn.geometry.is_empty]
    print(f"{PHN_NAME} SA2 polygons: {len(sa2_phn)}")

    print("pulling embeddings (6-32s per SA2 depending on polygon size)...")
    embeddings = pull_sa2_embeddings(sa2_phn)
    print(f"embeddings pulled: {len(embeddings)}")

    merged = sa2_phn.merge(embeddings, on="SA2_CODE21", how="inner")
    before_dropna = len(merged)
    merged = merged.dropna(subset=EMBEDDING_BANDS + ["Person"])
    print(f"merged rows: {before_dropna}, after dropping null embedding bands/population: {len(merged)}")

    merged["area_km2"] = merged.to_crs(EQUAL_AREA_CRS).geometry.area / 1e6
    before = len(merged)
    # Defensive guard, not currently triggered for Western NSW (verified
    # during planning: 38 SA2s, min population 3, no nulls) -- cheap
    # insurance if this script is rerun for a different, sparser region.
    merged = merged[(merged["Person"] > 0) & (merged["area_km2"] > 0)]
    print(f"merged rows: {before}, after dropping zero-population/zero-area: {len(merged)}")

    merged["pop_density_km2"] = merged["Person"] / merged["area_km2"]

    embedding_matrix = merged[EMBEDDING_BANDS].to_numpy()
    scaled = StandardScaler().fit_transform(embedding_matrix)
    n_components = min(15, scaled.shape[0] - 1)
    pca = PCA(n_components=n_components, random_state=0)
    pcs = pca.fit_transform(scaled)
    print(f"PCA({n_components}) explained variance ratio sum: {sum(pca.explained_variance_ratio_):.3f}")

    km = KMeans(n_clusters=3, random_state=0, n_init=10)
    merged["cluster_id"] = km.fit_predict(pcs)

    density_by_cluster = merged.groupby("cluster_id")["pop_density_km2"].mean().sort_values()
    non_built_up_cluster = density_by_cluster.index[0]
    print("cluster mean density (people/km^2), lowest = non-built-up:")
    print(density_by_cluster.to_string())

    merged["land_cover_label"] = merged["cluster_id"].apply(
        lambda c: "non-built-up" if c == non_built_up_cluster else "built-up"
    )
    print(merged["land_cover_label"].value_counts().to_string())

    out = merged[["SA2_CODE21", "cluster_id", "land_cover_label"]]
    out.to_parquet(OUT_PATH, index=False)
    print(f"wrote {OUT_PATH}")


if __name__ == "__main__":
    main()
