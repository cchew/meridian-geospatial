import pytest
from src.models import QueryParams, NarrativeContext, ValidationError


def test_query_params_valid_diagnostic():
    p = QueryParams(
        mode="diagnostic",
        region="Western NSW",
        facility_type="gp",
        threshold_min=45,
        k=None,
        pop_min=2000,
    )
    assert p.mode == "diagnostic"
    assert p.threshold_min == 45


def test_query_params_valid_prescriptive():
    p = QueryParams(
        mode="prescriptive",
        region="Western NSW",
        facility_type="gp",
        threshold_min=45,
        k=6,
        pop_min=1000,
    )
    assert p.k == 6


def test_query_params_rejects_threshold_out_of_bounds():
    with pytest.raises(ValidationError, match="threshold_min"):
        QueryParams(
            mode="diagnostic",
            region="Western NSW",
            facility_type="gp",
            threshold_min=5,
            k=None,
            pop_min=None,
        )


def test_query_params_rejects_k_out_of_bounds():
    with pytest.raises(ValidationError, match="k"):
        QueryParams(
            mode="prescriptive",
            region="Western NSW",
            facility_type="gp",
            threshold_min=45,
            k=15,
            pop_min=None,
        )


def test_query_params_rejects_pop_min_out_of_bounds():
    with pytest.raises(ValidationError, match="pop_min"):
        QueryParams(
            mode="diagnostic",
            region="Western NSW",
            facility_type="gp",
            threshold_min=45,
            k=None,
            pop_min=99999,
        )
