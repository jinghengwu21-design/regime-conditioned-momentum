from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd


BASE = Path(r"F:\freqtrade")
BTC_5M = BASE / "user_data" / "data" / "okx" / "futures" / "BTC_USDT_USDT-5m-futures.feather"
OUT_DIR = BASE / "research" / "btc_regime_v2_2026-06-21"

BASELINE_IS = BASE / "research" / "btc_2factor_baseline_fee10_rerun_is_2026-06-21" / "signal_k_breakout_trades.csv"
BASELINE_OOS = BASE / "research" / "btc_2factor_baseline_fee10_rerun_oos_2020_2023_2026-06-21" / "signal_k_breakout_trades.csv"

BARS_PER_DAY = 288
BARS_PER_8H = 96


def profit_factor(values: pd.Series) -> float:
    wins = values[values > 0].sum()
    losses = -values[values <= 0].sum()
    return float(wins / losses) if losses > 0 else np.nan


def max_drawdown_pct(values: pd.Series) -> float:
    if values.empty:
        return np.nan
    equity = (1.0 + values.astype(float) / 10000.0).cumprod()
    drawdown = equity / equity.cummax() - 1.0
    return float(drawdown.min() * 100.0)


def safe_divide(numerator: pd.Series, denominator: pd.Series) -> pd.Series:
    return numerator / denominator.replace(0, np.nan)


def load_bars(path: Path) -> pd.DataFrame:
    df = pd.read_feather(path)
    df["date"] = pd.to_datetime(df["date"], utc=True)
    df = df.sort_values("date").reset_index(drop=True)
    numeric_cols = ["open", "high", "low", "close", "volume"]
    df[numeric_cols] = df[numeric_cols].astype(float)
    return df


