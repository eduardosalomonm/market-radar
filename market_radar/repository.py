import json
import sqlite3
from datetime import date, datetime
from pathlib import Path
from typing import Optional

from .models import IdeaOutcome, ScanResult, SymbolSignal, TradeIdea, UniverseMember


class Repository:
    def __init__(self, path):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._initialize()

    def _connect(self):
        connection = sqlite3.connect(str(self.path))
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA foreign_keys = ON")
        return connection

    def _initialize(self) -> None:
        with self._connect() as db:
            db.executescript(
                """
                CREATE TABLE IF NOT EXISTS scans (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    as_of TEXT NOT NULL,
                    scan_type TEXT NOT NULL,
                    status TEXT NOT NULL,
                    provider TEXT NOT NULL,
                    stock_feed TEXT NOT NULL,
                    option_feed TEXT NOT NULL,
                    config_hash TEXT NOT NULL,
                    started_at TEXT NOT NULL,
                    completed_at TEXT NOT NULL,
                    warnings_json TEXT NOT NULL,
                    market_regime_json TEXT NOT NULL,
                    sector_returns_json TEXT NOT NULL
                );
                CREATE UNIQUE INDEX IF NOT EXISTS one_scheduled_scan_per_session
                    ON scans(as_of) WHERE scan_type = 'scheduled';
                CREATE TABLE IF NOT EXISTS signals (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    scan_id INTEGER NOT NULL REFERENCES scans(id) ON DELETE CASCADE,
                    ticker TEXT NOT NULL,
                    payload_json TEXT NOT NULL,
                    UNIQUE(scan_id, ticker)
                );
                CREATE TABLE IF NOT EXISTS ideas (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    scan_id INTEGER NOT NULL REFERENCES scans(id) ON DELETE CASCADE,
                    ticker TEXT NOT NULL,
                    payload_json TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS outcomes (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    idea_id INTEGER NOT NULL UNIQUE REFERENCES ideas(id) ON DELETE CASCADE,
                    payload_json TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS watchlist (
                    ticker TEXT PRIMARY KEY,
                    name TEXT NOT NULL,
                    sector TEXT NOT NULL,
                    sector_etf TEXT NOT NULL,
                    industry TEXT NOT NULL DEFAULT 'Unclassified'
                );
                CREATE TABLE IF NOT EXISTS raw_cache (
                    cache_key TEXT PRIMARY KEY,
                    payload_json TEXT NOT NULL,
                    fetched_at TEXT NOT NULL
                );
                """
            )
            columns = {row[1] for row in db.execute("PRAGMA table_info(watchlist)")}
            if "industry" not in columns:
                db.execute("ALTER TABLE watchlist ADD COLUMN industry TEXT NOT NULL DEFAULT 'Unclassified'")

    def scheduled_scan_exists(self, as_of: date) -> bool:
        with self._connect() as db:
            row = db.execute(
                "SELECT 1 FROM scans WHERE as_of = ? AND scan_type = 'scheduled' LIMIT 1", (as_of.isoformat(),)
            ).fetchone()
        return row is not None

    def save_scan(self, result: ScanResult) -> int:
        if result.scan_type == "scheduled":
            with self._connect() as db:
                existing = db.execute(
                    "SELECT id FROM scans WHERE as_of = ? AND scan_type = 'scheduled'", (result.as_of.isoformat(),)
                ).fetchone()
                if existing:
                    return int(existing["id"])

        with self._connect() as db:
            cursor = db.execute(
                """
                INSERT INTO scans (
                    as_of, scan_type, status, provider, stock_feed, option_feed, config_hash,
                    started_at, completed_at, warnings_json, market_regime_json, sector_returns_json
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    result.as_of.isoformat(),
                    result.scan_type,
                    result.status,
                    result.provider,
                    result.stock_feed,
                    result.option_feed,
                    result.config_hash,
                    result.started_at.isoformat(),
                    result.completed_at.isoformat(),
                    json.dumps(result.warnings, sort_keys=True),
                    json.dumps(result.market_regime, sort_keys=True),
                    json.dumps(result.sector_returns, sort_keys=True),
                ),
            )
            scan_id = int(cursor.lastrowid)
            db.executemany(
                "INSERT INTO signals (scan_id, ticker, payload_json) VALUES (?, ?, ?)",
                [(scan_id, signal.ticker, json.dumps(signal.to_dict(), sort_keys=True)) for signal in result.signals],
            )
            db.executemany(
                "INSERT INTO ideas (scan_id, ticker, payload_json) VALUES (?, ?, ?)",
                [(scan_id, idea.ticker, json.dumps(idea.to_dict(), sort_keys=True)) for idea in result.ideas],
            )
        return scan_id

    def get_scan(self, scan_id: int) -> ScanResult:
        with self._connect() as db:
            scan = db.execute("SELECT * FROM scans WHERE id = ?", (scan_id,)).fetchone()
            if scan is None:
                raise KeyError(f"Unknown scan id: {scan_id}")
            signal_rows = db.execute(
                "SELECT payload_json FROM signals WHERE scan_id = ? ORDER BY ticker", (scan_id,)
            ).fetchall()
            idea_rows = db.execute(
                "SELECT id, payload_json FROM ideas WHERE scan_id = ? ORDER BY id", (scan_id,)
            ).fetchall()

        signals = []
        for row in signal_rows:
            payload = json.loads(row["payload_json"])
            payload["as_of"] = date.fromisoformat(payload["as_of"])
            payload["latest_trade_at"] = (
                datetime.fromisoformat(payload["latest_trade_at"]) if payload.get("latest_trade_at") else None
            )
            signals.append(SymbolSignal(**payload))
        ideas = []
        for row in idea_rows:
            payload = json.loads(row["payload_json"])
            payload["scan_date"] = date.fromisoformat(payload["scan_date"])
            payload["id"] = int(row["id"])
            ideas.append(TradeIdea(**payload))

        return ScanResult(
            id=int(scan["id"]),
            as_of=date.fromisoformat(scan["as_of"]),
            scan_type=scan["scan_type"],
            status=scan["status"],
            provider=scan["provider"],
            stock_feed=scan["stock_feed"],
            option_feed=scan["option_feed"],
            config_hash=scan["config_hash"],
            started_at=datetime.fromisoformat(scan["started_at"]),
            completed_at=datetime.fromisoformat(scan["completed_at"]),
            signals=signals,
            ideas=ideas,
            warnings=json.loads(scan["warnings_json"]),
            market_regime=json.loads(scan["market_regime_json"]),
            sector_returns=json.loads(scan["sector_returns_json"]),
        )

    def list_scans(self, limit: int = 50):
        with self._connect() as db:
            rows = db.execute(
                "SELECT id, as_of, scan_type, status, provider, completed_at FROM scans ORDER BY id DESC LIMIT ?",
                (limit,),
            ).fetchall()
        return [dict(row) for row in rows]

    def latest_scan(self) -> Optional[ScanResult]:
        rows = self.list_scans(limit=1)
        return self.get_scan(rows[0]["id"]) if rows else None

    def previous_scan(self, scan_id: int) -> Optional[ScanResult]:
        with self._connect() as db:
            current = db.execute("SELECT as_of, provider FROM scans WHERE id = ?", (scan_id,)).fetchone()
            if current is None:
                raise KeyError(f"Unknown scan id: {scan_id}")
            previous = db.execute(
                """
                SELECT id FROM scans
                WHERE as_of < ? AND provider = ? AND status = 'complete'
                ORDER BY as_of DESC, id DESC
                LIMIT 1
                """,
                (current["as_of"], current["provider"]),
            ).fetchone()
        return self.get_scan(int(previous["id"])) if previous else None

    def upsert_watchlist(self, member: UniverseMember) -> None:
        with self._connect() as db:
            db.execute(
                """
                INSERT INTO watchlist (ticker, name, sector, sector_etf, industry) VALUES (?, ?, ?, ?, ?)
                ON CONFLICT(ticker) DO UPDATE SET
                    name=excluded.name,
                    sector=excluded.sector,
                    sector_etf=excluded.sector_etf,
                    industry=excluded.industry
                """,
                (member.ticker.upper(), member.name, member.sector, member.sector_etf, member.industry),
            )

    def remove_watchlist(self, ticker: str) -> None:
        with self._connect() as db:
            db.execute("DELETE FROM watchlist WHERE ticker = ?", (ticker.upper(),))

    def list_watchlist(self) -> list[UniverseMember]:
        with self._connect() as db:
            rows = db.execute("SELECT * FROM watchlist ORDER BY ticker").fetchall()
        return [
            UniverseMember(
                row["ticker"],
                row["name"],
                row["sector"],
                row["sector_etf"],
                True,
                row["industry"],
            )
            for row in rows
        ]

    def save_outcome(self, outcome: IdeaOutcome) -> None:
        if outcome.idea_id is None:
            raise ValueError("Outcome must reference a saved idea")
        with self._connect() as db:
            db.execute(
                """
                INSERT INTO outcomes (idea_id, payload_json, updated_at) VALUES (?, ?, ?)
                ON CONFLICT(idea_id) DO UPDATE SET payload_json=excluded.payload_json, updated_at=excluded.updated_at
                """,
                (outcome.idea_id, json.dumps(outcome.to_dict(), sort_keys=True), datetime.utcnow().isoformat()),
            )

    def list_outcomes(self) -> list[IdeaOutcome]:
        with self._connect() as db:
            rows = db.execute("SELECT idea_id, payload_json FROM outcomes ORDER BY id DESC").fetchall()
        outcomes = []
        for row in rows:
            payload = json.loads(row["payload_json"])
            payload["triggered_on"] = (
                date.fromisoformat(payload["triggered_on"]) if payload.get("triggered_on") else None
            )
            payload["closed_on"] = date.fromisoformat(payload["closed_on"]) if payload.get("closed_on") else None
            payload["idea_id"] = int(row["idea_id"])
            outcomes.append(IdeaOutcome(**payload))
        return outcomes

    def list_scheduled_ideas(self) -> list[TradeIdea]:
        with self._connect() as db:
            rows = db.execute(
                """
                SELECT ideas.id, ideas.payload_json FROM ideas
                JOIN scans ON scans.id = ideas.scan_id
                WHERE scans.scan_type = 'scheduled'
                ORDER BY ideas.id
                """
            ).fetchall()
        ideas = []
        for row in rows:
            payload = json.loads(row["payload_json"])
            payload["scan_date"] = date.fromisoformat(payload["scan_date"])
            payload["id"] = int(row["id"])
            ideas.append(TradeIdea(**payload))
        return ideas

    def cache_get(self, key: str):
        with self._connect() as db:
            row = db.execute("SELECT payload_json FROM raw_cache WHERE cache_key = ?", (key,)).fetchone()
        return json.loads(row["payload_json"]) if row else None

    def cache_put(self, key: str, payload) -> None:
        with self._connect() as db:
            db.execute(
                """
                INSERT INTO raw_cache (cache_key, payload_json, fetched_at) VALUES (?, ?, ?)
                ON CONFLICT(cache_key) DO UPDATE SET payload_json=excluded.payload_json, fetched_at=excluded.fetched_at
                """,
                (key, json.dumps(payload, sort_keys=True), datetime.utcnow().isoformat()),
            )
