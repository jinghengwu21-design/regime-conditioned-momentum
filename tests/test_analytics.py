import math
import pytest
from research_agent.analytics import drawdown_episodes, portfolio_analytics
from research_agent.data import DataStore


@pytest.fixture(scope="module")
def analytics():
    return portfolio_analytics(DataStore(), "2020-01-01T00:00:00Z", "2026-10-03T12:05:00Z")


def test_calendar_compounding_reconciles_to_ledger(analytics):
    compounded = math.prod(1 + row["return"] for row in analytics["monthly"]) - 1
    assert compounded == pytest.approx(16.8157867377)
    assert sum(row["pnl"] for row in analytics["monthly"]) == pytest.approx(16815.7867377)
    assert sum(row["count"] for row in analytics["attribution"]) == 922


def test_benchmark_uses_only_matched_complete_days(analytics):
    rows = analytics["benchmark"]
    assert len(rows) == 2467
    assert rows[-1]["date"] == "2026-10-02"
    assert rows[0]["benchmark"] == pytest.approx(7202 / 7192.9 * .9995 / 1.0005 * 100)
    assert rows[0]["strategy"] == 100


def test_fill_detail_reconciles_to_trade_turnover(analytics):
    for trade in analytics["trades"]:
        assert sum(f["amount"] * f["price"] for f in trade["fills"]) == pytest.approx(trade["turnover"])
    assert analytics["risk"]["max_losing_streak"] == 17
    assert analytics["drawdowns"][0]["depth"] == pytest.approx(.3009061620126916)


def test_drawdown_episodes_keep_unrecovered_tail():
    curve = [{"date": f"2024-01-0{i+1}T00:00:00Z", "equity": x} for i, x in enumerate([100, 90, 95, 100, 120, 108])]
    rows = drawdown_episodes(curve)
    assert len(rows) == 2
    assert sum(item["recovered"] for item in rows) == 1
    assert next(item for item in rows if not item["recovered"])["recovery"] is None


def test_subperiod_retains_account_capital():
    data = portfolio_analytics(DataStore(), "2026-01-01T00:00:00Z", "2026-10-03T12:05:00Z")
    assert data["base"]["metrics"]["trade_count"] == 105
    assert data["base"]["metrics"]["opening_equity"] == pytest.approx(17718.25403183, abs=.1)
    assert len(data["monthly"]) == 10
    assert data["daily"][124]["rolling_sharpe"] is None
