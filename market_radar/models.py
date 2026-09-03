from dataclasses import asdict, dataclass, field
from datetime import date, datetime
from typing import Optional


@dataclass(frozen=True)
class DailyBar:
    session: date
    open: float
    high: float
    low: float
    close: float
    volume: float

    def to_dict(self) -> dict[str, object]:
        result = asdict(self)
        result["session"] = self.session.isoformat()
        return result


@dataclass(frozen=True)
class OptionContract:
    symbol: str
    contract_type: str
    delta: float
    bid: float
    ask: float
    last_price: float
    last_size: int
    trade_timestamp: datetime
    expiration: date


@dataclass(frozen=True)
class OptionPressure:
    axis: float
    bullish_premium: float
    total_premium: float
    valid_contracts: int
    excluded_contracts: int
    exclusions: dict[str, int]
    feed: str
    latest_trade_at: Optional[datetime]

    def to_dict(self) -> dict[str, object]:
        result = asdict(self)
        result["latest_trade_at"] = self.latest_trade_at.isoformat() if self.latest_trade_at else None
        return result


@dataclass(frozen=True)
class TradeIdea:
    ticker: str
    quadrant: str
    direction: str
    evidence_score: float
    scan_date: date
    trigger: float
    stop: float
    target_1r: float
    target_2r: float
    expires_after_sessions: int = 5
    max_holding_sessions: int = 20
    id: Optional[int] = None

    def to_dict(self) -> dict[str, object]:
        result = asdict(self)
        result["scan_date"] = self.scan_date.isoformat()
        return result


@dataclass(frozen=True)
class IdeaOutcome:
    ticker: str
    status: str
    result_r: Optional[float]
    triggered_on: Optional[date]
    closed_on: Optional[date]
    sessions_observed: int
    idea_id: Optional[int] = None

    def to_dict(self) -> dict[str, object]:
        result = asdict(self)
        result["triggered_on"] = self.triggered_on.isoformat() if self.triggered_on else None
        result["closed_on"] = self.closed_on.isoformat() if self.closed_on else None
        return result


@dataclass(frozen=True)
class SymbolSignal:
    ticker: str
    name: str
    sector: str
    sector_etf: str
    as_of: date
    close: float
    high: float
    low: float
    atr14: float
    ema20: float
    ema50: float
    ema200: float
    return_5d: float
    return_20d: float
    sector_relative_5d: float
    spy_relative_20d: float
    price_axis: float
    volume_ratio: float
    volume_percentile: float
    trend_confirmation: float
    swing_low_10d: float
    swing_high_10d: float
    dollar_turnover_5d: float = 0.0
    price_history: list[dict[str, object]] = field(default_factory=list)
    relative_history: list[dict[str, object]] = field(default_factory=list)
    industry: str = "Unclassified"
    options_axis: Optional[float] = None
    quadrant: Optional[str] = None
    evidence_score: Optional[float] = None
    valid_contracts: int = 0
    excluded_contracts: int = 0
    exclusions: dict[str, int] = field(default_factory=dict)
    feed: Optional[str] = None
    latest_trade_at: Optional[datetime] = None
    warnings: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, object]:
        result = asdict(self)
        result["as_of"] = self.as_of.isoformat()
        result["latest_trade_at"] = self.latest_trade_at.isoformat() if self.latest_trade_at else None
        return result


@dataclass(frozen=True)
class UniverseMember:
    ticker: str
    name: str
    sector: str
    sector_etf: str
    is_watchlist: bool = False
    industry: str = "Unclassified"


@dataclass(frozen=True)
class PortfolioPosition:
    ticker: str
    name: str
    sector: str
    sector_etf: str
    shares: float
    average_cost: Optional[float] = None
    industry: str = "Unclassified"
    thesis: str = ""
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None

    def to_universe_member(self) -> UniverseMember:
        return UniverseMember(
            ticker=self.ticker,
            name=self.name,
            sector=self.sector,
            sector_etf=self.sector_etf,
            is_watchlist=True,
            industry=self.industry,
        )


@dataclass(frozen=True)
class ScanResult:
    as_of: date
    scan_type: str
    status: str
    provider: str
    stock_feed: str
    option_feed: str
    config_hash: str
    started_at: datetime
    completed_at: datetime
    signals: list[SymbolSignal]
    ideas: list[TradeIdea]
    warnings: list[str]
    market_regime: dict[str, object]
    sector_returns: dict[str, list[float]]
    id: Optional[int] = None

    def to_dict(self) -> dict[str, object]:
        return {
            "id": self.id,
            "as_of": self.as_of.isoformat(),
            "scan_type": self.scan_type,
            "status": self.status,
            "provider": self.provider,
            "stock_feed": self.stock_feed,
            "option_feed": self.option_feed,
            "config_hash": self.config_hash,
            "started_at": self.started_at.isoformat(),
            "completed_at": self.completed_at.isoformat(),
            "signals": [signal.to_dict() for signal in self.signals],
            "ideas": [idea.to_dict() for idea in self.ideas],
            "warnings": self.warnings,
            "market_regime": self.market_regime,
            "sector_returns": self.sector_returns,
        }
