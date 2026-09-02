from typing import Optional

from .models import ScanResult, SymbolSignal, TradeIdea

QUADRANT_EXPLANATIONS = {
    "Contrarian Bid": "Price has lagged, but options activity leans bullish. Watch for a confirmed reversal.",
    "Fear": "Price weakness and bearish options activity agree. Watch for downside continuation.",
    "Chase": "Relative price strength and bullish options activity agree. Watch for momentum continuation.",
    "Hedged Rally": "Price is strong while options activity leans bearish. Treat as watch-only because puts may be hedges.",
}

SECTOR_NAMES = {
    "XLC": "Communication Services",
    "XLY": "Consumer Discretionary",
    "XLP": "Consumer Staples",
    "XLE": "Energy",
    "XLF": "Financials",
    "XLV": "Health Care",
    "XLI": "Industrials",
    "XLB": "Materials",
    "XLRE": "Real Estate",
    "XLK": "Technology",
    "XLU": "Utilities",
}


def evidence_label(score: float) -> str:
    if score >= 85:
        return "Very strong evidence"
    if score >= 75:
        return "Strong evidence"
    return "Qualified evidence"


def recommendation_reason(signal: SymbolSignal, idea: Optional[TradeIdea]) -> str:
    price = abs(signal.price_axis)
    options = abs(signal.options_axis or 0)
    volume = (
        f"elevated volume ({signal.volume_ratio:.2f}× normal)"
        if signal.volume_ratio >= 1.1
        else f"ordinary volume ({signal.volume_ratio:.2f}× normal)"
    )

    if signal.quadrant == "Contrarian Bid":
        evidence = (
            f"Bullish options pressure ({options:.0f}/100) is moving against pronounced relative price weakness "
            f"({price:.0f}/100), with {volume}."
        )
    elif signal.quadrant == "Fear":
        evidence = (
            f"Bearish options pressure ({options:.0f}/100) confirms pronounced relative price weakness "
            f"({price:.0f}/100), with {volume}."
        )
    elif signal.quadrant == "Chase":
        evidence = (
            f"Bullish options pressure ({options:.0f}/100) confirms strong relative price performance "
            f"({price:.0f}/100), with {volume}."
        )
    else:
        evidence = (
            f"Bearish options pressure ({options:.0f}/100) conflicts with relative price strength "
            f"({price:.0f}/100), which may be hedging rather than a directional signal."
        )

    if idea is None:
        return evidence
    action = "above" if idea.direction == "long" else "below"
    return f"{evidence} The {idea.direction} idea activates only {action} ${idea.trigger:,.2f}."


def evidence_components(signal: SymbolSignal) -> list[dict[str, object]]:
    values = [
        ("Options agreement", "How one-sided the included option premium is", abs(signal.options_axis or 0), 0.35),
        (
            "Options coverage",
            "Whether enough valid contracts support the reading",
            min(signal.valid_contracts / 20, 1) * 100,
            0.20,
        ),
        ("Price displacement", "How unusual relative price movement is", abs(signal.price_axis), 0.20),
        ("Volume confirmation", "Where today's volume ranks in the universe", signal.volume_percentile, 0.15),
        ("Trend confirmation", "Whether the trend fits this setup type", signal.trend_confirmation, 0.10),
    ]
    return [
        {
            "Evidence": label,
            "What it means": explanation,
            "Reading": round(value, 1),
            "Weight": f"{weight:.0%}",
            "Score points": round(value * weight, 1),
        }
        for label, explanation, value, weight in values
    ]


def executive_brief(scan: ScanResult) -> dict[str, object]:
    macro = scan.market_regime.get("global_macro", {})
    market_label = scan.market_regime.get("label", "Unknown market regime")
    macro_tone = macro.get("tone", "Mixed")
    if market_label == "Bullish trend" and macro_tone == "Constructive":
        posture = "Constructive, with momentum leadership"
    elif market_label == "Bearish trend" or macro_tone == "Cautious":
        posture = "Defensive—prioritize confirmation and risk control"
    else:
        posture = "Selective—focus on the clearest confirmations"

    ideas = sorted(scan.ideas, key=lambda idea: idea.evidence_score, reverse=True)
    quadrant_counts: dict[str, int] = {}
    for idea in ideas:
        quadrant_counts[idea.quadrant] = quadrant_counts.get(idea.quadrant, 0) + 1
    dominant = max(quadrant_counts, key=quadrant_counts.get) if quadrant_counts else "No qualifying setup"
    high_evidence = sum(idea.evidence_score >= 80 for idea in ideas)

    takeaways = [
        f"SPY is in a {market_label.lower()} and the cross-asset backdrop is {macro_tone.lower()}.",
        f"{len(ideas)} conditional ideas qualified; {high_evidence} score at least 80/100.",
    ]
    if ideas:
        takeaways.append(
            f"{dominant} is the most common qualified setup; the top-ranked idea is {ideas[0].ticker} "
            f"at {ideas[0].evidence_score:.1f}/100."
        )
    if macro.get("takeaways"):
        takeaways.append(macro["takeaways"][0])
    latest_sector_returns = {ticker: values[-1] for ticker, values in scan.sector_returns.items() if values}
    if latest_sector_returns:
        leader = max(latest_sector_returns, key=latest_sector_returns.get)
        laggard = min(latest_sector_returns, key=latest_sector_returns.get)
        takeaways.append(
            f"Latest-week sector leadership favors {SECTOR_NAMES.get(leader, leader)} "
            f"({latest_sector_returns[leader]:+.1%} vs SPY); {SECTOR_NAMES.get(laggard, laggard)} "
            f"lags ({latest_sector_returns[laggard]:+.1%})."
        )

    risks = []
    if scan.option_feed == "indicative":
        risks.append("Options pressure uses delayed indicative snapshots, not complete institutional order flow.")
    if market_label == "Mixed regime":
        risks.append("The broad-market trend is mixed, so isolated stock signals deserve extra confirmation.")
    if macro_tone == "Cautious":
        risks.append("Cross-asset markets are defensive; long setups face a less supportive backdrop.")
    if scan.warnings:
        risks.append(f"This scan completed with {len(scan.warnings)} partial-data warning(s).")
    if not risks:
        risks.append("Every idea is conditional and expires if its trigger is not reached within five sessions.")

    return {
        "posture": posture,
        "market_label": market_label,
        "macro_tone": macro_tone,
        "risk_score": macro.get("risk_score"),
        "idea_count": len(ideas),
        "high_evidence_count": high_evidence,
        "dominant_setup": dominant,
        "takeaways": takeaways,
        "risks": risks,
    }
