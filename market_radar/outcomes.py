from datetime import date, timedelta

from .analytics import evaluate_idea


def update_forward_outcomes(provider, repository, as_of: date) -> int:
    ideas = repository.list_scheduled_ideas()
    if not ideas:
        return 0
    earliest = min(idea.scan_date for idea in ideas)
    symbols = sorted({idea.ticker for idea in ideas})
    bars_by_symbol = provider.get_daily_bars(symbols, earliest + timedelta(days=1), as_of)
    updated = 0
    for idea in ideas:
        outcome = evaluate_idea(idea, bars_by_symbol.get(idea.ticker, []))
        repository.save_outcome(outcome)
        updated += 1
    return updated