def add_vwap_features(df: pd.DataFrame) -> pd.DataFrame:
    out = df.copy()
    typical = (out["high"] + out["low"] + out["close"]) / 3.0
    pv = typical * out["volume"]

    out["utc_hour"] = out["date"].dt.hour
    out["session_8h_id"] = out["date"].dt.floor("8h")
    out["session_8h_name"] = np.select(
        [
            out["utc_hour"].between(0, 7),
            out["utc_hour"].between(8, 15),
            out["utc_hour"].between(16, 23),
        ],
        ["utc_00_08", "utc_08_16", "utc_16_24"],
        default="unknown",
    )

    out["session_pv_cum_pre"] = pv.groupby(out["session_8h_id"]).cumsum().shift(1)
    out["session_vol_cum_pre"] = out["volume"].groupby(out["session_8h_id"]).cumsum().shift(1)
    session_changed = out["session_8h_id"] != out["session_8h_id"].shift(1)
    out.loc[session_changed, ["session_pv_cum_pre", "session_vol_cum_pre"]] = np.nan
    out["session_vwap_pre"] = safe_divide(out["session_pv_cum_pre"], out["session_vol_cum_pre"])

    out["rolling24_pv_sum_pre"] = pv.rolling(BARS_PER_DAY, min_periods=BARS_PER_DAY // 4).sum().shift(1)
    out["rolling24_vol_sum_pre"] = out["volume"].rolling(BARS_PER_DAY, min_periods=BARS_PER_DAY // 4).sum().shift(1)
    out["rolling24_vwap_pre"] = safe_divide(out["rolling24_pv_sum_pre"], out["rolling24_vol_sum_pre"])
    out["rolling24_vwap_slope_1h_pre"] = out["rolling24_vwap_pre"] - out["rolling24_vwap_pre"].shift(12)
    return out


def build_regime_v2(df: pd.DataFrame) -> pd.DataFrame:
    out = add_vwap_features(df)
    prior_close = out["close"].shift(1)
    high_low_range = out["high"] - out["low"]
    logret = np.log(out["close"] / out["close"].shift(1))

    out["median_range_3d_pre"] = high_low_range.rolling(BARS_PER_DAY * 3, min_periods=BARS_PER_DAY).median().shift(1)
    out["median_range_1h_pre"] = high_low_range.rolling(12, min_periods=8).median().shift(1)
    out["range_ratio_1h_vs_3d_pre"] = safe_divide(out["median_range_1h_pre"], out["median_range_3d_pre"])

    out["ret_1h_bps_pre"] = (prior_close / out["close"].shift(13) - 1.0) * 10000.0
    out["ret_4h_bps_pre"] = (prior_close / out["close"].shift(49) - 1.0) * 10000.0
    out["ret_24h_bps_pre"] = (prior_close / out["close"].shift(BARS_PER_DAY + 1) - 1.0) * 10000.0

    out["rv_1h_pre"] = logret.rolling(12, min_periods=8).std(ddof=0).shift(1) * np.sqrt(12)
    out["rv_24h_pre"] = logret.rolling(BARS_PER_DAY, min_periods=BARS_PER_DAY // 2).std(ddof=0).shift(1) * np.sqrt(BARS_PER_DAY)
    out["rv_ratio_1h_vs_24h_pre"] = safe_divide(out["rv_1h_pre"], out["rv_24h_pre"])

    out["rolling24_vwap_dist_range_units_pre"] = safe_divide(
        prior_close - out["rolling24_vwap_pre"], out["median_range_3d_pre"]
    )
    out["session_vwap_dist_range_units_pre"] = safe_divide(
        prior_close - out["session_vwap_pre"], out["median_range_3d_pre"]
    )
    out["rolling24_vwap_slope_1h_range_units_pre"] = safe_divide(
        out["rolling24_vwap_slope_1h_pre"], out["median_range_3d_pre"]
    )

    volume_1h_pre = out["volume"].rolling(12, min_periods=8).sum().shift(1)
    median_volume_1h_3d_pre = volume_1h_pre.rolling(BARS_PER_DAY * 3, min_periods=BARS_PER_DAY).median().shift(1)
    out["volume_ratio_1h_vs_3d_pre"] = safe_divide(volume_1h_pre, median_volume_1h_3d_pre)

    near_rolling24 = out["rolling24_vwap_dist_range_units_pre"].abs() <= 0.50
    near_session = out["session_vwap_dist_range_units_pre"].abs() <= 0.50
    above_rolling24 = out["rolling24_vwap_dist_range_units_pre"] > 0.50
    below_rolling24 = out["rolling24_vwap_dist_range_units_pre"] < -0.50
    above_session = out["session_vwap_dist_range_units_pre"] > 0.50
    below_session = out["session_vwap_dist_range_units_pre"] < -0.50

    out["vwap_agreement"] = np.select(
        [
            near_rolling24 & near_session,
            above_rolling24 & above_session,
            below_rolling24 & below_session,
            above_rolling24 | above_session,
            below_rolling24 | below_session,
        ],
        [
            "near_both_vwap",
            "above_both_vwap",
            "below_both_vwap",
            "mixed_above_value",
            "mixed_below_value",
        ],
        default="mixed_or_warmup",
    )

    up_trend = (
        (out["rolling24_vwap_dist_range_units_pre"] > 0.50)
        & (out["rolling24_vwap_slope_1h_range_units_pre"] > 0.15)
        & (out["ret_4h_bps_pre"] > 0)
    )
    down_trend = (
        (out["rolling24_vwap_dist_range_units_pre"] < -0.50)
        & (out["rolling24_vwap_slope_1h_range_units_pre"] < -0.15)
        & (out["ret_4h_bps_pre"] < 0)
    )
    out["trend_axis"] = np.select([up_trend, down_trend], ["up", "down"], default="balance")

    out["vol_axis"] = np.select(
        [
            out["range_ratio_1h_vs_3d_pre"] >= 2.00,
            out["range_ratio_1h_vs_3d_pre"] >= 1.25,
            out["range_ratio_1h_vs_3d_pre"] <= 0.80,
        ],
        ["shock", "active", "compressed"],
        default="normal",
    )
    out["participation_axis"] = np.select(
        [
            out["volume_ratio_1h_vs_3d_pre"] >= 1.50,
            out["volume_ratio_1h_vs_3d_pre"] <= 0.70,
        ],
        ["high", "low"],
        default="normal",
    )

    valid = (
        out["median_range_3d_pre"].notna()
        & out["rolling24_vwap_pre"].notna()
        & out["session_vwap_pre"].notna()
        & out["volume_ratio_1h_vs_3d_pre"].notna()
    )

    out["regime_v2"] = np.select(
        [
            ~valid,
            (out["trend_axis"] == "up") & out["vol_axis"].isin(["active", "shock"]),
            (out["trend_axis"] == "up"),
            (out["trend_axis"] == "down") & out["vol_axis"].isin(["active", "shock"]),
            (out["trend_axis"] == "down"),
            (out["vol_axis"] == "compressed") & (out["vwap_agreement"] == "near_both_vwap"),
            (out["vwap_agreement"].isin(["above_both_vwap", "mixed_above_value"])),
            (out["vwap_agreement"].isin(["below_both_vwap", "mixed_below_value"])),
            out["vwap_agreement"] == "near_both_vwap",
        ],
        [
            "unknown_warmup",
            "active_uptrend_acceptance",
            "quiet_uptrend_acceptance",
            "active_downtrend_acceptance",
            "quiet_downtrend_acceptance",
            "compressed_balance_near_vwap",
            "upper_value_rotation_or_extension",
            "lower_value_rotation_or_extension",
            "balanced_rotation_near_vwap",
        ],
        default="mixed_vwap_transition",
    )

    out["feature_asof_note"] = "all_regime_v2_features_shifted_or_session_to_date_pre_current_bar"
    keep_cols = [
        "date",
        "open",
        "high",
        "low",
        "close",
        "volume",
        "session_8h_id",
        "session_8h_name",
        "session_vwap_pre",
        "rolling24_vwap_pre",
        "median_range_3d_pre",
        "range_ratio_1h_vs_3d_pre",
        "rv_ratio_1h_vs_24h_pre",
        "ret_1h_bps_pre",
        "ret_4h_bps_pre",
        "ret_24h_bps_pre",
        "rolling24_vwap_dist_range_units_pre",
        "session_vwap_dist_range_units_pre",
        "rolling24_vwap_slope_1h_range_units_pre",
        "volume_ratio_1h_vs_3d_pre",
        "vwap_agreement",
        "trend_axis",
        "vol_axis",
        "participation_axis",
        "regime_v2",
        "feature_asof_note",
    ]
    return out[keep_cols]


def summarize_trades(df: pd.DataFrame, group_cols: list[str]) -> pd.DataFrame:
    rows: list[dict[str, object]] = []
    if df.empty:
        return pd.DataFrame()
    for key, grp in df.groupby(group_cols, dropna=False):
        if not isinstance(key, tuple):
            key = (key,)
        net = grp["net_bps"].astype(float)
        gross = grp["gross_bps"].astype(float) if "gross_bps" in grp else pd.Series(dtype=float)
        row = dict(zip(group_cols, key))
        row.update(
            {
                "trades": int(len(grp)),
                "profit_factor": profit_factor(net),
                "mean_net_bps": float(net.mean()),
                "median_net_bps": float(net.median()),
                "winrate": float((net > 0).mean()),
                "net_sum_bps": float(net.sum()),
                "gross_sum_bps": float(gross.sum()) if not gross.empty else np.nan,
                "max_drawdown_pct": max_drawdown_pct(net),
                "mean_r": float(grp["net_r"].mean()) if "net_r" in grp else np.nan,
                "r_profit_factor": profit_factor(grp["net_r"].astype(float)) if "net_r" in grp else np.nan,
                "target_rate": float(grp["target_reached"].mean()) if "target_reached" in grp else np.nan,
                "stop_rate": float((grp["exit_reason"] == "stop_loss").mean()) if "exit_reason" in grp else np.nan,
                "median_risk_bps": float(grp["risk_bps"].median()) if "risk_bps" in grp else np.nan,
            }
        )
        rows.append(row)
    return pd.DataFrame(rows)


def summarize_bars(regimes: pd.DataFrame) -> pd.DataFrame:
    counts = (
        regimes.groupby(["regime_v2", "trend_axis", "vol_axis", "participation_axis", "vwap_agreement"], dropna=False)
        .size()
        .reset_index(name="bars")
        .sort_values("bars", ascending=False)
    )
    counts["bar_pct"] = counts["bars"] / counts["bars"].sum()
    return counts


def run_asof_spot_audit(bars: pd.DataFrame, regimes: pd.DataFrame) -> pd.DataFrame:
    typical = (bars["high"] + bars["low"] + bars["close"]) / 3.0
    pv = typical * bars["volume"]
    idxs = [BARS_PER_DAY, 1000, 50000, 200000, len(bars) - 10]
    rows: list[dict[str, object]] = []
    for idx in idxs:
        if idx <= 0 or idx >= len(bars):
            continue
        row = regimes.iloc[idx]
        lo = max(0, idx - BARS_PER_DAY)
        rolling_vol = bars["volume"].iloc[lo:idx].sum()
        manual_rolling24 = pv.iloc[lo:idx].sum() / rolling_vol if rolling_vol else np.nan

        session_id = row["session_8h_id"]
        same_session_pre = regimes.iloc[:idx]["session_8h_id"] == session_id
        session_vol = bars["volume"].iloc[:idx][same_session_pre].sum()
        manual_session = pv.iloc[:idx][same_session_pre].sum() / session_vol if session_vol else np.nan

        rows.append(
            {
                "idx": int(idx),
                "date": row["date"],
                "rolling24_vwap_pre_diff": abs(float(row["rolling24_vwap_pre"]) - manual_rolling24)
                if np.isfinite(manual_rolling24) and pd.notna(row["rolling24_vwap_pre"])
                else np.nan,
                "session_vwap_pre_diff": abs(float(row["session_vwap_pre"]) - manual_session)
                if np.isfinite(manual_session) and pd.notna(row["session_vwap_pre"])
                else np.nan,
                "regime_v2": row["regime_v2"],
            }
        )
    return pd.DataFrame(rows)


def load_baseline_trades() -> pd.DataFrame:
    frames = []
    for sample, path in [("IS_2024plus", BASELINE_IS), ("OOS_2020_2023", BASELINE_OOS)]:
        df = pd.read_csv(path, parse_dates=["signal_date", "entry_date", "exit_date"])
        df["sample"] = sample
        df["signal_date"] = pd.to_datetime(df["signal_date"], utc=True)
        df["entry_date"] = pd.to_datetime(df["entry_date"], utc=True)
        df["year"] = df["entry_date"].dt.year
        frames.append(df)
    return pd.concat(frames, ignore_index=True)


def attach_regime_to_trades(trades: pd.DataFrame, regimes: pd.DataFrame) -> pd.DataFrame:
    regime_cols = [
        "date",
        "session_8h_name",
        "session_vwap_pre",
        "rolling24_vwap_pre",
        "range_ratio_1h_vs_3d_pre",
        "rv_ratio_1h_vs_24h_pre",
        "ret_4h_bps_pre",
        "ret_24h_bps_pre",
        "rolling24_vwap_dist_range_units_pre",
        "session_vwap_dist_range_units_pre",
        "volume_ratio_1h_vs_3d_pre",
        "vwap_agreement",
        "trend_axis",
        "vol_axis",
        "participation_axis",
        "regime_v2",
    ]
    return pd.merge_asof(
        trades.sort_values("signal_date"),
        regimes[regime_cols].sort_values("date"),
        left_on="signal_date",
        right_on="date",
        direction="backward",
    ).drop(columns=["date"])


def format_table(df: pd.DataFrame, cols: list[str], max_rows: int | None = None) -> str:
    if max_rows is not None:
        df = df.head(max_rows)
    view = df[cols].copy()
    for col in view.select_dtypes(include=["float64", "float32"]).columns:
        view[col] = view[col].round(4)
    return view.to_markdown(index=False)


def write_report(
    bar_summary: pd.DataFrame,
    overall: pd.DataFrame,
    by_regime: pd.DataFrame,
    by_axis: dict[str, pd.DataFrame],
    by_old_market_state: pd.DataFrame,
    spot_audit: pd.DataFrame,
    out_dir: Path,
) -> None:
    report = f"""# BTC Regime V2 Research Note

Generated: 2026-06-21

## Purpose

Build a market-state layer before changing strategy logic.

This is not a trading filter yet. It labels each 5m BTC bar using only information available before the current bar, then joins those labels to the existing two-factor baseline trades for diagnosis.

## External Research Anchors

- [Hamilton 1989, Markov-switching model](https://users.ssc.wisc.edu/~behansen/718/Hamilton1989.pdf): classic support for the idea that markets can move between unobserved states. A fitted HMM is not used yet because it would add state-count, training-window, and label-stability choices before we have a clean diagnostic baseline.
- [Adams and MacKay, Bayesian Online Changepoint Detection](https://arxiv.org/abs/0710.3742): useful for abrupt regime shifts because it updates the inferred run length online. It is heavier than needed for this first observable-state layer.
- [Busseti and Boyd, Volume Weighted Average Price Optimal Execution](https://web.stanford.edu/~boyd/papers/pdf/vwap_opt_exec.pdf): VWAP is treated as a volume-weighted benchmark/reference price. For 24/7 BTC there is no equity-style cash session, so this version uses both 8h UTC session VWAP and rolling 24h VWAP.
- [Moskowitz, Ooi, and Pedersen, Time Series Momentum](https://pages.stern.nyu.edu/~lpederse/papers/TimeSeriesMomentum.pdf): trend/momentum research motivates separating direction from volatility/risk state instead of hiding both inside one opaque label.

## No-Leakage Rules

- Every live feature is `*_pre`, built with `.shift(1)` or session-to-date cumulative values excluding the current bar.
- No full-sample quantiles are used in labels.
- Thresholds are coarse fixed constants: VWAP distance in 3-day median range units, 1h/3d range ratio, and 1h/3d volume ratio.
- The output is a diagnostic state table; it is not automatically approved as a strategy filter.

## VWAP Parameter Choice

- `session_vwap_pre`: 8h UTC blocks (`00-08`, `08-16`, `16-24`). This is a logical BTC/USDT perpetual segmentation because crypto trades 24/7 and many derivatives workflows anchor around 8h funding cycles.
- `rolling24_vwap_pre`: 24h rolling VWAP. This gives a day-scale value anchor without pretending BTC has a stock-market open and close.
- VWAP distance is normalized by prior 3-day median 5m range instead of a fitted z-score, so a volatility shift does not require future distribution knowledge.

## Asof Spot Audit

The audit manually recomputes the two VWAP anchors at several timestamps using only rows before the labelled bar. Differences below are floating-point noise.

{format_table(spot_audit, ["idx", "date", "regime_v2", "rolling24_vwap_pre_diff", "session_vwap_pre_diff"])}

## Regime V2 Definition

- `trend_axis`: `up`, `down`, or `balance`, based on prior close vs rolling24 VWAP, rolling24 VWAP 1h slope, and prior 4h return.
- `vol_axis`: `compressed`, `normal`, `active`, or `shock`, based on prior 1h median range divided by prior 3d median range.
- `participation_axis`: `low`, `normal`, or `high`, based on prior 1h volume divided by prior 3d median 1h volume.
- `vwap_agreement`: whether prior close is above, below, near, or mixed between 8h session VWAP and rolling24 VWAP.

## Bar Distribution

{format_table(bar_summary, ["regime_v2", "trend_axis", "vol_axis", "participation_axis", "vwap_agreement", "bars", "bar_pct"], 18)}

## Baseline Overall

{format_table(overall, ["sample", "trades", "profit_factor", "mean_net_bps", "median_net_bps", "winrate", "net_sum_bps", "max_drawdown_pct", "r_profit_factor", "mean_r", "target_rate", "stop_rate"])}

## Baseline By Regime V2

{format_table(by_regime, ["sample", "regime_v2", "trades", "profit_factor", "mean_net_bps", "median_net_bps", "winrate", "net_sum_bps", "max_drawdown_pct", "r_profit_factor", "mean_r", "target_rate", "stop_rate"], 40)}

## Axis Diagnostics

### Trend Axis

{format_table(by_axis["trend_axis"], ["sample", "trend_axis", "trades", "profit_factor", "mean_net_bps", "median_net_bps", "winrate", "net_sum_bps", "r_profit_factor", "mean_r"])}

### Volatility Axis

{format_table(by_axis["vol_axis"], ["sample", "vol_axis", "trades", "profit_factor", "mean_net_bps", "median_net_bps", "winrate", "net_sum_bps", "r_profit_factor", "mean_r"])}

### VWAP Agreement

{format_table(by_axis["vwap_agreement"], ["sample", "vwap_agreement", "trades", "profit_factor", "mean_net_bps", "median_net_bps", "winrate", "net_sum_bps", "r_profit_factor", "mean_r"])}

### Participation Axis

{format_table(by_axis["participation_axis"], ["sample", "participation_axis", "trades", "profit_factor", "mean_net_bps", "median_net_bps", "winrate", "net_sum_bps", "r_profit_factor", "mean_r"])}

## Old Market State Contrast

The old `market_state` column came from EMA proximity, compression, and channel-tail heuristics inside the strategy engine. It is kept here only as a contrast.

{format_table(by_old_market_state, ["sample", "market_state", "trades", "profit_factor", "mean_net_bps", "median_net_bps", "winrate", "net_sum_bps", "r_profit_factor", "mean_r"])}

## Reading

Regime v2 is a map, not a cure. If a bucket is bad in both IS and OOS, it is a candidate for a future pre-registered risk-control hypothesis. If a bucket is good only in IS, it is evidence of noise, not permission to filter.

The clean next step is visual inspection and stability checks, not adding every good-looking bucket into the entry rule.
"""
    (out_dir / "BTC_REGIME_V2_RESEARCH_NOTE.md").write_text(report, encoding="utf-8")


def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)

    bars = load_bars(BTC_5M)
    regimes = build_regime_v2(bars)
    spot_audit = run_asof_spot_audit(bars, regimes)
    trades = attach_regime_to_trades(load_baseline_trades(), regimes)

    bar_summary = summarize_bars(regimes)
    overall = summarize_trades(trades, ["sample"]).sort_values("sample")
    by_regime = summarize_trades(trades, ["sample", "regime_v2"]).sort_values(
        ["sample", "profit_factor", "trades"], ascending=[True, False, False]
    )
    by_axis = {
        axis: summarize_trades(trades, ["sample", axis]).sort_values(["sample", axis])
        for axis in ["trend_axis", "vol_axis", "vwap_agreement", "participation_axis"]
    }
    by_old_market_state = summarize_trades(trades, ["sample", "market_state"]).sort_values(
        ["sample", "profit_factor"], ascending=[True, False]
    )

    regimes.to_feather(OUT_DIR / "btc_regime_v2_bars.feather")
    spot_audit.to_csv(OUT_DIR / "btc_regime_v2_asof_spot_audit.csv", index=False, encoding="utf-8-sig")
    bar_summary.to_csv(OUT_DIR / "btc_regime_v2_bar_distribution.csv", index=False, encoding="utf-8-sig")
    trades.to_csv(OUT_DIR / "btc_2factor_baseline_trades_with_regime_v2.csv", index=False, encoding="utf-8-sig")
    overall.to_csv(OUT_DIR / "btc_2factor_baseline_overall_with_regime_v2.csv", index=False, encoding="utf-8-sig")
    by_regime.to_csv(OUT_DIR / "btc_2factor_baseline_by_regime_v2.csv", index=False, encoding="utf-8-sig")
    by_old_market_state.to_csv(
        OUT_DIR / "btc_2factor_baseline_by_old_market_state.csv", index=False, encoding="utf-8-sig"
    )
    for axis, table in by_axis.items():
        table.to_csv(OUT_DIR / f"btc_2factor_baseline_by_{axis}.csv", index=False, encoding="utf-8-sig")

    write_report(bar_summary, overall, by_regime, by_axis, by_old_market_state, spot_audit, OUT_DIR)

    print(f"Wrote {OUT_DIR}")
    print("overall")
    print(overall.round(6).to_string(index=False))
    print("by_regime")
    print(
        by_regime[
            [
                "sample",
                "regime_v2",
                "trades",
                "profit_factor",
                "mean_net_bps",
                "median_net_bps",
                "winrate",
                "net_sum_bps",
                "r_profit_factor",
                "mean_r",
            ]
        ]
        .round(6)
        .to_string(index=False)
    )


if __name__ == "__main__":
    main()
