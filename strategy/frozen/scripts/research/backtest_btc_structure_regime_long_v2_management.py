from __future__ import annotations

from pathlib import Path
import sys

import numpy as np
import pandas as pd


SCRIPT_DIR = Path(__file__).resolve().parent
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

from backtest_big_body_momentum_k import add_signal_columns
from build_btc_regime_v2 import build_regime_v2


BASE = Path(r"F:\freqtrade")
BTC_5M = BASE / "user_data" / "data" / "okx" / "futures" / "BTC_USDT_USDT-5m-futures.feather"
OUT_DIR = BASE / "research" / "btc_structure_regime_long_v2_management_2026-06-21"

IS_START = pd.Timestamp("2024-01-01", tz="UTC")
EVAL_START = pd.Timestamp("2024-01-04", tz="UTC")

BARS_PER_DAY = 288
FEE_BPS = 10.0
V1_MAX_HOLD_BARS = 24
V2_MAX_HOLD_BARS = 96
V5_MAX_HOLD_BARS = 288
LAUNCH_DEADLINE_BARS = 12
STRUCTURE_HIGH_BARS = 24
RECLAIM_HIGH_BARS = 12
SUPPORT_LOOKBACK_BARS = 12
TRAIL_LOOKBACK_BARS = 12
TRAIL_2H_LOOKBACK_BARS = 24

ALLOWED_LONG_REGIMES = {
    "active_uptrend_acceptance",
    "quiet_uptrend_acceptance",
    "upper_value_rotation_or_extension",
}


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


def load_is_frame() -> pd.DataFrame:
    bars = pd.read_feather(BTC_5M)
    bars["date"] = pd.to_datetime(bars["date"], utc=True)
    bars = bars.sort_values("date").reset_index(drop=True)
    for col in ["open", "high", "low", "close", "volume"]:
        bars[col] = bars[col].astype(float)

    bars = bars[bars["date"] >= IS_START].reset_index(drop=True)
    signal_frame = add_signal_columns(
        bars,
        timeframe="5m",
        body_pct_min=0.70,
        range_z_min=1.0,
        range_filter="rolling_quantile",
        range_window_days=3,
        range_quantile=0.90,
        robust_range_zscore=2.0,
        tod_lookback_days=20,
        range_confirm_mean_bars=0,
        range_confirm_mean_multiple=1.0,
    )
    regimes = build_regime_v2(bars)
    regime_cols = [
        "date",
        "regime_v2",
        "trend_axis",
        "vol_axis",
        "participation_axis",
        "vwap_agreement",
        "session_vwap_pre",
        "rolling24_vwap_pre",
        "median_range_3d_pre",
        "range_ratio_1h_vs_3d_pre",
        "volume_ratio_1h_vs_3d_pre",
    ]
    df = pd.merge_asof(
        signal_frame.sort_values("date"),
        regimes[regime_cols].sort_values("date"),
        on="date",
        direction="backward",
    )
    df = add_structure_features(df)
    return df[df["date"] >= EVAL_START].reset_index(drop=True)


