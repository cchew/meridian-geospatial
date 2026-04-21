from __future__ import annotations
import os
from dataclasses import asdict

import anthropic
from dotenv import load_dotenv

from src.models import NarrativeContext, ParseError, QueryParams, ValidationError

load_dotenv()

_client = anthropic.Anthropic(api_key=os.environ.get("ANTHROPIC_API_KEY"))

MODEL = "claude-sonnet-4-6"
MAX_INPUT_CHARS = 500

_PARSE_SYSTEM = (
    "You are a query parser for a health facility planning tool covering "
    "Australian Primary Health Networks. Extract structured parameters from "
    "the user's question using the extract_query_params tool. "
    "Return only the tool call — no prose, no explanations."
)

_PARSE_TOOL = {
    "name": "extract_query_params",
    "description": "Extract structured health planning query parameters from natural language.",
    "input_schema": {
        "type": "object",
        "properties": {
            "mode": {
                "type": "string",
                "enum": ["diagnostic", "prescriptive"],
                "description": "diagnostic=coverage gaps, prescriptive=facility placement",
            },
            "region": {
                "type": "string",
                "description": "PHN region name, e.g. 'Western NSW'",
            },
            "facility_type": {
                "type": "string",
                "enum": ["gp"],
                "description": "Type of health facility",
            },
            "threshold_min": {
                "type": "integer",
                "description": "Travel time threshold in minutes (10-120)",
            },
            "k": {
                "type": "integer",
                "description": "Number of new facilities to place (prescriptive mode only, 1-10)",
            },
            "pop_min": {
                "type": "integer",
                "description": "Minimum population for a locality to be included (0-50000)",
            },
        },
        "required": ["mode", "region", "facility_type", "threshold_min"],
    },
}

_NARRATIVE_SYSTEM = (
    "You are a health policy analyst writing briefing notes for PHN executives "
    "and DHDA (Department of Health, Disability and Ageing) officials. "
    "Write in clear, precise language. Be specific about town names and numbers.\n\n"
    "For DIAGNOSTIC mode:\n"
    "- Write exactly 2 sentences of plain-English overview summarising the coverage situation "
    "(e.g. 'Towns X, Y and Z are more than 45 minutes from the nearest GP.').\n"
    "- Then use bullet points (starting with •) to list key findings — one clear point per bullet.\n\n"
    "For PRESCRIPTIVE mode:\n"
    "- Use bullet points (starting with •) throughout. No prose paragraphs.\n"
    "- Cover: proposed locations and why, before/after coverage improvement, and next steps.\n\n"
    "Reference the November 2025 Bulk Billing Practice Incentive Program (BBPIP) "
    "where relevant to new facility viability. Keep each bullet to one clear point.\n\n"
    "Do not include any 'Prepared by', 'Classification', or similar footer lines."
)


def parse_query(user_input: str) -> QueryParams:
    """Parse natural language query into QueryParams using Claude tool use."""
    if len(user_input) > MAX_INPUT_CHARS:
        raise ValueError(f"Input exceeds {MAX_INPUT_CHARS} characters")

    response = _client.messages.create(
        model=MODEL,
        max_tokens=512,
        system=_PARSE_SYSTEM,
        tools=[_PARSE_TOOL],
        tool_choice={"type": "any"},
        messages=[{"role": "user", "content": user_input}],
    )

    tool_use = next(
        (block for block in response.content if block.type == "tool_use"), None
    )
    if tool_use is None:
        raise ParseError(
            f"Expected tool call from Claude, got stop_reason={response.stop_reason!r}"
        )

    raw = tool_use.input
    # Raises ValidationError if region/bounds invalid
    return QueryParams(
        mode=raw["mode"],
        region=raw.get("region", "Western NSW"),
        facility_type=raw.get("facility_type", "gp"),
        threshold_min=int(raw["threshold_min"]),
        k=int(raw["k"]) if raw.get("k") is not None else None,
        pop_min=int(raw["pop_min"]) if raw.get("pop_min") is not None else None,
    )


def generate_narrative(ctx: NarrativeContext) -> str:
    """Generate briefing-quality narrative from structured results."""
    # Build structured prompt — raw user text never reaches this function
    lines = [
        f"Region: {ctx.region}",
        f"Mode: {ctx.mode}",
        f"Travel time threshold: {ctx.threshold_min} minutes",
        f"Total population analysed: {ctx.total_population:,}",
        f"Population within threshold of existing GP: {ctx.covered_population:,} ({ctx.coverage_pct:.1f}%)",
        f"Towns currently lacking coverage: {', '.join(ctx.uncovered_towns) if ctx.uncovered_towns else 'None'}",
    ]
    if ctx.mode == "prescriptive" and ctx.proposed_sites:
        lines += [
            f"Proposed new clinic locations: {', '.join(ctx.proposed_sites)}",
            f"Coverage before new clinics: {ctx.covered_before:,} ({ctx.coverage_pct_before:.1f}%)",
            f"Coverage after new clinics: {ctx.covered_after:,} ({ctx.coverage_pct_after:.1f}%)",
            f"Number of new facilities: {ctx.k}",
        ]

    structured_input = "\n".join(lines)

    response = _client.messages.create(
        model=MODEL,
        max_tokens=1024,
        system=_NARRATIVE_SYSTEM,
        messages=[{
            "role": "user",
            "content": (
                f"Write a briefing note in {ctx.mode.upper()} mode format based on the following "
                f"health coverage analysis results:\n\n"
                + structured_input
            ),
        }],
    )

    text_block = next(
        (block for block in response.content if block.type == "text"), None
    )
    if text_block is None:
        raise ParseError("No text response from narrative generation")
    return text_block.text
