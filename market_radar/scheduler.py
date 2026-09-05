import time
from datetime import datetime
from typing import Optional
from zoneinfo import ZoneInfo

from .outcomes import update_forward_outcomes
from .pipeline import run_scan
from .portfolio_tracker import refresh_prices

NEW_YORK = ZoneInfo("America/New_York")


def scheduler_tick(provider, repository, universe, now: Optional[datetime] = None):
    current = now or datetime.now(NEW_YORK)
    if provider.name != "demo" and repository.list_positions():
        try:
            refresh_prices(provider, repository, repository.list_positions(), current)
        except Exception as exc:
            print(f"Portfolio refresh unavailable: {type(exc).__name__}", flush=True)
    session = provider.latest_completed_session(current)
    if repository.scheduled_scan_exists(session):
        update_forward_outcomes(provider, repository, session)
        return None
    scan_universe = universe() if callable(universe) else universe
    result = run_scan(provider, scan_universe, session, scan_type="scheduled")
    scan_id = repository.save_scan(result)
    saved = repository.get_scan(scan_id)
    update_forward_outcomes(provider, repository, session)
    return saved


def run_scheduler(provider, repository, universe, interval_seconds: int = 900) -> None:
    while True:
        try:
            scheduler_tick(provider, repository, universe)
        except Exception as exc:
            print(f"Scheduler warning: {type(exc).__name__}: {exc}", flush=True)
        time.sleep(interval_seconds)
