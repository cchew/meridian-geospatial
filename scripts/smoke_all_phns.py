"""Run Mode 1 (diagnostic) for every PHN; assert no errors."""
from __future__ import annotations
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.models import QueryParams
from src.spatial import load_sa2_access, load_sa2_geometries, build_spatial_context_sa2, list_phns
from src.optimiser import diagnose_sa2_coverage

def main() -> None:
    access = load_sa2_access()
    sa2 = load_sa2_geometries()
    failures = []
    print(f"{'PHN':40s} {'SA2s':>6s} {'med GP min':>12s} {'uncov bulk-billing':>20s}")
    for phn in list_phns(access):
        try:
            params = QueryParams(mode="diagnostic", region=phn,
                                  facility_type="gp_bulk_billing", threshold_min=45)
            ctx = build_spatial_context_sa2(params, access, sa2)
            demand, summary = diagnose_sa2_coverage(
                ctx.demand_points, params.threshold_min, params.facility_type
            )
            print(f"{phn:40s} {len(ctx.demand_points):6d} "
                  f"{ctx.demand_points['gp_min'].median():12.2f} "
                  f"{summary['uncovered_sa2_count']:20d}")
        except Exception as e:
            failures.append((phn, repr(e)))
            print(f"{phn:40s} ERROR: {e}")

    if failures:
        print(f"\n{len(failures)} PHN(s) failed:")
        for phn, err in failures:
            print(f"  - {phn}: {err}")
        sys.exit(1)
    print(f"\nAll {len(list_phns(access))} PHNs passed.")

if __name__ == "__main__":
    main()
