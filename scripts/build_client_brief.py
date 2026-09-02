import argparse
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from market_radar.catalysts import load_catalysts  # noqa: E402
from market_radar.client_report import build_client_brief_pdf  # noqa: E402
from market_radar.daily_intelligence import build_daily_intelligence  # noqa: E402
from market_radar.repository import Repository  # noqa: E402


def main() -> None:
    parser = argparse.ArgumentParser(description="Build a client brief from an immutable saved scan")
    parser.add_argument("--database", type=Path, default=Path("data/market_radar.db"))
    parser.add_argument("--catalysts", type=Path, default=Path("data/catalysts.json"))
    parser.add_argument("--scan-id", type=int)
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("output/pdf/market-radar-client-brief.pdf"),
    )
    args = parser.parse_args()

    repository = Repository(args.database)
    scan = repository.get_scan(args.scan_id) if args.scan_id else repository.latest_scan()
    if scan is None:
        raise SystemExit("No saved scan is available")
    previous = repository.previous_scan(scan.id)
    watchlist = [item.ticker for item in repository.list_watchlist()]
    intelligence = build_daily_intelligence(scan, previous, watchlist)
    catalysts = load_catalysts(
        args.catalysts,
        scan.as_of,
        days=35,
        tickers={item.ticker for item in scan.ideas} | set(watchlist),
    )
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_bytes(build_client_brief_pdf(scan, intelligence, catalysts))
    print(f"Saved client brief for scan {scan.id} to {args.output}")


if __name__ == "__main__":
    main()
