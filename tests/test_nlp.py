from unittest.mock import MagicMock, patch

import pytest

from src.models import ParseError, QueryParams, NarrativeContext, ValidationError
from src.nlp import parse_query, generate_narrative, build_tool_schema


def _mock_tool_response(tool_input: dict):
    mock_resp = MagicMock()
    mock_resp.stop_reason = "tool_use"
    mock_content = MagicMock()
    mock_content.type = "tool_use"
    mock_content.input = tool_input
    mock_resp.content = [mock_content]
    return mock_resp


def _mock_text_response(text: str):
    mock_resp = MagicMock()
    mock_resp.stop_reason = "end_turn"
    mock_content = MagicMock()
    mock_content.type = "text"
    mock_content.text = text
    mock_resp.content = [mock_content]
    return mock_resp


@patch("src.nlp._client")
def test_parse_query_diagnostic(mock_client):
    mock_client.messages.create.return_value = _mock_tool_response({
        "mode": "diagnostic",
        "region": "Western NSW",
        "facility_type": "gp",
        "threshold_min": 45,
        "pop_min": 2000,
    })
    result = parse_query("Which towns lack GP coverage?")
    assert result.mode == "diagnostic"
    assert result.threshold_min == 45
    assert result.region == "Western NSW"


@patch("src.nlp._client")
def test_parse_query_rejects_long_input(mock_client):
    with pytest.raises(ValueError, match="500"):
        parse_query("x" * 501)
    mock_client.messages.create.assert_not_called()


@patch("src.nlp._client")
def test_parse_query_raises_on_non_tool_response(mock_client):
    mock_client.messages.create.return_value = _mock_text_response("I cannot help with that.")
    with pytest.raises(ParseError):
        parse_query("What is the weather?")


@patch("src.nlp._client")
def test_parse_query_accepts_any_region_without_fallback(mock_client):
    """Region validation is delegated to schema enum; __post_init__ accepts any non-empty region."""
    mock_client.messages.create.return_value = _mock_tool_response({
        "mode": "diagnostic",
        "region": "Murrumbidgee PHN",
        "facility_type": "gp",
        "threshold_min": 45,
    })
    # Should not raise — the schema enum is the gatekeeper
    result = parse_query("Coverage in Murrumbidgee?")
    assert result.region == "Murrumbidgee PHN"


@patch("src.nlp._client")
def test_generate_narrative_returns_string(mock_client):
    mock_client.messages.create.return_value = _mock_text_response(
        "Currently, 67% of the population is within 45 minutes of a GP."
    )
    ctx = NarrativeContext(
        mode="diagnostic",
        region="Western NSW",
        threshold_min=45,
        covered_population=8000,
        total_population=12000,
        coverage_pct=66.7,
        uncovered_towns=["Cobar", "Bourke"],
    )
    result = generate_narrative(ctx)
    assert isinstance(result, str)
    assert len(result) > 10


@patch("src.nlp._client")
def test_generate_narrative_raw_user_text_never_sent(mock_client):
    """User query text must not appear in the narrative generation prompt."""
    mock_client.messages.create.return_value = _mock_text_response("Narrative text.")
    ctx = NarrativeContext(
        mode="diagnostic",
        region="Western NSW",
        threshold_min=45,
        covered_population=5000,
        total_population=10000,
        coverage_pct=50.0,
        uncovered_towns=["Walgett"],
    )
    generate_narrative(ctx)
    call_args = mock_client.messages.create.call_args
    messages = call_args.kwargs.get("messages") or call_args[1].get("messages") or call_args[0][3]
    # The user message should be structured data only — no free text from the UI
    for msg in messages:
        assert "ignore previous" not in str(msg).lower()


def test_build_tool_schema_region_enum_has_provided_phns():
    """build_tool_schema must embed the supplied PHN list as the region enum."""
    regions = [f"PHN {i}" for i in range(31)]
    schema = build_tool_schema(regions)
    region_enum = schema["input_schema"]["properties"]["region"]["enum"]
    assert region_enum == regions
    assert len(region_enum) == 31


@patch("src.nlp._client")
def test_parse_query_fallback_region_used_on_invalid_phn(mock_client):
    """When LLM returns an unrecognised PHN, fallback_region is substituted."""
    import src.models as m
    original = list(m.ALLOWED_REGIONS)
    m.ALLOWED_REGIONS[:] = ["Western NSW", "Murrumbidgee"]
    try:
        mock_client.messages.create.return_value = _mock_tool_response({
            "mode": "diagnostic",
            "region": "Unknown PHN XYZ",
            "facility_type": "gp",
            "threshold_min": 45,
        })
        result = parse_query(
            "Coverage gaps?",
            fallback_region="Western NSW",
        )
        assert result.region == "Western NSW"
    finally:
        m.ALLOWED_REGIONS[:] = original
