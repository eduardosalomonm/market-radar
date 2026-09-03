from collections.abc import Iterable
from typing import Optional

from .models import PortfolioPosition, ScanResult


def _score(value: Optional[float]) -> Optional[float]:
    return round(value, 1) if value is not None else None


def _sector_leader(scan: ScanResult) -> Optional[str]:
    latest = {ticker: values[-1] for ticker, values in scan.sector_returns.items() if values}
    return max(latest, key=latest.get) if latest else None


def build_daily_intelligence(
    current: ScanResult,
    previous: Optional[ScanResult],
    watchlist: Iterable[str],
    positions: Iterable[PortfolioPosition] = (),
) -> dict[str, object]:
    current_signals = {signal.ticker: signal for signal in current.signals}
    previous_signals = {signal.ticker: signal for signal in previous.signals} if previous else {}
    current_ideas = {idea.ticker: idea for idea in current.ideas}
    previous_ideas = {idea.ticker: idea for idea in previous.ideas} if previous else {}

    saved_positions = list(positions)
    followed_tickers = {item.upper() for item in watchlist} | {item.ticker.upper() for item in saved_positions}
    pulse = []
    for ticker in sorted(followed_tickers):
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

    position_rows = []
    sector_values: dict[str, float] = {}
    portfolio_value = 0.0
    comparable_value = 0.0
    daily_pnl = 0.0
    cost_basis = 0.0
    cost_basis_covered = 0.0
    valued_positions = 0
    for position in saved_positions:
        signal = current_signals.get(position.ticker)
        prior = previous_signals.get(position.ticker)
        market_value = signal.close * position.shares if signal else None
        session_pnl = (
            (signal.close - prior.close) * position.shares
            if signal and prior and prior.close
            else None
        )
        unrealized = (
            (signal.close - position.average_cost) * position.shares
            if signal and position.average_cost is not None
            else None
        )
        if market_value is not None:
            valued_positions += 1
            portfolio_value += market_value
            sector_values[position.sector] = sector_values.get(position.sector, 0.0) + market_value
        if session_pnl is not None and prior is not None:
            daily_pnl += session_pnl
            comparable_value += prior.close * position.shares
        if position.average_cost is not None and market_value is not None:
            position_cost = position.average_cost * position.shares
            cost_basis += position_cost
            cost_basis_covered += market_value or 0.0
        position_rows.append(
            {
                "ticker": position.ticker,
                "name": position.name,
                "shares": position.shares,
                "average_cost": position.average_cost,
                "current_price": signal.close if signal else None,
                "market_value": market_value,
                "session_pnl": session_pnl,
                "session_return": signal.close / prior.close - 1 if signal and prior and prior.close else None,
                "unrealized_pnl": unrealized,
                "quadrant": signal.quadrant if signal else None,
                "evidence": _score(signal.evidence_score) if signal else None,
                "thesis": position.thesis,
            }
        )

    sector_exposure = [
        {
            "sector": sector,
            "market_value": value,
            "weight": value / portfolio_value if portfolio_value else 0.0,
        }
        for sector, value in sorted(sector_values.items(), key=lambda item: item[1], reverse=True)
    ]
    largest_position = max(position_rows, key=lambda row: row["market_value"] or 0, default=None)

    alerts = []
    new_idea_set = set(new_ideas)
    removed_idea_set = set(removed_ideas)
    quadrant_by_ticker = {item["ticker"]: item for item in quadrant_changes}
    score_by_ticker = {item["ticker"]: item for item in score_moves if abs(item["change"]) >= 10}
    for row in pulse:
        ticker = row["ticker"]
        reasons = []
        severity = "attention"
        if ticker in new_idea_set:
            reasons.append("new qualified setup")
            severity = "high"
        if ticker in removed_idea_set:
            reasons.append("no longer clears the evidence threshold")
            severity = "high"
        if ticker in quadrant_by_ticker:
            change = quadrant_by_ticker[ticker]
            reasons.append(f"setup changed from {change['from']} to {change['to']}")
            severity = "high"
        if ticker in score_by_ticker:
            reasons.append(f"evidence moved {score_by_ticker[ticker]['change']:+.1f} points")
        if row["price_change"] is not None and abs(row["price_change"]) >= 0.04:
            reasons.append(f"price moved {row['price_change']:+.1%} since the prior saved session")
            severity = "high"
        if reasons:
            alerts.append({"ticker": ticker, "name": row["name"], "severity": severity, "reason": "; ".join(reasons)})

    risk_score = current.market_regime.get("global_macro", {}).get("risk_score")
    macro_notes = []
    if sector_exposure:
        largest_sector = sector_exposure[0]
        macro_notes.append(
            f"{largest_sector['sector']} is the largest sector exposure at {largest_sector['weight']:.0%} of valued holdings."
        )
        if largest_sector["weight"] >= 0.5:
            macro_notes.append("Concentration is high: one sector represents at least half of the valued portfolio.")
    if risk_score is not None:
        tone = "supportive" if risk_score >= 65 else "defensive" if risk_score < 35 else "mixed"
        macro_notes.append(f"Cross-asset risk appetite is {tone} at {risk_score:.0f}/100.")

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
        "portfolio": {
            "positions": position_rows,
            "position_count": len(saved_positions),
            "market_value": portfolio_value if valued_positions else None,
            "daily_pnl": daily_pnl if comparable_value else None,
            "daily_return": daily_pnl / comparable_value if comparable_value else None,
            "cost_basis": cost_basis if cost_basis else None,
            "unrealized_pnl": cost_basis_covered - cost_basis if cost_basis else None,
            "largest_position": largest_position,
            "sector_exposure": sector_exposure,
            "macro_notes": macro_notes,
        },
        "alerts": alerts,
        "alert_policy": (
            "Only material followed-name changes are shown: a new/removed qualified setup, a setup change, "
            "an evidence move of at least 10 points, or a saved-session price move of at least 4%."
        ),
    }