def add_structure_features(df: pd.DataFrame) -> pd.DataFrame:
    out = df.copy()
    out["prior_2h_high"] = (
        out["high"].rolling(STRUCTURE_HIGH_BARS, min_periods=STRUCTURE_HIGH_BARS // 2).max().shift(1)
    )
    out["prior_2h_low"] = (
        out["low"].rolling(STRUCTURE_HIGH_BARS, min_periods=STRUCTURE_HIGH_BARS // 2).min().shift(1)
    )
    out["prior_1h_high"] = (
        out["high"].rolling(RECLAIM_HIGH_BARS, min_periods=RECLAIM_HIGH_BARS // 2).max().shift(1)
    )
    out["prior_1h_low"] = (
        out["low"].rolling(RECLAIM_HIGH_BARS, min_periods=RECLAIM_HIGH_BARS // 2).min().shift(1)
    )
    out["prior_1h_low_for_support"] = (
        out["low"].rolling(SUPPORT_LOOKBACK_BARS, min_periods=SUPPORT_LOOKBACK_BARS // 2).min().shift(1)
    )
    out["prior_2h_box_range_units"] = (
        (out["prior_2h_high"] - out["prior_2h_low"]) / out["median_range_3d_pre"].replace(0, np.nan)
    )
    out["break_prior_2h_high"] = out["close"] > out["prior_2h_high"]
    out["break_prior_1h_high"] = out["close"] > out["prior_1h_high"]
    out["signal_tests_rolling24_support"] = out["low"] <= (
        out["rolling24_vwap_pre"] + out["median_range_3d_pre"]
    )
    out["reclaim_from_rolling24_support"] = (
        out["signal_tests_rolling24_support"]
        & out["break_prior_1h_high"]
        & (out["close"] > out["session_vwap_pre"])
        & (out["close"] > out["rolling24_vwap_pre"])
    )
    out["long_signal_k"] = out["is_big_body_momentum_k"].fillna(False) & (out["direction"] > 0)
    out["regime_long_ok"] = out["regime_v2"].isin(ALLOWED_LONG_REGIMES)
    out["structure_event"] = out["break_prior_2h_high"] | out["reclaim_from_rolling24_support"]
    return out


def select_structure_candidates(df: pd.DataFrame) -> pd.DataFrame:
    base = df["long_signal_k"] & df["regime_long_ok"] & df["structure_event"]
    candidate_indices = np.flatnonzero(base.fillna(False).to_numpy())
    selected: list[int] = []
    last_idx: int | None = None
    last_high = np.nan
    for idx in candidate_indices:
        row = df.iloc[idx]
        close = float(row["close"])
        high = float(row["high"])
        median_range = float(row["median_range_3d_pre"]) if np.isfinite(row["median_range_3d_pre"]) else np.nan
        reclaim = bool(row["reclaim_from_rolling24_support"])

        if last_idx is None:
            selected.append(idx)
            last_idx = idx
            last_high = high
            continue

        bars_since = idx - last_idx
        new_leg = np.isfinite(median_range) and np.isfinite(last_high) and close > last_high + median_range
        enough_time = bars_since >= STRUCTURE_HIGH_BARS
        if reclaim or new_leg or enough_time:
            selected.append(idx)
            last_idx = idx
            last_high = high
    out = df.iloc[selected].copy()
    out["structure_selected"] = True
    return out


def setup_base_row(
    variant: str,
    signal_idx: int,
    signal: pd.Series,
    trigger: pd.Series,
    entry_triggered: bool,
    entry_price: float,
    stop_entry: float,
    stop_loss: float,
    risk_abs: float,
) -> dict[str, object]:
    risk_bps = risk_abs / entry_price * 10000.0 if entry_triggered and entry_price > 0 else np.nan
    return {
        "variant": variant,
        "signal_idx": int(signal_idx),
        "signal_date": signal["date"],
        "entry_bar_date": trigger["date"],
        "entry_triggered": bool(entry_triggered),
        "entry_price": entry_price,
        "stop_entry": stop_entry,
        "stop_loss": stop_loss,
        "risk_bps": risk_bps,
        "body_pct": float(signal["body_pct"]),
        "upper_pct": float(signal["upper_pct"]),
        "lower_pct": float(signal["lower_pct"]),
        "range_filter_score": float(signal["range_filter_score"])
        if np.isfinite(signal["range_filter_score"])
        else np.nan,
        "regime_v2": signal["regime_v2"],
        "trend_axis": signal["trend_axis"],
        "vol_axis": signal["vol_axis"],
        "participation_axis": signal["participation_axis"],
        "vwap_agreement": signal["vwap_agreement"],
        "prior_2h_high": float(signal["prior_2h_high"]) if np.isfinite(signal["prior_2h_high"]) else np.nan,
        "prior_1h_high": float(signal["prior_1h_high"]) if np.isfinite(signal["prior_1h_high"]) else np.nan,
        "prior_2h_box_range_units": float(signal["prior_2h_box_range_units"])
        if np.isfinite(signal["prior_2h_box_range_units"])
        else np.nan,
        "break_prior_2h_high": bool(signal["break_prior_2h_high"]),
        "signal_tests_rolling24_support": bool(signal["signal_tests_rolling24_support"]),
        "reclaim_from_rolling24_support": bool(signal["reclaim_from_rolling24_support"]),
    }


def simulate_trades(df: pd.DataFrame, signals: pd.DataFrame, variant: str, manager: str) -> pd.DataFrame:
    rows: list[dict[str, object]] = []
    for idx, signal in signals.iterrows():
        if idx + 1 >= len(df):
            continue
        trigger = df.iloc[idx + 1]
        stop_entry = float(signal["high"])
        if manager == "v10_body_low_stop_2htrail_24h":
            stop_loss = float(min(signal["open"], signal["close"]))
        else:
            stop_loss = float(signal["low"])
        if not np.isfinite(stop_entry) or not np.isfinite(stop_loss) or stop_entry <= stop_loss:
            continue
        if float(trigger["high"]) < stop_entry:
            entry_triggered = False
            entry_price = np.nan
            risk_abs = np.nan
        else:
            entry_triggered = True
            entry_price = max(float(trigger["open"]), stop_entry)
            risk_abs = entry_price - stop_loss
        if entry_triggered and (not np.isfinite(risk_abs) or risk_abs <= 0):
            continue

        row = setup_base_row(
            variant=variant,
            signal_idx=int(idx),
            signal=signal,
            trigger=trigger,
            entry_triggered=entry_triggered,
            entry_price=entry_price,
            stop_entry=stop_entry,
            stop_loss=stop_loss,
            risk_abs=risk_abs,
        )
        if entry_triggered:
            if manager == "v1_target2r_24b":
                row.update(simulate_v1_path(df, idx + 1, entry_price, stop_loss, risk_abs))
            elif manager == "v2_1r_breakeven_1htrail_96b":
                row.update(simulate_v2_path(df, idx + 1, entry_price, stop_loss, risk_abs))
            elif manager == "v3_acceptance_fail_1htrail_96b":
                row.update(
                    simulate_v3_path(
                        df=df,
                        entry_idx=idx + 1,
                        entry_price=entry_price,
                        stop_loss=stop_loss,
                        risk_abs=risk_abs,
                        breakout_level=stop_entry,
                    )
                )
            elif manager == "v4_1r_breakeven_2htrail_96b":
                row.update(simulate_v4_path(df, idx + 1, entry_price, stop_loss, risk_abs))
            elif manager == "v5_1r_breakeven_2htrail_24h":
                row.update(simulate_v5_path(df, idx + 1, entry_price, stop_loss, risk_abs))
            elif manager == "v6_trigger_close_confirm_2htrail_24h":
                row.update(
                    simulate_trigger_acceptance_path(
                        df=df,
                        entry_idx=idx + 1,
                        entry_price=entry_price,
                        stop_loss=stop_loss,
                        risk_abs=risk_abs,
                        breakout_level=stop_entry,
                        require_trigger_close_confirmation=True,
                        use_trigger_low_stop=False,
                    )
                )
            elif manager == "v7_trigger_low_stop_2htrail_24h":
                row.update(
                    simulate_trigger_acceptance_path(
                        df=df,
                        entry_idx=idx + 1,
                        entry_price=entry_price,
                        stop_loss=stop_loss,
                        risk_abs=risk_abs,
                        breakout_level=stop_entry,
                        require_trigger_close_confirmation=False,
                        use_trigger_low_stop=True,
                    )
                )
            elif manager == "v8_half_tp1_2htrail_24h":
                row.update(simulate_half_tp1_path(df, idx + 1, entry_price, stop_loss, risk_abs))
            elif manager == "v9_launch_1h_or_exit_2htrail_24h":
                row.update(simulate_launch_deadline_path(df, idx + 1, entry_price, stop_loss, risk_abs))
            elif manager == "v10_body_low_stop_2htrail_24h":
                row.update(simulate_v5_path(df, idx + 1, entry_price, stop_loss, risk_abs))
            else:
                raise ValueError(f"Unsupported manager: {manager}")
        rows.append(row)
    trades = pd.DataFrame(rows)
    if trades.empty:
        return trades
    trades["sample"] = "IS_2024plus_clean"
    trades["year"] = pd.to_datetime(trades["signal_date"], utc=True).dt.year
    return trades.reset_index(drop=True)


def finalize_path(
    df: pd.DataFrame,
    entry_idx: int,
    entry_price: float,
    risk_abs: float,
    scheduled_end_idx: int,
    exit_price: float,
    exit_reason: str,
    bars_held: int,
    hit_1r: bool,
    hit_2r: bool,
    hit_stop: bool,
    ambiguous: bool,
    protection_activated: bool = False,
    max_stop_price: float | None = None,
) -> dict[str, object]:
    gross_bps = (exit_price / entry_price - 1.0) * 10000.0
    net_bps = gross_bps - FEE_BPS
    gross_r = (exit_price - entry_price) / risk_abs
    fee_r = FEE_BPS / (risk_abs / entry_price * 10000.0)
    net_r = gross_r - fee_r
    exit_idx = min(len(df) - 1, entry_idx + bars_held)
    path = df.iloc[entry_idx : exit_idx + 1]
    mfe_r = (path["high"].max() - entry_price) / risk_abs
    mae_r = (path["low"].min() - entry_price) / risk_abs
    capture_r = net_r / mfe_r if np.isfinite(mfe_r) and mfe_r > 0 else np.nan
    return {
        "exit_date": df.iloc[entry_idx + bars_held]["date"],
        "exit_price": exit_price,
        "exit_reason": exit_reason,
        "bars_held": int(bars_held),
        "gross_bps": gross_bps,
        "net_bps": net_bps,
        "gross_r": gross_r,
        "net_r": net_r,
        "fee_r": fee_r,
        "mfe_r": mfe_r,
        "mae_r": mae_r,
        "capture_r": capture_r,
        "hit_1r": bool(hit_1r),
        "hit_2r": bool(hit_2r),
        "hit_stop": bool(hit_stop),
        "ambiguous": bool(ambiguous),
        "protection_activated": bool(protection_activated),
        "max_stop_price": max_stop_price if max_stop_price is not None else np.nan,
        "scheduled_end_idx": int(scheduled_end_idx),
    }


def simulate_v1_path(
    df: pd.DataFrame,
    entry_idx: int,
    entry_price: float,
    stop_loss: float,
    risk_abs: float,
) -> dict[str, object]:
    target_1r = entry_price + risk_abs
    target_2r = entry_price + 2.0 * risk_abs
    end_idx = min(len(df) - 1, entry_idx + V1_MAX_HOLD_BARS)
    exit_price = float(df.iloc[end_idx]["close"])
    exit_reason = "time_exit"
    bars_held = end_idx - entry_idx
    hit_1r = False
    hit_2r = False
    hit_stop = False
    ambiguous = False

    for j in range(entry_idx, end_idx + 1):
        low = float(df.iloc[j]["low"])
        high = float(df.iloc[j]["high"])
        stop_touch = low <= stop_loss
        target_1r_touch = high >= target_1r
        target_2r_touch = high >= target_2r
        if stop_touch and target_1r_touch:
            ambiguous = True
            hit_stop = True
            exit_price = stop_loss
            exit_reason = "ambiguous_stop_first"
            bars_held = j - entry_idx
            break
        if stop_touch:
            hit_stop = True
            exit_price = stop_loss
            exit_reason = "stop_loss"
            bars_held = j - entry_idx
            break
        if target_2r_touch:
            hit_1r = True
            hit_2r = True
            exit_price = target_2r
            exit_reason = "target_2r"
            bars_held = j - entry_idx
            break
        if target_1r_touch:
            hit_1r = True

    return finalize_path(
        df=df,
        entry_idx=entry_idx,
        entry_price=entry_price,
        risk_abs=risk_abs,
        scheduled_end_idx=end_idx,
        exit_price=exit_price,
        exit_reason=exit_reason,
        bars_held=bars_held,
        hit_1r=hit_1r,
        hit_2r=hit_2r,
        hit_stop=hit_stop,
        ambiguous=ambiguous,
        protection_activated=False,
        max_stop_price=stop_loss,
    )


def trailing_low_before_bar(df: pd.DataFrame, bar_idx: int, lookback_bars: int = TRAIL_LOOKBACK_BARS) -> float:
    start = max(0, bar_idx - lookback_bars)
    if start >= bar_idx:
        return np.nan
    return float(df.iloc[start:bar_idx]["low"].min())


def simulate_v2_path(
    df: pd.DataFrame,
    entry_idx: int,
    entry_price: float,
    stop_loss: float,
    risk_abs: float,
) -> dict[str, object]:
    target_1r = entry_price + risk_abs
    end_idx = min(len(df) - 1, entry_idx + V2_MAX_HOLD_BARS)
    exit_price = float(df.iloc[end_idx]["close"])
    exit_reason = "time_exit_8h"
    bars_held = end_idx - entry_idx
    active_stop = stop_loss
    stop_stage = "initial_stop"
    max_stop_price = active_stop
    hit_1r = False
    hit_2r = False
    hit_stop = False
    ambiguous = False
    protection_activated = False

    for j in range(entry_idx, end_idx + 1):
        if protection_activated:
            prior_1h_low = trailing_low_before_bar(df, j)
            if np.isfinite(prior_1h_low):
                trail_stop = max(active_stop, entry_price, prior_1h_low)
                if trail_stop > active_stop:
                    active_stop = trail_stop
                    stop_stage = "structure_1h_trail_stop" if trail_stop > entry_price else "breakeven_stop"
                    max_stop_price = max(max_stop_price, active_stop)

        low = float(df.iloc[j]["low"])
        high = float(df.iloc[j]["high"])
        stop_touch = low <= active_stop
        target_1r_touch = high >= target_1r

        if stop_touch and (not protection_activated) and target_1r_touch:
            ambiguous = True
            hit_stop = True
            exit_price = active_stop
            exit_reason = "ambiguous_initial_stop_first"
            bars_held = j - entry_idx
            break
        if stop_touch:
            hit_stop = True
            exit_price = active_stop
            exit_reason = stop_stage
            bars_held = j - entry_idx
            break
        if target_1r_touch and not protection_activated:
            hit_1r = True
            protection_activated = True
            active_stop = max(active_stop, entry_price)
            stop_stage = "breakeven_stop"
            max_stop_price = max(max_stop_price, active_stop)
        if high >= entry_price + 2.0 * risk_abs:
            hit_2r = True

    return finalize_path(
        df=df,
        entry_idx=entry_idx,
        entry_price=entry_price,
        risk_abs=risk_abs,
        scheduled_end_idx=end_idx,
        exit_price=exit_price,
        exit_reason=exit_reason,
        bars_held=bars_held,
        hit_1r=hit_1r,
        hit_2r=hit_2r,
        hit_stop=hit_stop,
        ambiguous=ambiguous,
        protection_activated=protection_activated,
        max_stop_price=max_stop_price,
    )


def simulate_v3_path(
    df: pd.DataFrame,
    entry_idx: int,
    entry_price: float,
    stop_loss: float,
    risk_abs: float,
    breakout_level: float,
) -> dict[str, object]:
    target_1r = entry_price + risk_abs
    end_idx = min(len(df) - 1, entry_idx + V2_MAX_HOLD_BARS)
    exit_price = float(df.iloc[end_idx]["close"])
    exit_reason = "time_exit_8h"
    bars_held = end_idx - entry_idx
    active_stop = stop_loss
    stop_stage = "initial_stop"
    max_stop_price = active_stop
    hit_1r = False
    hit_2r = False
    hit_stop = False
    ambiguous = False
    protection_activated = False

    for j in range(entry_idx, end_idx + 1):
        if protection_activated:
            prior_1h_low = trailing_low_before_bar(df, j)
            if np.isfinite(prior_1h_low):
                trail_stop = max(active_stop, entry_price, prior_1h_low)
                if trail_stop > active_stop:
                    active_stop = trail_stop
                    stop_stage = "structure_1h_trail_stop" if trail_stop > entry_price else "breakeven_stop"
                    max_stop_price = max(max_stop_price, active_stop)

        bar = df.iloc[j]
        low = float(bar["low"])
        high = float(bar["high"])
        close = float(bar["close"])
        stop_touch = low <= active_stop
        target_1r_touch = high >= target_1r

        if stop_touch and (not protection_activated) and target_1r_touch:
            ambiguous = True
            hit_stop = True
            exit_price = active_stop
            exit_reason = "ambiguous_initial_stop_first"
            bars_held = j - entry_idx
            break
        if stop_touch:
            hit_stop = True
            exit_price = active_stop
            exit_reason = stop_stage
            bars_held = j - entry_idx
            break
        if target_1r_touch and not protection_activated:
            hit_1r = True
            protection_activated = True
            active_stop = max(active_stop, entry_price)
            stop_stage = "breakeven_stop"
            max_stop_price = max(max_stop_price, active_stop)
        elif (not protection_activated) and close < breakout_level:
            exit_price = close
            exit_reason = "breakout_acceptance_failure"
            bars_held = j - entry_idx
            break
        if high >= entry_price + 2.0 * risk_abs:
            hit_2r = True

    return finalize_path(
        df=df,
        entry_idx=entry_idx,
        entry_price=entry_price,
        risk_abs=risk_abs,
        scheduled_end_idx=end_idx,
        exit_price=exit_price,
        exit_reason=exit_reason,
        bars_held=bars_held,
        hit_1r=hit_1r,
        hit_2r=hit_2r,
        hit_stop=hit_stop,
        ambiguous=ambiguous,
        protection_activated=protection_activated,
        max_stop_price=max_stop_price,
    )


def simulate_v4_path(
    df: pd.DataFrame,
    entry_idx: int,
    entry_price: float,
    stop_loss: float,
    risk_abs: float,
) -> dict[str, object]:
    target_1r = entry_price + risk_abs
    end_idx = min(len(df) - 1, entry_idx + V2_MAX_HOLD_BARS)
    exit_price = float(df.iloc[end_idx]["close"])
    exit_reason = "time_exit_8h"
    bars_held = end_idx - entry_idx
    active_stop = stop_loss
    stop_stage = "initial_stop"
    max_stop_price = active_stop
    hit_1r = False
    hit_2r = False
    hit_stop = False
    ambiguous = False
    protection_activated = False

    for j in range(entry_idx, end_idx + 1):
        if protection_activated:
            prior_2h_low = trailing_low_before_bar(df, j, TRAIL_2H_LOOKBACK_BARS)
            if np.isfinite(prior_2h_low):
                trail_stop = max(active_stop, entry_price, prior_2h_low)
                if trail_stop > active_stop:
                    active_stop = trail_stop
                    stop_stage = "structure_2h_trail_stop" if trail_stop > entry_price else "breakeven_stop"
                    max_stop_price = max(max_stop_price, active_stop)

        low = float(df.iloc[j]["low"])
        high = float(df.iloc[j]["high"])
        stop_touch = low <= active_stop
        target_1r_touch = high >= target_1r

        if stop_touch and (not protection_activated) and target_1r_touch:
            ambiguous = True
            hit_stop = True
            exit_price = active_stop
            exit_reason = "ambiguous_initial_stop_first"
            bars_held = j - entry_idx
            break
        if stop_touch:
            hit_stop = True
            exit_price = active_stop
            exit_reason = stop_stage
            bars_held = j - entry_idx
            break
        if target_1r_touch and not protection_activated:
            hit_1r = True
            protection_activated = True
            active_stop = max(active_stop, entry_price)
            stop_stage = "breakeven_stop"
            max_stop_price = max(max_stop_price, active_stop)
        if high >= entry_price + 2.0 * risk_abs:
            hit_2r = True

    return finalize_path(
        df=df,
        entry_idx=entry_idx,
        entry_price=entry_price,
        risk_abs=risk_abs,
        scheduled_end_idx=end_idx,
        exit_price=exit_price,
        exit_reason=exit_reason,
        bars_held=bars_held,
        hit_1r=hit_1r,
        hit_2r=hit_2r,
        hit_stop=hit_stop,
        ambiguous=ambiguous,
        protection_activated=protection_activated,
        max_stop_price=max_stop_price,
    )


def simulate_v5_path(
    df: pd.DataFrame,
    entry_idx: int,
    entry_price: float,
    stop_loss: float,
    risk_abs: float,
) -> dict[str, object]:
    target_1r = entry_price + risk_abs
    end_idx = min(len(df) - 1, entry_idx + V5_MAX_HOLD_BARS)
    exit_price = float(df.iloc[end_idx]["close"])
    exit_reason = "time_exit_24h"
    bars_held = end_idx - entry_idx
    active_stop = stop_loss
    stop_stage = "initial_stop"
    max_stop_price = active_stop
    hit_1r = False
    hit_2r = False
    hit_stop = False
    ambiguous = False
    protection_activated = False

    for j in range(entry_idx, end_idx + 1):
        if protection_activated:
            prior_2h_low = trailing_low_before_bar(df, j, TRAIL_2H_LOOKBACK_BARS)
            if np.isfinite(prior_2h_low):
                trail_stop = max(active_stop, entry_price, prior_2h_low)
                if trail_stop > active_stop:
                    active_stop = trail_stop
                    stop_stage = "structure_2h_trail_stop" if trail_stop > entry_price else "breakeven_stop"
                    max_stop_price = max(max_stop_price, active_stop)

        low = float(df.iloc[j]["low"])
        high = float(df.iloc[j]["high"])
        stop_touch = low <= active_stop
        target_1r_touch = high >= target_1r

        if stop_touch and (not protection_activated) and target_1r_touch:
            ambiguous = True
            hit_stop = True
            exit_price = active_stop
            exit_reason = "ambiguous_initial_stop_first"
            bars_held = j - entry_idx
            break
        if stop_touch:
            hit_stop = True
            exit_price = active_stop
            exit_reason = stop_stage
            bars_held = j - entry_idx
            break
        if target_1r_touch and not protection_activated:
            hit_1r = True
            protection_activated = True
            active_stop = max(active_stop, entry_price)
            stop_stage = "breakeven_stop"
            max_stop_price = max(max_stop_price, active_stop)
        if high >= entry_price + 2.0 * risk_abs:
            hit_2r = True

    return finalize_path(
        df=df,
        entry_idx=entry_idx,
        entry_price=entry_price,
        risk_abs=risk_abs,
        scheduled_end_idx=end_idx,
        exit_price=exit_price,
        exit_reason=exit_reason,
        bars_held=bars_held,
        hit_1r=hit_1r,
        hit_2r=hit_2r,
        hit_stop=hit_stop,
        ambiguous=ambiguous,
        protection_activated=protection_activated,
        max_stop_price=max_stop_price,
    )


def simulate_trigger_acceptance_path(
    df: pd.DataFrame,
    entry_idx: int,
    entry_price: float,
    stop_loss: float,
    risk_abs: float,
    breakout_level: float,
    require_trigger_close_confirmation: bool,
    use_trigger_low_stop: bool,
) -> dict[str, object]:
    target_1r = entry_price + risk_abs
    end_idx = min(len(df) - 1, entry_idx + V5_MAX_HOLD_BARS)
    exit_price = float(df.iloc[end_idx]["close"])
    exit_reason = "time_exit_24h"
    bars_held = end_idx - entry_idx
    active_stop = stop_loss
    stop_stage = "initial_stop"
    max_stop_price = active_stop
    hit_1r = False
    hit_2r = False
    hit_stop = False
    ambiguous = False
    protection_activated = False
    trigger_stop_armed = False

    for j in range(entry_idx, end_idx + 1):
        if protection_activated:
            prior_2h_low = trailing_low_before_bar(df, j, TRAIL_2H_LOOKBACK_BARS)
            if np.isfinite(prior_2h_low):
                trail_stop = max(active_stop, entry_price, prior_2h_low)
                if trail_stop > active_stop:
                    active_stop = trail_stop
                    stop_stage = "structure_2h_trail_stop" if trail_stop > entry_price else "breakeven_stop"
                    max_stop_price = max(max_stop_price, active_stop)

        bar = df.iloc[j]
        low = float(bar["low"])
        high = float(bar["high"])
        close = float(bar["close"])
        stop_touch = low <= active_stop
        target_1r_touch = high >= target_1r

        if stop_touch and (not protection_activated) and target_1r_touch:
            ambiguous = True
            hit_stop = True
            exit_price = active_stop
            exit_reason = "ambiguous_initial_stop_first"
            bars_held = j - entry_idx
            break
        if stop_touch:
            hit_stop = True
            exit_price = active_stop
            exit_reason = stop_stage
            bars_held = j - entry_idx
            break
        if target_1r_touch and not protection_activated:
            hit_1r = True
            protection_activated = True
            active_stop = max(active_stop, entry_price)
            stop_stage = "breakeven_stop"
            max_stop_price = max(max_stop_price, active_stop)

        if j == entry_idx and not protection_activated:
            if require_trigger_close_confirmation and close < breakout_level:
                exit_price = close
                exit_reason = "trigger_close_acceptance_failure"
                bars_held = 0
                break
            if use_trigger_low_stop and close >= breakout_level:
                trigger_low = float(bar["low"])
                if np.isfinite(trigger_low) and trigger_low > active_stop:
                    active_stop = trigger_low
                    stop_stage = "trigger_low_stop"
                    max_stop_price = max(max_stop_price, active_stop)
                    trigger_stop_armed = True

        if high >= entry_price + 2.0 * risk_abs:
            hit_2r = True

    result = finalize_path(
        df=df,
        entry_idx=entry_idx,
        entry_price=entry_price,
        risk_abs=risk_abs,
        scheduled_end_idx=end_idx,
        exit_price=exit_price,
        exit_reason=exit_reason,
        bars_held=bars_held,
        hit_1r=hit_1r,
        hit_2r=hit_2r,
        hit_stop=hit_stop,
        ambiguous=ambiguous,
        protection_activated=protection_activated,
        max_stop_price=max_stop_price,
    )
    result["trigger_stop_armed"] = bool(trigger_stop_armed)
    return result


def finalize_scaled_path(
    df: pd.DataFrame,
    entry_idx: int,
    entry_price: float,
    risk_abs: float,
    scheduled_end_idx: int,
    exit_price: float,
    exit_reason: str,
    bars_held: int,
    runner_fraction: float,
    realized_r: float,
    hit_1r: bool,
    hit_2r: bool,
    hit_stop: bool,
    ambiguous: bool,
    protection_activated: bool,
    max_stop_price: float,
) -> dict[str, object]:
    runner_r = (exit_price - entry_price) / risk_abs
    gross_r = realized_r + runner_fraction * runner_r
    effective_exit_price = entry_price + gross_r * risk_abs
    gross_bps = (effective_exit_price / entry_price - 1.0) * 10000.0
    net_bps = gross_bps - FEE_BPS
    fee_r = FEE_BPS / (risk_abs / entry_price * 10000.0)
    net_r = gross_r - fee_r
    exit_idx = min(len(df) - 1, entry_idx + bars_held)
    path = df.iloc[entry_idx : exit_idx + 1]
    mfe_r = (path["high"].max() - entry_price) / risk_abs
    mae_r = (path["low"].min() - entry_price) / risk_abs
    capture_r = net_r / mfe_r if np.isfinite(mfe_r) and mfe_r > 0 else np.nan
    return {
        "exit_date": df.iloc[entry_idx + bars_held]["date"],
        "exit_price": effective_exit_price,
        "runner_exit_price": exit_price,
        "exit_reason": exit_reason,
        "bars_held": int(bars_held),
        "gross_bps": gross_bps,
        "net_bps": net_bps,
        "gross_r": gross_r,
        "net_r": net_r,
        "fee_r": fee_r,
        "mfe_r": mfe_r,
        "mae_r": mae_r,
        "capture_r": capture_r,
        "hit_1r": bool(hit_1r),
        "hit_2r": bool(hit_2r),
        "hit_stop": bool(hit_stop),
        "ambiguous": bool(ambiguous),
        "protection_activated": bool(protection_activated),
        "max_stop_price": max_stop_price,
        "scheduled_end_idx": int(scheduled_end_idx),
        "scaled_exit": True,
        "runner_fraction": float(runner_fraction),
        "realized_r": float(realized_r),
    }


def simulate_half_tp1_path(
    df: pd.DataFrame,
    entry_idx: int,
    entry_price: float,
    stop_loss: float,
    risk_abs: float,
) -> dict[str, object]:
    target_1r = entry_price + risk_abs
    end_idx = min(len(df) - 1, entry_idx + V5_MAX_HOLD_BARS)
    exit_price = float(df.iloc[end_idx]["close"])
    exit_reason = "time_exit_24h"
    bars_held = end_idx - entry_idx
    active_stop = stop_loss
    stop_stage = "initial_stop"
    max_stop_price = active_stop
    hit_1r = False
    hit_2r = False
    hit_stop = False
    ambiguous = False
    protection_activated = False
    runner_fraction = 1.0
    realized_r = 0.0

    for j in range(entry_idx, end_idx + 1):
        if protection_activated:
            prior_2h_low = trailing_low_before_bar(df, j, TRAIL_2H_LOOKBACK_BARS)
            if np.isfinite(prior_2h_low):
                trail_stop = max(active_stop, entry_price, prior_2h_low)
                if trail_stop > active_stop:
                    active_stop = trail_stop
                    stop_stage = "partial_1r_structure_2h_trail_stop" if trail_stop > entry_price else "partial_1r_breakeven_stop"
                    max_stop_price = max(max_stop_price, active_stop)

        low = float(df.iloc[j]["low"])
        high = float(df.iloc[j]["high"])
        stop_touch = low <= active_stop
        target_1r_touch = high >= target_1r

        if stop_touch and (not protection_activated) and target_1r_touch:
            ambiguous = True
            hit_stop = True
            exit_price = active_stop
            exit_reason = "ambiguous_initial_stop_first"
            bars_held = j - entry_idx
            break
        if stop_touch:
            hit_stop = True
            exit_price = active_stop
            exit_reason = stop_stage
            bars_held = j - entry_idx
            break
        if target_1r_touch and not protection_activated:
            hit_1r = True
            protection_activated = True
            runner_fraction = 0.5
            realized_r = 0.5
            active_stop = max(active_stop, entry_price)
            stop_stage = "partial_1r_breakeven_stop"
            max_stop_price = max(max_stop_price, active_stop)
        if high >= entry_price + 2.0 * risk_abs:
            hit_2r = True

    if not protection_activated:
        return finalize_path(
            df=df,
            entry_idx=entry_idx,
            entry_price=entry_price,
            risk_abs=risk_abs,
            scheduled_end_idx=end_idx,
            exit_price=exit_price,
            exit_reason=exit_reason,
            bars_held=bars_held,
            hit_1r=hit_1r,
            hit_2r=hit_2r,
            hit_stop=hit_stop,
            ambiguous=ambiguous,
            protection_activated=protection_activated,
            max_stop_price=max_stop_price,
        )

    return finalize_scaled_path(
        df=df,
        entry_idx=entry_idx,
        entry_price=entry_price,
        risk_abs=risk_abs,
        scheduled_end_idx=end_idx,
        exit_price=exit_price,
        exit_reason=exit_reason,
        bars_held=bars_held,
        runner_fraction=runner_fraction,
        realized_r=realized_r,
        hit_1r=hit_1r,
        hit_2r=hit_2r,
        hit_stop=hit_stop,
        ambiguous=ambiguous,
        protection_activated=protection_activated,
        max_stop_price=max_stop_price,
    )


def simulate_launch_deadline_path(
    df: pd.DataFrame,
    entry_idx: int,
    entry_price: float,
    stop_loss: float,
    risk_abs: float,
) -> dict[str, object]:
    target_1r = entry_price + risk_abs
    end_idx = min(len(df) - 1, entry_idx + V5_MAX_HOLD_BARS)
    exit_price = float(df.iloc[end_idx]["close"])
    exit_reason = "time_exit_24h"
    bars_held = end_idx - entry_idx
    active_stop = stop_loss
    stop_stage = "initial_stop"
    max_stop_price = active_stop
    hit_1r = False
    hit_2r = False
    hit_stop = False
    ambiguous = False
    protection_activated = False

    for j in range(entry_idx, end_idx + 1):
        if protection_activated:
            prior_2h_low = trailing_low_before_bar(df, j, TRAIL_2H_LOOKBACK_BARS)
            if np.isfinite(prior_2h_low):
                trail_stop = max(active_stop, entry_price, prior_2h_low)
                if trail_stop > active_stop:
                    active_stop = trail_stop
                    stop_stage = "structure_2h_trail_stop" if trail_stop > entry_price else "breakeven_stop"
                    max_stop_price = max(max_stop_price, active_stop)

        bar = df.iloc[j]
        low = float(bar["low"])
        high = float(bar["high"])
        stop_touch = low <= active_stop
        target_1r_touch = high >= target_1r

        if stop_touch and (not protection_activated) and target_1r_touch:
            ambiguous = True
            hit_stop = True
            exit_price = active_stop
            exit_reason = "ambiguous_initial_stop_first"
            bars_held = j - entry_idx
            break
        if stop_touch:
            hit_stop = True
            exit_price = active_stop
            exit_reason = stop_stage
            bars_held = j - entry_idx
            break
        if target_1r_touch and not protection_activated:
            hit_1r = True
            protection_activated = True
            active_stop = max(active_stop, entry_price)
            stop_stage = "breakeven_stop"
            max_stop_price = max(max_stop_price, active_stop)
        elif (not protection_activated) and (j - entry_idx >= LAUNCH_DEADLINE_BARS):
            exit_price = float(bar["close"])
            exit_reason = "launch_deadline_1h_no_1r"
            bars_held = j - entry_idx
            break
        if high >= entry_price + 2.0 * risk_abs:
            hit_2r = True

    return finalize_path(
        df=df,
        entry_idx=entry_idx,
        entry_price=entry_price,
        risk_abs=risk_abs,
        scheduled_end_idx=end_idx,
        exit_price=exit_price,
        exit_reason=exit_reason,
        bars_held=bars_held,
        hit_1r=hit_1r,
        hit_2r=hit_2r,
        hit_stop=hit_stop,
        ambiguous=ambiguous,
        protection_activated=protection_activated,
        max_stop_price=max_stop_price,
    )


def summarize_trades(df: pd.DataFrame, group_cols: list[str]) -> pd.DataFrame:
    rows: list[dict[str, object]] = []
    if df.empty:
        return pd.DataFrame()
    for key, grp in df.groupby(group_cols, dropna=False):
        if not isinstance(key, tuple):
            key = (key,)
        triggered = grp[grp["entry_triggered"]].copy()
        net = triggered["net_bps"].astype(float).dropna()
        net_r = triggered["net_r"].astype(float).dropna()
        row = dict(zip(group_cols, key))
        row.update(
            {
                "signals": int(len(grp)),
                "triggered": int(len(triggered)),
                "trigger_rate": float(len(triggered) / len(grp)) if len(grp) else np.nan,
                "profit_factor": profit_factor(net),
                "mean_net_bps": float(net.mean()) if len(net) else np.nan,
                "median_net_bps": float(net.median()) if len(net) else np.nan,
                "winrate": float((net > 0).mean()) if len(net) else np.nan,
                "net_sum_bps": float(net.sum()) if len(net) else np.nan,
                "max_drawdown_pct": max_drawdown_pct(net),
                "r_profit_factor": profit_factor(net_r),
                "mean_net_r": float(net_r.mean()) if len(net_r) else np.nan,
                "median_net_r": float(net_r.median()) if len(net_r) else np.nan,
                "hit_1r_rate": float(triggered["hit_1r"].mean()) if len(triggered) else np.nan,
                "hit_2r_rate": float(triggered["hit_2r"].mean()) if len(triggered) else np.nan,
                "stop_rate": float(triggered["hit_stop"].mean()) if len(triggered) else np.nan,
                "ambiguous_rate": float(triggered["ambiguous"].mean()) if len(triggered) else np.nan,
                "protection_rate": float(triggered["protection_activated"].mean())
                if len(triggered) and "protection_activated" in triggered
                else np.nan,
                "median_risk_bps": float(triggered["risk_bps"].median()) if len(triggered) else np.nan,
                "median_bars_held": float(triggered["bars_held"].median()) if len(triggered) else np.nan,
                "mean_mfe_r": float(triggered["mfe_r"].mean()) if len(triggered) else np.nan,
                "median_capture_r": float(triggered["capture_r"].replace([np.inf, -np.inf], np.nan).median())
                if len(triggered)
                else np.nan,
            }
        )
        rows.append(row)
    return pd.DataFrame(rows)


def format_table(df: pd.DataFrame, cols: list[str], max_rows: int | None = None) -> str:
    view = df[cols].copy()
    if max_rows is not None:
        view = view.head(max_rows)
    for col in view.select_dtypes(include=["float64", "float32"]).columns:
        view[col] = view[col].round(4)
    return view.to_markdown(index=False)


def write_report(
    overall: pd.DataFrame,
    by_regime: pd.DataFrame,
    by_reason: pd.DataFrame,
    by_exit: pd.DataFrame,
    trades: pd.DataFrame,
) -> None:
    report = f"""# BTC Structure Regime Long V2 Management

Generated: 2026-06-21

## Boundary

This run is in-sample only. It rebuilds Signal K and regime features from bars after 2024-01-01 and evaluates only after 2024-01-04. No 2020-2023 out-of-sample rows are loaded into the research sample.

## Entry Logic

Entry selection is unchanged from Structure Regime Long V1:

1. Long Signal K: `body_pct >= 0.70`, current range >= prior 3-day rolling `q90`.
2. Regime allowed: `active_uptrend_acceptance`, `quiet_uptrend_acceptance`, `upper_value_rotation_or_extension`.
3. Structure event: close breaks prior 2h high, or Signal K itself tests rolling24 VWAP support and reclaims prior 1h high while closing above both VWAP anchors.
4. Same-leg de-duplication: keep the first structural claim unless a new leg, VWAP reclaim, or 2h reset appears.
5. Next-candle stop-entry at the Signal K high; cancel if the next candle does not trigger.

## Management Variants

- `v1_target2r_24b`: fixed 2R target, initial stop at Signal K low, max hold 24 bars.
- `v2_1r_breakeven_1htrail_96b`: no fixed target. Initial stop stays at Signal K low. After price reaches +1R, stop moves to breakeven and then follows the prior 1h low. Max hold is 96 bars, matching the 8h regime/VWAP session horizon.
- `v3_acceptance_fail_1htrail_96b`: same as V2, but before +1R, a close back below the stop-entry level exits the trade as a failed accepted breakout.
- `v4_1r_breakeven_2htrail_96b`: same as V2, but the post-1R structural trail follows the prior 2h low, matching the 2h breakout structure.
- `v5_1r_breakeven_2htrail_24h`: same as V4, but the safety time cap is one rolling24 VWAP cycle.
- `v6_trigger_close_confirm_2htrail_24h`: same as V5, but if the trigger candle itself closes back below the breakout level before +1R, exit at that close.
- `v7_trigger_low_stop_2htrail_24h`: same as V5, but after a trigger candle closes above the breakout level, the initial stop is tightened to the trigger candle low from the next bar onward.
- `v8_half_tp1_2htrail_24h`: same as V5, but realizes half the position at +1R and lets the remainder follow the 2h structure trail.
- `v9_launch_1h_or_exit_2htrail_24h`: same as V5, but if +1R is not reached within the first hour, exit at the current close.
- `v10_body_low_stop_2htrail_24h`: same as V5, but the initial stop is the bullish Signal K body low instead of the full candle low.

Stop updates use only completed bars before the current bar. Ambiguous same-bar initial stop/+1R cases are counted stop-first.

## Overall

{format_table(overall, ["variant", "sample", "signals", "triggered", "trigger_rate", "profit_factor", "mean_net_bps", "median_net_bps", "winrate", "max_drawdown_pct", "r_profit_factor", "mean_net_r", "median_net_r", "hit_1r_rate", "hit_2r_rate", "stop_rate", "protection_rate", "median_bars_held", "median_risk_bps"])}

## By Regime

{format_table(by_regime, ["variant", "regime_v2", "signals", "triggered", "profit_factor", "mean_net_bps", "median_net_bps", "winrate", "r_profit_factor", "mean_net_r", "hit_1r_rate", "hit_2r_rate", "stop_rate", "median_bars_held"], 50)}

## By Structure Reason

{format_table(by_reason, ["variant", "break_prior_2h_high", "reclaim_from_rolling24_support", "signals", "triggered", "profit_factor", "mean_net_bps", "median_net_bps", "winrate", "r_profit_factor", "mean_net_r", "hit_1r_rate", "hit_2r_rate", "stop_rate"], 30)}

## By Exit Reason

{format_table(by_exit, ["variant", "exit_reason", "trades", "mean_net_bps", "median_net_bps", "mean_net_r", "median_net_r", "mean_mfe_r"], 30)}

## Reading Boundary

If a management variant improves, it is evidence that trade management deserves the next frozen OOS validation. It is not permission to tune the trail length, warmup, allowed regimes, or structure buckets from this report.
"""
    (OUT_DIR / "BTC_STRUCTURE_REGIME_LONG_V2_MANAGEMENT_IS_REPORT.md").write_text(report, encoding="utf-8")


def summarize_by_exit(trades: pd.DataFrame) -> pd.DataFrame:
    triggered = trades[trades["entry_triggered"]].copy()
    rows: list[dict[str, object]] = []
    for (variant, reason), grp in triggered.groupby(["variant", "exit_reason"], dropna=False):
        rows.append(
            {
                "variant": variant,
                "exit_reason": reason,
                "trades": int(len(grp)),
                "mean_net_bps": float(grp["net_bps"].mean()),
                "median_net_bps": float(grp["net_bps"].median()),
                "mean_net_r": float(grp["net_r"].mean()),
                "median_net_r": float(grp["net_r"].median()),
                "mean_mfe_r": float(grp["mfe_r"].mean()),
            }
        )
    return pd.DataFrame(rows).sort_values(["variant", "trades"], ascending=[True, False])


def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    df = load_is_frame()
    candidates = select_structure_candidates(df)
    trades = pd.concat(
        [
            simulate_trades(df, candidates, "v1_target2r_24b", "v1_target2r_24b"),
            simulate_trades(df, candidates, "v2_1r_breakeven_1htrail_96b", "v2_1r_breakeven_1htrail_96b"),
            simulate_trades(df, candidates, "v3_acceptance_fail_1htrail_96b", "v3_acceptance_fail_1htrail_96b"),
            simulate_trades(df, candidates, "v4_1r_breakeven_2htrail_96b", "v4_1r_breakeven_2htrail_96b"),
            simulate_trades(df, candidates, "v5_1r_breakeven_2htrail_24h", "v5_1r_breakeven_2htrail_24h"),
            simulate_trades(
                df,
                candidates,
                "v6_trigger_close_confirm_2htrail_24h",
                "v6_trigger_close_confirm_2htrail_24h",
            ),
            simulate_trades(df, candidates, "v7_trigger_low_stop_2htrail_24h", "v7_trigger_low_stop_2htrail_24h"),
            simulate_trades(df, candidates, "v8_half_tp1_2htrail_24h", "v8_half_tp1_2htrail_24h"),
            simulate_trades(df, candidates, "v9_launch_1h_or_exit_2htrail_24h", "v9_launch_1h_or_exit_2htrail_24h"),
            simulate_trades(df, candidates, "v10_body_low_stop_2htrail_24h", "v10_body_low_stop_2htrail_24h"),
        ],
        ignore_index=True,
    )

    overall = summarize_trades(trades, ["variant", "sample"]).sort_values("variant")
    by_regime = summarize_trades(trades, ["variant", "regime_v2"]).sort_values(
        ["variant", "profit_factor"], ascending=[True, False]
    )
    by_reason = summarize_trades(
        trades, ["variant", "break_prior_2h_high", "reclaim_from_rolling24_support"]
    ).sort_values(["variant", "break_prior_2h_high", "reclaim_from_rolling24_support"])
    by_exit = summarize_by_exit(trades)

    candidates.to_csv(OUT_DIR / "structure_regime_long_v2_selected_signals_is.csv", index=False, encoding="utf-8-sig")
    trades.to_csv(OUT_DIR / "structure_regime_long_v2_management_trades_is.csv", index=False, encoding="utf-8-sig")
    overall.to_csv(OUT_DIR / "structure_regime_long_v2_management_overall_is.csv", index=False, encoding="utf-8-sig")
    by_regime.to_csv(OUT_DIR / "structure_regime_long_v2_management_by_regime_is.csv", index=False, encoding="utf-8-sig")
    by_reason.to_csv(OUT_DIR / "structure_regime_long_v2_management_by_reason_is.csv", index=False, encoding="utf-8-sig")
    by_exit.to_csv(OUT_DIR / "structure_regime_long_v2_management_by_exit_is.csv", index=False, encoding="utf-8-sig")
    write_report(overall, by_regime, by_reason, by_exit, trades)

    print(f"Wrote {OUT_DIR}")
    print("overall")
    print(overall.round(6).to_string(index=False))
    print("by_exit")
    print(by_exit.round(6).to_string(index=False))


if __name__ == "__main__":
    main()
