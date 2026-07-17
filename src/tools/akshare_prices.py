"""A-share price adapter backed by AKShare."""

import datetime
import logging
import re

import pandas as pd

from src.data.models import Price

logger = logging.getLogger(__name__)

_A_SHARE_TICKER_PATTERN = re.compile(r"^\d{6}\.(?:SH|SZ|BJ)$", re.IGNORECASE)
_REQUIRED_COLUMNS = {"日期", "开盘", "收盘", "最高", "最低", "成交量"}


def is_a_share_ticker(ticker: str) -> bool:
    """Return whether a ticker uses the supported A-share exchange suffix."""
    return bool(_A_SHARE_TICKER_PATTERN.fullmatch(ticker.strip()))


def _to_akshare_date(value: str) -> str:
    """Convert the project's ISO date format to AKShare's YYYYMMDD format."""
    return datetime.date.fromisoformat(value).strftime("%Y%m%d")


def _fetch_stock_history(
    **kwargs,
) -> pd.DataFrame:
    """Import AKShare lazily for A-share requests."""
    import akshare as ak

    return ak.stock_zh_a_hist(**kwargs)


def get_a_share_prices(
    ticker: str,
    start_date: str,
    end_date: str,
) -> list[Price]:
    """Fetch front-adjusted A-share prices and map them to project models."""
    normalized_ticker = ticker.strip().upper()
    if not is_a_share_ticker(normalized_ticker):
        raise ValueError(f"Unsupported A-share ticker: {ticker}")

    symbol = normalized_ticker.split(".", maxsplit=1)[0]

    try:
        frame = _fetch_stock_history(
            symbol=symbol,
            period="daily",
            start_date=_to_akshare_date(start_date),
            end_date=_to_akshare_date(end_date),
            adjust="qfq",
            timeout=15,
        )
    except Exception as exc:
        logger.warning(
            "Failed to fetch A-share prices for %s from AKShare: %s",
            normalized_ticker,
            exc,
        )
        return []

    if frame is None or frame.empty:
        return []

    missing_columns = _REQUIRED_COLUMNS.difference(
        frame.columns,
    )
    if missing_columns:
        logger.warning(
            "AKShare response for %s is missing columns: %s",
            normalized_ticker,
            ", ".join(sorted(missing_columns)),
        )
        return []

    normalized = frame.rename(
        columns={
            "日期": "time",
            "开盘": "open",
            "收盘": "close",
            "最高": "high",
            "最低": "low",
            "成交量": "volume",
        }
    )[["time", "open", "close", "high", "low", "volume"]].copy()

    normalized["time"] = pd.to_datetime(normalized["time"], errors="coerce")
    for column in ["open", "close", "high", "low", "volume"]:
        normalized[column] = pd.to_numeric(normalized[column], errors="coerce")

    normalized.dropna(inplace=True)
    normalized.sort_values("time", inplace=True)

    return [
        Price(
            time=row.time.strftime("%Y-%m-%dT00:00:00"),
            open=float(row.open),
            close=float(row.close),
            high=float(row.high),
            low=float(row.low),
            volume=int(row.volume),
        )
        for row in normalized.itertuples(index=False)
    ]
