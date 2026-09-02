import argparse
import os
import subprocess
import sys
from datetime import date, datetime
from pathlib import Path
from zoneinfo import ZoneInfo

from .pipeline import run_scan
from .providers import AlpacaProvider, CachedProvider, DemoProvider
from .repository import Repository
from .scheduler import run_scheduler
from .universe import load_universe

PROJECT_ROOT = Path(__file__).parents[1]
DEFAULT_DATABASE = PROJECT_ROOT / "data" / "market_radar.db"
DEFAULT_UNIVERSE = PROJECT_ROOT / "data" / "universe.csv"


def _load_env(path: Path) -> None:
    if not path.exists():
        return
    for line in path.read_text(encoding="utf-8").splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("#") or "=" not in stripped:
            continue
        key, value = stripped.split("=", 1)
        os.environ.setdefault(key.strip(), value.strip().strip('"').strip("'"))


def _common_arguments(parser):
    parser.add_argument("--database", default=str(DEFAULT_DATABASE))
    parser.add_argument("--universe", default=str(DEFAULT_UNIVERSE))


def build_parser():
    parser = argparse.ArgumentParser(prog="market-radar", description="Transparent after-close market evidence radar")
    subparsers = parser.add_subparsers(dest="command", required=True)
    demo = subparsers.add_parser("demo", help="Run a deterministic fixture-backed scan")
    _common_arguments(demo)
    demo.add_argument("--as-of", help="Completed session in YYYY-MM-DD format")
    scan = subparsers.add_parser("scan", help="Run a live Alpaca scan")
    _common_arguments(scan)
    scan.add_argument("--as-of", help="Completed session in YYYY-MM-DD format")
    serve = subparsers.add_parser("serve", help="Launch the Streamlit dashboard")
    _common_arguments(serve)
    serve.add_argument("--port", type=int, default=int(os.getenv("MARKET_RADAR_PORT", "8502")))
    serve.add_argument("--address", default=os.getenv("MARKET_RADAR_ADDRESS", "127.0.0.1"))
    scheduler = subparsers.add_parser("scheduler", help="Run the after-close scheduler")
    _common_arguments(scheduler)
    scheduler.add_argument("--interval", type=int, default=900)
    bootstrap = subparsers.add_parser("bootstrap", help="Create presentation data only when the database is empty")
    _common_arguments(bootstrap)
    bootstrap.add_argument("--as-of", help="Completed session in YYYY-MM-DD format")
    return parser


def _live_provider(repository=None):
    _load_env(PROJECT_ROOT / ".env")
    provider = AlpacaProvider(os.getenv("ALPACA_API_KEY_ID"), os.getenv("ALPACA_API_SECRET_KEY"))
    return CachedProvider(provider, repository) if repository else provider


def _context(args):
    repository = Repository(args.database)
    universe = load_universe(args.universe, repository.list_watchlist())
    return repository, universe


def main(argv=None):
    _load_env(PROJECT_ROOT / ".env")
    args = build_parser().parse_args(argv)
    repository, universe = _context(args)
    if args.command in {"demo", "scan"}:
        provider = DemoProvider() if args.command == "demo" else _live_provider(repository)
        as_of = (
            date.fromisoformat(args.as_of)
            if args.as_of
            else provider.latest_completed_session(datetime.now(ZoneInfo("America/New_York")))
        )
        result = run_scan(provider, universe, as_of, scan_type="manual")
        scan_id = repository.save_scan(result)
        print(
            f"Saved {args.command} scan {scan_id} for {as_of.isoformat()}: "
            f"{len(result.signals)} symbols, {len(result.ideas)} trade ideas, status={result.status}"
        )
        return 0
    if args.command == "scheduler":
        run_scheduler(_live_provider(repository), repository, universe, interval_seconds=args.interval)
        return 0
    if args.command == "bootstrap":
        existing = repository.latest_scan()
        if existing:
            print(f"Presentation data ready: scan {existing.id} for {existing.as_of.isoformat()}")
            return 0
        provider = DemoProvider()
        as_of = (
            date.fromisoformat(args.as_of)
            if args.as_of
            else provider.latest_completed_session(datetime.now(ZoneInfo("America/New_York")))
        )
        scan_id = repository.save_scan(run_scan(provider, universe, as_of, scan_type="manual"))
        print(f"Created presentation demo scan {scan_id} for {as_of.isoformat()}")
        return 0
    if args.command == "serve":
        env = os.environ.copy()
        env["MARKET_RADAR_DATABASE"] = str(Path(args.database).resolve())
        env["MARKET_RADAR_UNIVERSE"] = str(Path(args.universe).resolve())
        return subprocess.call(
            [
                sys.executable,
                "-m",
                "streamlit",
                "run",
                str(PROJECT_ROOT / "market_radar" / "dashboard.py"),
                "--server.port",
                str(args.port),
                "--server.address",
                args.address,
                "--server.headless",
                "true",
            ],
            env=env,
            cwd=PROJECT_ROOT,
        )
    return 2
