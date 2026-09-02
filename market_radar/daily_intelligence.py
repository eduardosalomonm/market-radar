from collections.abc import Iterable
from typing import Optional

from .models import ScanResult


def _score(value: Optional[float]) -> Optional[float]:
    return round(value, 1) if value is not None else None


def _sector_leader(scan: ScanResult) -> Optional[str]:
    latest = {ticker: values[-1] for ticker, values in scan.sector_returns.items() if values}
    return max(latest, key=latest.get) if latest else None


def build_daily_intelligence(
    current: ScanResult,
    previous: Optional[ScanResult],
    watchlist: Iterable[str],
) -> dict[str, object]:
    current_signals = {signal.ticker: signal for signal in current.signals}
    previous_signals = {signal.ticker: signal for signal in previous.signals} if previous else {}
    current_ideas = {idea.ticker: idea for idea in current.ideas}
    previous_ideas = {idea.ticker: idea for idea in previous.ideas} if previous else {}

    pulse = []
    for ticker in sorted({item.upper() for item in watchlist}):
        signal = current_signals.get(ticker)
        prior = previous_signals.get(ticker)
        if signal is None:
            pulse.append(
                {
                    "ticker": ticker,
                    "name": ticker,
                    "current_price": None,
                    "price_change": None,
                    "evidence": None,
                    "evidence_change": None,
                    "quadrant": None,
                    "status": "Awaiting next scan",
                }
            )
            continue

        if ticker in current_ideas:
            status = "Qualified idea"
        elif signal.quadrant == "Hedged Rally":
            status = "Watch-only"
        elif signal.options_axis is not None:
            status = "Signal only"
        else:
            status = "Price scan only"
        price_change = signal.close / prior.close - 1.0 if prior and prior.close else None
        evidence_change = (
            signal.evidence_score - prior.evidence_score
            if prior and signal.evidence_score is not None and prior.evidence_score is not None
            else None
        )
        pulse.append(
            {
                "ticker": ticker,
                "name": signal.name,
                "current_price": signal.close,
                "price_change": price_change,
                "evidence": _score(signal.evidence_score),
                "evidence_change": _score(evidence_change),
                "quadrant": signal.quadrant,
                "status": status,
            }
        )

    new_ideas = sorted(set(current_ideas) - set(previous_ideas)) if previous else []
    removed_ideas = sorted(set(previous_ideas) - set(current_ideas)) if previous else []
    quadrant_changes = []
    score_moves = []
    if previous:
        for ticker in sorted(set(current_signals) & set(previous_signals)):
            signal = current_signals[ticker]
            prior = previous_signals[ticker]
            if signal.quadrant and prior.quadrant and signal.quadrant != prior.quadrant:
                quadrant_changes.append({"ticker": ticker, "from": prior.quadrant, "to": signal.quadrant})
            if signal.evidence_score is not None and prior.evidence_score is not None:
                delta = signal.evidence_score - prior.evidence_score
                if abs(delta) >= 5:
                    score_moves.append(
                        {
                            "ticker": ticker,
                            "from": round(prior.evidence_score, 1),
                            "to": round(signal.evidence_score, 1),
                            "change": round(delta, 1),
                        }
                    )
        score_moves.sort(key=lambda item: abs(item["change"]), reverse=True)

    current_regime = current.market_regime.get("label", "Unknown")
    previous_regime = previous.market_regime.get("label", "Unknown") if previous else None
    regime_change = (
        f"{previous_regime} → {current_regime}"
        if previous and previous_regime != current_regime
        else f"Unchanged: {current_regime}"
    )
    current_sector_leader = _sector_leader(current)
    previous_sector_leader = _sector_leader(previous) if previous else None

    summary = []
    if previous is None:
        summary.append("No earlier completed session is available for comparison.")
    else:
        summary.append(f"{len(new_ideas)} new and {len(removed_ideas)} removed qualified idea(s).")
        summary.append(f"{len(quadrant_changes)} stock(s) changed price/options setup.")
        summary.append(regime_change)
        if current_sector_leader:
            if previous_sector_leader and previous_sector_leader != current_sector_leader:
                summary.append(f"Sector leadership changed from {previous_sector_leader} to {current_sector_leader}.")
            else:
                summary.append(f"Sector leadership remains {current_sector_leader}.")

    return {
        "current_as_of": current.as_of.isoformat(),
        "previous_as_of": previous.as_of.isoformat() if previous else None,
        "watchlist_pulse": pulse,
        "changes": {
            "new_ideas": new_ideas,
            "removed_ideas": removed_ideas,
            "quadrant_changes": quadrant_changes,
            "score_moves": score_moves,
            "market_regime": regime_change,
            "sector_leader": current_sector_leader,
            "previous_sector_leader": previous_sector_leader,
            "summary": summary,
        },
    }
