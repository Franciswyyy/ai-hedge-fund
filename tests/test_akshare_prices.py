from unittest.mock import patch

import pandas as pd

from src.data.models import Price
from src.tools.akshare_prices import get_a_share_prices, is_a_share_ticker
from src.tools.api import get_prices


def test_recognizes_explicit_a_share_tickers():
    assert is_a_share_ticker("600519.SH")
    assert is_a_share_ticker("000001.sz")
    assert is_a_share_ticker("430047.BJ")
    assert not is_a_share_ticker("600519")
    assert not is_a_share_ticker("AAPL")


@patch("src.tools.akshare_prices._fetch_stock_history")
def test_maps_and_sorts_akshare_prices(mock_fetch_stock_history):
    mock_fetch_stock_history.return_value = pd.DataFrame(
        {
            "日期": ["2025-01-03", "2025-01-02"],
            "开盘": [1510.0, 1500.0],
            "收盘": [1520.0, 1515.0],
            "最高": [1530.0, 1525.0],
            "最低": [1505.0, 1495.0],
            "成交量": [21000, 20000],
        }
    )

    prices = get_a_share_prices("600519.sh", "2025-01-01", "2025-01-03")

    mock_fetch_stock_history.assert_called_once_with(
        symbol="600519",
        period="daily",
        start_date="20250101",
        end_date="20250103",
        adjust="qfq",
        timeout=15,
    )
    assert [price.time for price in prices] == [
        "2025-01-02T00:00:00",
        "2025-01-03T00:00:00",
    ]
    assert prices[0].open == 1500.0
    assert prices[0].close == 1515.0
    assert prices[0].volume == 20000


@patch("src.tools.akshare_prices._fetch_stock_history")
def test_returns_empty_list_when_akshare_fails(mock_fetch_stock_history):
    mock_fetch_stock_history.side_effect = RuntimeError("provider unavailable")

    assert get_a_share_prices("600519.SH", "2025-01-01", "2025-01-03") == []


@patch("src.tools.api._cache")
@patch("src.tools.api.get_a_share_prices")
def test_get_prices_routes_a_share_tickers_without_financial_datasets_key(
    mock_get_a_share_prices,
    mock_cache,
):
    mock_cache.get_prices.return_value = None
    mock_get_a_share_prices.return_value = [
        Price(
            time="2025-01-02T00:00:00",
            open=1500.0,
            close=1515.0,
            high=1525.0,
            low=1495.0,
            volume=20000,
        )
    ]

    prices = get_prices("600519.sh", "2025-01-01", "2025-01-03")

    expected_cache_key = "600519.SH_2025-01-01_2025-01-03"
    expected_request = ("600519.SH", "2025-01-01", "2025-01-03")
    mock_cache.get_prices.assert_called_once_with(expected_cache_key)
    mock_get_a_share_prices.assert_called_once()
    assert mock_get_a_share_prices.call_args.args == expected_request
    mock_cache.set_prices.assert_called_once()
    assert prices[0].close == 1515.0
