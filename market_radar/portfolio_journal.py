"""Private decision journal: freeze why and when, then compare later observations without rewriting history."""

import json
import re
import uuid
from datetime import date, timedelta

ACTIONS = ("Hold", "Add", "Trim", "Sell", "Watch")
VERDICTS = ("Still valid", "Changed my mind", "Too early to tell")
MAX_ENTRIES = 200
MAX_TEXT = 500


def _text(value, label, required=True):
    value = str(value or "").strip()[:MAX_TEXT]
    if required and not value:
        raise ValueError(f"{label} is required")
    return value


def _number(value):
    return float(value) if isinstance(value, (int, float)) and not isinstance(value, bool) else None


def validate_entry(raw):
    """Normalize one entry from storage or a backup; raises ValueError on anything malformed."""
    try:
        ticker = str(raw["ticker"]).strip().upper()
        if not re.fullmatch(r"[A-Z0-9][A-Z0-9.\-]{0,14}", ticker):
            raise ValueError("Invalid ticker in decision journal")
        if raw["action"] not in ACTIONS:
            raise ValueError("Unknown decision action")
        decided, review = date.fromisoformat(raw["decided_on"]), date.fromisoformat(raw["review_on"])
        if review < decided:
            raise ValueError("Review date cannot precede the decision")
        reviews = []
        for item in raw.get("reviews", [])[:20]:
            if item["verdict"] not in VERDICTS:
                raise ValueError("Unknown review verdict")
            reviews.append({"on": date.fromisoformat(item["on"]).isoformat(), "verdict": item["verdict"],
                            "note": _text(item.get("note"), "Note", False)})
        return {"id": re.sub(r"[^a-f0-9]", "", str(raw["id"]))[:32] or uuid.uuid4().hex[:12],
                "ticker": ticker, "action": raw["action"],
                "reason": _text(raw["reason"], "Reason"), "reconsider_if": _text(raw.get("reconsider_if"), "Trigger", False),
                "decided_on": decided.isoformat(), "review_on": review.isoformat(),
                "price": _number(raw.get("price")), "price_as_of": raw.get("price_as_of") if raw.get("price_as_of") else None,
                "currency": str(raw.get("currency") or "")[:3], "weight": _number(raw.get("weight")),
                "reviews": reviews}
    except (KeyError, TypeError, AttributeError) as exc:
        raise ValueError("Invalid decision journal entry") from exc


def load_journal(raw):
    """Stored settings are trusted less than code: skip damaged entries instead of failing the page."""
    try:
        items = json.loads(raw or "[]")
    except (TypeError, json.JSONDecodeError):
        return []
    entries = []
    for item in items if isinstance(items, list) else []:
        try:
            entries.append(validate_entry(item))
        except ValueError:
            continue
    return entries[-MAX_ENTRIES:]


def dump_journal(entries):
    return json.dumps(entries[-MAX_ENTRIES:], allow_nan=False)


def import_journal(raw):
    """Optional `journal` key of a portfolio backup; validated in full before any write."""
    data = json.loads(raw)
    items = data.get("journal", []) if isinstance(data, dict) else []
    if not isinstance(items, list) or len(items) > MAX_ENTRIES:
        raise ValueError(f"A backup supports up to {MAX_ENTRIES} journal entries")
    return [validate_entry(item) for item in items]


def merge_journal(existing, imported):
    known = {e["id"] for e in existing}
    return (existing + [e for e in imported if e["id"] not in known])[-MAX_ENTRIES:]


def record_decision(report, ticker, action, reason, reconsider_if, review_on, today):
    row = next((r for r in report["rows"] if r["ticker"] == ticker), None)
    if row is None:
        raise ValueError("Choose a holding in this portfolio")
    if review_on <= today or review_on > today + timedelta(days=730):
        raise ValueError("Pick a review date within the next two years")
    return validate_entry({"id": uuid.uuid4().hex[:12], "ticker": ticker, "action": action, "reason": reason,
                           "reconsider_if": reconsider_if, "decided_on": today.isoformat(), "review_on": review_on.isoformat(),
                           "price": row["price"], "price_as_of": row["as_of"], "currency": row["currency"],
                           "weight": row["weight"] if report["complete"] else None})


def add_review(entry, verdict, note, today):
    """Append-only: the original reason, snapshot and date are never edited."""
    if verdict not in VERDICTS:
        raise ValueError("Unknown review verdict")
    return dict(entry, reviews=entry["reviews"] + [{"on": today.isoformat(), "verdict": verdict, "note": _text(note, "Note", False)}])


def review_journal(entries, report, today):
    """Due decisions first. Price change only when currency matches and the current price is newer."""
    rows = {r["ticker"]: r for r in report["rows"]}
    result = []
    for entry in entries:
        row = rows.get(entry["ticker"])
        last_review = date.fromisoformat(entry["reviews"][-1]["on"]) if entry["reviews"] else None
        review_on = date.fromisoformat(entry["review_on"])
        due = review_on <= today and (last_review is None or last_review < review_on)
        change = None
        if (row and entry["price"] and row["price"] is not None and row["currency"] == entry["currency"]
                and row["as_of"] and entry["price_as_of"] and row["as_of"] > entry["price_as_of"]):
            change = row["price"] / entry["price"] - 1
        result.append(dict(entry, due=due, days=(review_on - today).days, held=row is not None,
                           price_now=row["price"] if row else None, price_now_as_of=row["as_of"] if row else None,
                           price_change=change, weight_now=row["weight"] if row and report["complete"] else None))
    return sorted(result, key=lambda e: (not e["due"], e["review_on"]))
