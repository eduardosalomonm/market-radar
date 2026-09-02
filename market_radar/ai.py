import json
import os
from typing import Optional

from .models import ScanResult

BRIEF_SCHEMA = {
    "type": "object",
    "properties": {
        "headline": {"type": "string"},
        "summary": {"type": "string"},
        "leaders": {"type": "array", "items": {"type": "string"}, "maxItems": 5},
        "risks": {"type": "array", "items": {"type": "string"}, "maxItems": 5},
    },
    "required": ["headline", "summary", "leaders", "risks"],
    "additionalProperties": False,
}


def _deterministic_brief(scan: ScanResult):
    ranked = sorted(
        (signal for signal in scan.signals if signal.evidence_score is not None),
        key=lambda signal: signal.evidence_score,
        reverse=True,
    )
    leaders = [f"{signal.ticker} · {signal.quadrant} · {signal.evidence_score:.0f}" for signal in ranked[:5]]
    risks = list(scan.warnings[:3])
    if scan.option_feed == "indicative":
        risks.append("Indicative options data is delayed and uses modified quotes; pressure is an approximation.")
    if not risks:
        risks.append("Evidence scores are rankings, not calibrated probabilities or financial advice.")
    return {
        "headline": f"{scan.market_regime.get('label', 'Market regime')} · {len(scan.ideas)} conditional ideas",
        "summary": (
            f"The {scan.as_of.isoformat()} scan ranked {len(ranked)} options-enriched names and produced "
            f"{len(scan.ideas)} evidence-qualified conditional swing plans."
        ),
        "leaders": leaders,
        "risks": risks,
        "source": "deterministic",
    }


def _evidence_payload(scan: ScanResult):
    return {
        "as_of": scan.as_of.isoformat(),
        "status": scan.status,
        "provider": scan.provider,
        "stock_feed": scan.stock_feed,
        "option_feed": scan.option_feed,
        "market_regime": scan.market_regime,
        "sector_returns": scan.sector_returns,
        "warnings": scan.warnings,
        "ranked_signals": [
            {
                "ticker": signal.ticker,
                "sector": signal.sector,
                "quadrant": signal.quadrant,
                "evidence_score": signal.evidence_score,
                "price_axis": signal.price_axis,
                "options_axis": signal.options_axis,
                "valid_contracts": signal.valid_contracts,
                "feed": signal.feed,
            }
            for signal in scan.signals
            if signal.evidence_score is not None
        ],
        "trade_ideas": [idea.to_dict() for idea in scan.ideas],
    }


def generate_daily_brief(
    scan: ScanResult,
    api_key: Optional[str] = None,
    model: Optional[str] = None,
    client=None,
):
    fallback = _deterministic_brief(scan)
    if client is None:
        key = api_key or os.getenv("OPENAI_API_KEY")
        if not key:
            return fallback
        try:
            from openai import OpenAI

            client = OpenAI(api_key=key)
        except Exception as exc:
            fallback["risks"].append(f"AI brief unavailable ({type(exc).__name__}); deterministic copy shown.")
            return fallback

    try:
        response = client.responses.create(
            model=model or os.getenv("OPENAI_MODEL", "gpt-5.4-mini"),
            instructions=(
                "Summarize only the supplied deterministic market evidence. Do not calculate new scores, change trade "
                "levels, add facts, promise returns, or describe the ranking as a probability. Keep the tone concise."
            ),
            input=json.dumps(_evidence_payload(scan), sort_keys=True),
            text={"format": {"type": "json_schema", "name": "daily_brief", "strict": True, "schema": BRIEF_SCHEMA}},
            tool_choice="none",
            store=False,
        )
        parsed = json.loads(response.output_text)
        if set(parsed) != {"headline", "summary", "leaders", "risks"}:
            raise ValueError("Unexpected brief keys")
        parsed["source"] = "openai"
        return parsed
    except Exception as exc:
        fallback["risks"].append(f"AI brief unavailable ({type(exc).__name__}); deterministic copy shown.")
        return fallback
