"""Export an allowlisted public demo from existing Freqtrade research artifacts.

This exporter reads existing outputs; it does not backtest or access an account.
Run from this checkout with --source-root pointing at the original workspace.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import zipfile

import pandas as pd

HERE = Path(__file__).resolve().parents[1]


def write(path: Path, value: object) -> None:
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2), encoding="utf-8")


def build(root: Path, destination: Path) -> None:
    destination.mkdir(parents=True, exist_ok=True)
    source = root / "research/operations/v3f_full_history_2026-10-03"
    archive = next((source / "native").glob("backtest-result-*.zip"))
    with zipfile.ZipFile(archive) as bundle:
        name = next(n for n in bundle.namelist() if n.endswith(".json") and not n.endswith("_config.json"))
        native = json.loads(bundle.read(name))["strategy"]["SarkazV3F"]
    trades, fills = [], []
    for index, trade in enumerate(sorted(native["trades"], key=lambda t: (t["close_timestamp"], t["open_timestamp"]))):
        tid = f"T{index + 1:04d}"
        entry_n = exit_n = 0.0
        entry_count = 0
        for order in trade["orders"]:
            notional = float(order["amount"]) * float(order["safe_price"])
            is_entry = bool(order["ft_is_entry"])
            entry_n += notional if is_entry else 0
            exit_n += notional if not is_entry else 0
            entry_count += int(is_entry)
            fills.append({"trade_id": tid, "timestamp": pd.Timestamp(order["order_filled_timestamp"], unit="ms", tz="UTC").isoformat(), "side": order["ft_order_side"], "is_entry": is_entry, "amount": order["amount"], "price": order["safe_price"], "notional_usdt": notional})
        trades.append({"trade_id": tid, "asset": trade["pair"], "open_date": trade["open_date"], "close_date": trade["close_date"], "profit_abs": trade["profit_abs"], "entry_notional_usdt": entry_n, "exit_notional_usdt": exit_n, "entry_count": entry_count, "leverage": trade["leverage"], "exit_reason": trade["exit_reason"]})
    pd.DataFrame(trades).to_csv(destination / "trades.csv", index=False, float_format="%.12g")
    pd.DataFrame(fills).to_csv(destination / "fills.csv", index=False, float_format="%.12g")
    summary = json.loads((source / "summary.json").read_text(encoding="utf-8-sig"))
    write(destination / "reference_metrics.json", {k: summary[k] for k in ["total_trades", "profit_total", "cagr", "daily_wallet_sharpe", "realized_max_drawdown", "profit_factor", "winrate", "final_balance", "trades_with_add"]})
    paths = [
        ("user_data/data/research_v2/btc_5m_research_v2_20260721/train_2020_2023/BTC_USDT_USDT-5m-futures.feather", "2020-01-01", "2024-01-01"),
        ("user_data/data/okx/futures/BTC_USDT_USDT-5m-futures.feather", "2024-01-01", "2026-01-01"),
        ("research/operations/v3f_2026_backtest_2026-10-03/download/futures/BTC_USDT_USDT-5m-futures.feather", "2026-01-01", "2026-10-03"),
    ]
    parts, source_files = [], []
    for rel, left, right in paths:
        path = root / rel
        frame = pd.read_feather(path)
        frame["date"] = pd.to_datetime(frame.date, utc=True)
        parts.append(frame.loc[(frame.date >= pd.Timestamp(left, tz="UTC")) & (frame.date < pd.Timestamp(right, tz="UTC"))])
        source_files.append({"path": rel, "slice_start": left, "slice_end_exclusive": right})
    candles = pd.concat(parts).sort_values("date").set_index("date")
    if candles.index.duplicated().any():
        raise ValueError("Duplicate market timestamps")
    daily = candles.resample("1D").agg(open=("open", "first"), high=("high", "max"), low=("low", "min"), close=("close", "last"), volume=("volume", "sum"), candle_count=("close", "count"))
    daily.to_csv(destination / "market_daily.csv", index_label="date", float_format="%.12g")
    manifest = {
        "dataset_id": "rcm-3f-history-20261003-v1", "asset": "BTC/USDT:USDT", "asset_class": "crypto_perpetual", "exchange": "OKX",
        "strategy": "RCM-3F", "engine": "Freqtrade", "engine_timeframe": "5m",
        "start": "2020-01-01T00:00:00+00:00", "end_exclusive": "2026-10-03T12:05:00+00:00",
        "metric_start": "2020-01-04T11:20:00+00:00", "metric_end": "2026-10-03T12:00:00+00:00", "backtest_days": native["backtest_days"],
        "starting_balance": 1000.0, "base_fee_bps_per_side": 5.0, "funding": "excluded", "equity_basis": "closed_trade_realized",
        "market_start": daily.index.min().isoformat(), "market_end_exclusive": "2026-10-03T00:00:00+00:00",
        "market_interval": "1D", "market_aggregation": "UTC day; OHLCV aggregated from original 5m candles; final backtest half-day is not included",
        "original_report": {"path": source.relative_to(root).as_posix() + "/REPORT_CN.md"},
        "original_archive": {"path": archive.relative_to(root).as_posix()},
        "market_sources": source_files,
        "files": {p.name: {"bytes": p.stat().st_size} for p in sorted(destination.glob("*")) if p.name != "manifest.json"},
    }
    write(destination / "manifest.json", manifest)
    print(json.dumps({"trades": len(trades), "fills": len(fills), "daily_candles": len(daily), "incomplete_days": int((daily.candle_count != 288).sum()), "destination": str(destination)}, ensure_ascii=False))


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--source-root", type=Path, required=True)
    parser.add_argument("--destination", type=Path, default=HERE / "data")
    args = parser.parse_args()
    build(args.source_root.resolve(), args.destination.resolve())
