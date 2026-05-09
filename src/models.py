from __future__ import annotations
from dataclasses import dataclass, field
from typing import Literal

import geopandas as gpd
import pandas as pd


class ValidationError(ValueError):
    pass


class ParseError(ValueError):
    pass


class RoutingError(RuntimeError):
    pass


@dataclass
class QueryParams:
    mode: Literal["diagnostic", "prescriptive"]
    region: str
    facility_type: str
    threshold_min: int
    k: int | None = None
    pop_min: int | None = None

    def __post_init__(self) -> None:
        if not 10 <= self.threshold_min <= 120:
            raise ValidationError(
                f"threshold_min must be between 10 and 120, got {self.threshold_min}"
            )
        if self.k is not None and not 1 <= self.k <= 10:
            raise ValidationError(
                f"k must be between 1 and 10, got {self.k}"
            )
        if self.pop_min is not None and not 0 <= self.pop_min <= 50000:
            raise ValidationError(
                f"pop_min must be between 0 and 50000, got {self.pop_min}"
            )


@dataclass
class SpatialContext:
    demand_points: gpd.GeoDataFrame      # localities with population column
    existing_facilities: gpd.GeoDataFrame
    candidates: gpd.GeoDataFrame         # ranked by DPA status + population


@dataclass
class CoverageMatrix:
    matrix: pd.DataFrame      # index=demand_id, columns=facility_id, values=minutes
    demand_ids: list[str]
    facility_ids: list[str]


@dataclass
class OptimisationResult:
    selected_sites: gpd.GeoDataFrame
    covered_before: int
    covered_after: int
    coverage_pct_before: float
    coverage_pct_after: float


@dataclass
class NarrativeContext:
    mode: Literal["diagnostic", "prescriptive"]
    region: str
    threshold_min: int
    covered_population: int
    total_population: int
    coverage_pct: float
    uncovered_towns: list[str]
    proposed_sites: list[str] | None = None
    covered_before: int | None = None
    covered_after: int | None = None
    coverage_pct_before: float | None = None
    coverage_pct_after: float | None = None
    k: int | None = None
