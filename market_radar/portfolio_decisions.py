"""Decision support from saved values, never trade execution or return forecasts."""

import math
from datetime import date


def review_priority(report, today, limit=.25, synthetic=False, due=()):
    if synthetic:
        return "Illustrative review", "Synthetic example: explore the mechanics, not a market recommendation."
    if not report["complete"]:
        return "Complete your valuation", "Some holdings have no value. Resolve missing prices before comparing portfolio decisions."
    # A due decision is date-driven, so stale prices must not hide it; the journal shows price dates itself.
    if due:
        return f"Revisit your {due[0]} decision", (f"{len(due)} saved decisions reached their review date. " if len(due) > 1 else
            "A saved decision reached its review date. ") + "Compare what you expected with what happened, below in Decision journal."
    dates = []
    for row in report["rows"]:
        try:
            dates.append(date.fromisoformat(row["as_of"]))
        except (TypeError, ValueError):
            return "Confirm your price dates", "Undated prices cannot support a current portfolio assessment."
    if any(d > today for d in dates):
        return "Check future-dated prices", "A saved price date is in the future. Correct it before reviewing current exposure."
    if dates and (today - min(dates)).days > 7:
        return "Refresh your prices first", f"The oldest holding value is {(today - min(dates)).days} calendar days old. Scenarios below use that saved snapshot."
    largest = max(report["rows"], key=lambda r: r["weight"], default=None)
    if largest and largest["weight"] > limit:
        return f"Review {largest['ticker']} concentration", f"{largest['weight']:.1%} of capital versus your {limit:.0%} review limit. Compare alternatives before changing positions."
    return "No position-limit breach", "This checks capital concentration only. It does not establish low risk or predict growth."


def contribution_scenario(report, amount, destination, limit=.25):
    if not math.isfinite(amount) or amount < 0 or amount > 1e9:
        raise ValueError("Contribution must be a finite, non-negative amount")
    if not report["complete"] or not report["total"] or report["total"] <= 0:
        raise ValueError("Complete positive valuation required")
    values = {r["ticker"]: r["value"] for r in report["rows"]}
    if destination != "Cash" and destination not in values:
        raise ValueError("Choose cash or an existing holding")
    if not 0 < limit < 1:
        raise ValueError("Limit must be between 0 and 100%")
    before = report["total"]
    # Holding: what it can receive before crossing the limit. Cash: what brings the largest back to it.
    if destination == "Cash":
        room = max(0, max(values.values()) / limit - before)
    else:
        room = max(0, (limit * before - values[destination]) / (1 - limit))
    after = before + amount
    new = dict(values)
    if destination != "Cash":
        new[destination] += amount
    rows = [{"Holding": ticker, "Before": value / before, "After": new[ticker] / after,
             "Change (pp)": (new[ticker] / after - value / before) * 100} for ticker, value in values.items()]
    return {"rows": rows, "total": after, "room": room,
            "largest_before": max(values.values()) / before, "largest_after": max(new.values()) / after,
            "breaches_before": sum(v / before > limit for v in values.values()),
            "breaches_after": sum(v / after > limit for v in new.values()),
            "cash_before": report["cash"] / before,
            "cash_after": (report["cash"] + (amount if destination == "Cash" else 0)) / after}
