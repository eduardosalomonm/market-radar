import csv
import io
import json
from collections.abc import Iterable

from .models import IdeaOutcome, TradeIdea


def export_ideas_csv(ideas: Iterable[TradeIdea]) -> str:
    output = io.StringIO()
    fields = [
        "ticker",
        "quadrant",
        "direction",
        "evidence_score",
        "scan_date",
        "trigger",
        "stop",
        "target_1r",
        "target_2r",
        "expires_after_sessions",
        "max_holding_sessions",
    ]
    writer = csv.DictWriter(output, fieldnames=fields, extrasaction="ignore", lineterminator="\n")
    writer.writeheader()
    for idea in ideas:
        writer.writerow(idea.to_dict())
    return output.getvalue()


def export_outcomes_json(outcomes: Iterable[IdeaOutcome]) -> str:
    return json.dumps([outcome.to_dict() for outcome in outcomes], indent=2, sort_keys=True)
