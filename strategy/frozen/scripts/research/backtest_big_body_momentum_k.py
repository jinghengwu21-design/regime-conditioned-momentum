from __future__ import annotations

import argparse
import math
import re
from pathlib import Path

import matplotlib.dates as mdates
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd


TIMEFRAME_MINUTES = {
    "1m": 1,
    "5m": 5,
    "15m": 15,
    "1h": 60,
    "4h": 240,
    "1d": 1440,
}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Event-backtest large body momentum candles from Freqtrade OHLCV feather files."
    )
    parser.add_argument(
        "--data-dir",
        default=r"F:\freqtrade\user_data\data\okx\futures",
        help="Freqtrade OHLCV directory.",
    )
    parser.add_argument(
        "--out-dir",
        default=r"F:\freqtrade\research\active_btc_research_runs_v2\manual_big_body_k",
        help="Output directory.",
    )
    parser.add_argument("--timeframes", nargs="+", default=["5m", "15m"])
    parser.add_argument(
        "--pairs",
        nargs="*",
        default=None,
        help="Optional pair whitelist, for example BTC/USDT:USDT XAU/USDT:USDT.",
    )
    parser.add_argument("--body-pct", type=float, default=0.70)
    parser.add_argument("--range-zscore", type=float, default=1.0)
    parser.add_argument(
        "--range-filter",
        choices=[
            "meanstd_1d_z",
            "rolling_quantile",
            "robust_mad",
            "time_of_day_quantile",
        ],
        default="meanstd_1d_z",
        help="Range expansion filter. All variants are ex-ante and shifted by one candle.",
    )
    parser.add_argument(
        "--range-window-days",
        type=int,
        default=3,
        help="Window length in days for rolling_quantile and robust_mad filters.",
    )
    parser.add_argument(
        "--range-quantile",
        type=float,
        default=0.90,
        help="Quantile threshold for rolling_quantile and time_of_day_quantile filters.",
    )
    parser.add_argument(
        "--robust-range-zscore",
        type=float,
        default=2.0,
        help="Robust MAD zscore threshold for robust_mad filter.",
    )
    parser.add_argument(
        "--tod-lookback-days",
        type=int,
        default=20,
        help="Previous sessions used for time_of_day_quantile.",
    )
    parser.add_argument(
        "--recent-days",
        type=int,
        default=30,
        help="Lookback window for visual slices.",
    )
    parser.add_argument(
        "--fee-bps",
        type=float,
        default=6.0,
        help="Round-trip cost stress in bps. Used only for summary metrics.",
    )
    parser.add_argument(
        "--max-slices-per-file",
        type=int,
        default=12,
        help="Top recent signals by range_zscore to render per pair/timeframe.",
    )
    parser.add_argument(
        "--daily-slices",
        action="store_true",
        help="Render one chart per pair/timeframe/day for the recent window.",
    )
    parser.add_argument(
        "--show-ema20",
        action="store_true",
        help="Draw EMA20 on candlestick slice charts. Visualization only; never used for signals.",
    )
    return parser.parse_args()


def timeframe_to_minutes(timeframe: str) -> int:
    if timeframe not in TIMEFRAME_MINUTES:
        raise ValueError(f"Unsupported timeframe: {timeframe}")
    return TIMEFRAME_MINUTES[timeframe]


def default_zscore_window(timeframe: str) -> int:
    minutes = timeframe_to_minutes(timeframe)
    # One trading day of bars for intraday timeframes, with enough history for stable std.
    return max(48, int(round(24 * 60 / minutes)))


def parse_file(path: Path) -> tuple[str, str] | None:
    match = re.match(r"(?P<pair>.+_USDT_USDT)-(?P<timeframe>\d+[mhd])-futures\.feather$", path.name)
    if not match:
        return None
    pair = match.group("pair").replace("_", "/").replace("/USDT/USDT", "/USDT:USDT")
    return pair, match.group("timeframe")


def time_of_day_quantile_threshold(
    dates: pd.Series,
    values: pd.Series,
    timeframe: str,
    lookback_days: int,
    quantile: float,
) -> pd.Series:
    minutes = timeframe_to_minutes(timeframe)
    slots = (dates.dt.hour * 60 + dates.dt.minute) // minutes
    threshold = pd.Series(np.nan, index=values.index, dtype=float)
    index_series = pd.Series(values.index, index=values.index)
    for _, idx in index_series.groupby(slots).groups.items():
        positions = list(idx)
        series = values.iloc[positions]
        threshold.iloc[positions] = (
            series.rolling(lookback_days, min_periods=max(5, lookback_days // 2))
            .quantile(quantile)
            .shift(1)
            .values
        )
    return threshold


def add_signal_columns(
    df: pd.DataFrame,
    timeframe: str,
    body_pct_min: float,
    range_z_min: float,
    range_filter: str,
    range_window_days: int,
    range_quantile: float,
    robust_range_zscore: float,
    tod_lookback_days: int,
    range_confirm_mean_bars: int = 0,
    range_confirm_mean_multiple: float = 1.0,
) -> pd.DataFrame:
    out = df.copy()
    candle_range = (out["high"] - out["low"]).astype(float).mask(lambda s: s <= 0, np.nan)
    body_signed = (out["close"] - out["open"]).astype(float)
    body = body_signed.abs()
    upper = (out["high"] - out[["open", "close"]].max(axis=1)).astype(float)
    lower = (out[["open", "close"]].min(axis=1) - out["low"]).astype(float)

    window = default_zscore_window(timeframe)
    min_periods = max(30, window // 4)
    range_mean = candle_range.rolling(window, min_periods=min_periods).mean().shift(1)
    range_std = candle_range.rolling(window, min_periods=min_periods).std(ddof=0).shift(1)
    volume = out["volume"].astype(float)
    volume_mean = volume.rolling(window, min_periods=min_periods).mean().shift(1)
    volume_std = volume.rolling(window, min_periods=min_periods).std(ddof=0).shift(1)

    out["range"] = candle_range
    out["body"] = body
    out["upper"] = upper
    out["lower"] = lower
    out["body_pct"] = body / candle_range
    out["upper_pct"] = upper / candle_range
    out["lower_pct"] = lower / candle_range
    out["close_location"] = (out["close"] - out["low"]) / candle_range
    out["body_signed_pct"] = body_signed / candle_range
    out["range_zscore"] = (candle_range - range_mean) / range_std.replace(0, np.nan)
    out["volume_zscore"] = (volume - volume_mean) / volume_std.replace(0, np.nan)
    out["ema20"] = out["close"].ewm(span=20, adjust=False).mean()
    out["direction"] = np.sign(body_signed).astype(int)
    out["range_filter"] = range_filter

    if range_filter == "meanstd_1d_z":
        out["range_filter_threshold"] = range_z_min
        out["range_filter_score"] = out["range_zscore"]
        range_ok = out["range_zscore"] > range_z_min
    elif range_filter == "rolling_quantile":
        quantile_window = default_zscore_window(timeframe) * range_window_days
        quantile_min_periods = max(60, quantile_window // 4)
        threshold = candle_range.rolling(
            quantile_window,
            min_periods=quantile_min_periods,
        ).quantile(range_quantile).shift(1)
        out["range_filter_threshold"] = threshold
        out["range_filter_score"] = candle_range / threshold.replace(0, np.nan)
        range_ok = candle_range >= threshold
    elif range_filter == "robust_mad":
        robust_window = default_zscore_window(timeframe) * range_window_days
        robust_min_periods = max(60, robust_window // 4)
        median = candle_range.rolling(robust_window, min_periods=robust_min_periods).median().shift(1)
        mad = (candle_range - median).abs().rolling(
            robust_window,
            min_periods=robust_min_periods,
        ).median().shift(1)
        robust_z = (candle_range - median) / (1.4826 * mad.replace(0, np.nan))
        out["robust_range_zscore"] = robust_z
        out["range_filter_threshold"] = robust_range_zscore
        out["range_filter_score"] = robust_z
        range_ok = robust_z > robust_range_zscore
    elif range_filter == "time_of_day_quantile":
        threshold = time_of_day_quantile_threshold(
            out["date"],
            candle_range,
            timeframe,
            tod_lookback_days,
            range_quantile,
        )
        out["range_filter_threshold"] = threshold
        out["range_filter_score"] = candle_range / threshold.replace(0, np.nan)
        range_ok = candle_range >= threshold
    else:
        raise ValueError(f"Unsupported range_filter: {range_filter}")

    confirm_bars = int(range_confirm_mean_bars)
    if confirm_bars > 0:
        confirm_min_periods = max(10, confirm_bars // 2)
        confirm_threshold = (
            candle_range.rolling(confirm_bars, min_periods=confirm_min_periods).mean().shift(1)
            * float(range_confirm_mean_multiple)
        )
        out["range_confirm_mean_bars"] = confirm_bars
        out["range_confirm_mean_multiple"] = float(range_confirm_mean_multiple)
        out["range_confirm_mean_threshold"] = confirm_threshold
        out["range_confirm_mean_score"] = candle_range / confirm_threshold.replace(0, np.nan)
        out["range_confirm_mean_ok"] = candle_range >= confirm_threshold
        range_ok = range_ok & out["range_confirm_mean_ok"].fillna(False)
    else:
        out["range_confirm_mean_bars"] = 0
        out["range_confirm_mean_multiple"] = float(range_confirm_mean_multiple)
        out["range_confirm_mean_threshold"] = np.nan
        out["range_confirm_mean_score"] = np.nan
        out["range_confirm_mean_ok"] = True

    out["is_big_body_momentum_k"] = (
        (out["body_pct"] >= body_pct_min)
        & range_ok
        & (out["direction"] != 0)
    )
    return out


def event_returns(df: pd.DataFrame, horizons: list[int], fee_bps: float) -> pd.DataFrame:
    signal_idx = np.flatnonzero(df["is_big_body_momentum_k"].to_numpy())
    rows: list[dict[str, float | int | str | pd.Timestamp]] = []
    for idx in signal_idx:
        if idx + 1 >= len(df):
            continue
        direction = int(df.iloc[idx]["direction"])
        entry = float(df.iloc[idx + 1]["open"])
        if not np.isfinite(entry) or entry <= 0:
            continue
        row: dict[str, float | int | str | pd.Timestamp] = {
            "date": df.iloc[idx]["date"],
            "entry_date": df.iloc[idx + 1]["date"],
            "entry": entry,
            "direction": "long" if direction > 0 else "short",
            "open": float(df.iloc[idx]["open"]),
            "high": float(df.iloc[idx]["high"]),
            "low": float(df.iloc[idx]["low"]),
            "close": float(df.iloc[idx]["close"]),
            "volume": float(df.iloc[idx]["volume"]),
            "range": float(df.iloc[idx]["range"]),
            "body_pct": float(df.iloc[idx]["body_pct"]),
            "upper_pct": float(df.iloc[idx]["upper_pct"]),
            "lower_pct": float(df.iloc[idx]["lower_pct"]),
            "close_location": float(df.iloc[idx]["close_location"]),
        "range_zscore": float(df.iloc[idx]["range_zscore"]),
            "range_filter": str(df.iloc[idx]["range_filter"]),
            "range_filter_score": float(df.iloc[idx]["range_filter_score"])
            if np.isfinite(df.iloc[idx]["range_filter_score"])
            else np.nan,
            "range_filter_threshold": float(df.iloc[idx]["range_filter_threshold"])
            if np.isfinite(df.iloc[idx]["range_filter_threshold"])
            else np.nan,
            "volume_zscore": float(df.iloc[idx]["volume_zscore"])
            if np.isfinite(df.iloc[idx]["volume_zscore"])
            else np.nan,
        }
        for horizon in horizons:
            exit_idx = idx + horizon
            if exit_idx >= len(df):
                row[f"gross_bps_h{horizon}"] = np.nan
                row[f"net_bps_h{horizon}"] = np.nan
                continue
            exit_price = float(df.iloc[exit_idx]["close"])
            gross = direction * (exit_price / entry - 1.0) * 10000.0
            row[f"gross_bps_h{horizon}"] = gross
            row[f"net_bps_h{horizon}"] = gross - fee_bps
        rows.append(row)
    return pd.DataFrame(rows)


def summarize_events(events: pd.DataFrame, horizons: list[int]) -> pd.DataFrame:
    group_cols = ["pair", "timeframe", "direction"]
    rows: list[dict[str, float | int | str]] = []
    for keys, grp in events.groupby(group_cols, dropna=False):
        base = dict(zip(group_cols, keys))
        base["signals"] = int(len(grp))
        base["first_signal"] = grp["date"].min()
        base["last_signal"] = grp["date"].max()
        for horizon in horizons:
            col = f"net_bps_h{horizon}"
            values = grp[col].dropna()
            base[f"mean_net_bps_h{horizon}"] = float(values.mean()) if len(values) else np.nan
            base[f"median_net_bps_h{horizon}"] = float(values.median()) if len(values) else np.nan
            base[f"winrate_h{horizon}"] = float((values > 0).mean()) if len(values) else np.nan
            base[f"sample_h{horizon}"] = int(len(values))
        rows.append(base)
    return pd.DataFrame(rows)


def recent_counts(events: pd.DataFrame, recent_start: pd.Timestamp) -> pd.DataFrame:
    recent = events[events["date"] >= recent_start].copy()
    if recent.empty:
        return pd.DataFrame()
    recent["day"] = recent["date"].dt.floor("D")
    return (
        recent.groupby(["pair", "timeframe", "direction", "day"])
        .size()
        .reset_index(name="signals")
        .sort_values(["timeframe", "pair", "day", "direction"])
    )


def recent_counts_from_frames(
    events: pd.DataFrame,
    recent_frames: dict[tuple[str, str], pd.DataFrame],
) -> pd.DataFrame:
    rows = []
    for (pair, timeframe), df in recent_frames.items():
        if df.empty:
            continue
        frame_days = pd.Series(df["date"].dt.floor("D").unique()).sort_values()
        sub = events[(events["pair"] == pair) & (events["timeframe"] == timeframe)].copy()
        if sub.empty:
            for day in frame_days:
                rows.append(
                    {
                        "pair": pair,
                        "timeframe": timeframe,
                        "day": day,
                        "long": 0,
                        "short": 0,
                        "total": 0,
                    }
                )
            continue
        sub["day"] = sub["date"].dt.floor("D")
        grouped = sub.groupby(["day", "direction"]).size().unstack(fill_value=0)
        for day in frame_days:
            long_count = int(grouped.loc[day, "long"]) if day in grouped.index and "long" in grouped.columns else 0
            short_count = int(grouped.loc[day, "short"]) if day in grouped.index and "short" in grouped.columns else 0
            rows.append(
                {
                    "pair": pair,
                    "timeframe": timeframe,
                    "day": day,
                    "long": long_count,
                    "short": short_count,
                    "total": long_count + short_count,
                }
            )
    return pd.DataFrame(rows).sort_values(["timeframe", "pair", "day"])


def draw_candles(ax: plt.Axes, window: pd.DataFrame, signal_pos: int, show_ema20: bool = False) -> None:
    x = np.arange(len(window))
    width = 0.62
    for j, (_, row) in enumerate(window.iterrows()):
        color = "#0f8b4c" if row["close"] >= row["open"] else "#c43c39"
        ax.vlines(j, row["low"], row["high"], color=color, linewidth=0.8, alpha=0.9)
        y0 = min(row["open"], row["close"])
        height = abs(row["close"] - row["open"])
        if height == 0:
            ax.hlines(row["close"], j - width / 2, j + width / 2, color=color, linewidth=1.0)
        else:
            rect = plt.Rectangle(
                (j - width / 2, y0),
                width,
                height,
                facecolor=color,
                edgecolor=color,
                linewidth=0.7,
                alpha=0.88,
            )
            ax.add_patch(rect)
    if show_ema20 and "ema20" in window:
        ax.plot(x, window["ema20"], color="#2454a6", linewidth=1.1, alpha=0.95, label="EMA20")
    if 0 <= signal_pos < len(window):
        ax.axvspan(signal_pos - 0.5, signal_pos + 0.5, color="#f2b705", alpha=0.22)
        ax.axvline(signal_pos, color="#2f3542", linewidth=0.8, linestyle="--", alpha=0.8)
    ax.grid(True, axis="y", alpha=0.18)
    ax.set_xlim(-1, len(window))
    ax.tick_params(axis="x", labelsize=6)
    ax.tick_params(axis="y", labelsize=6)


def plot_contact_sheet(
    df: pd.DataFrame,
    events: pd.DataFrame,
    pair: str,
    timeframe: str,
    out_path: Path,
    max_slices: int,
    show_ema20: bool,
) -> bool:
    if events.empty:
        return False
    selected = events.sort_values("range_zscore", ascending=False).head(max_slices)
    if selected.empty:
        return False

    cols = 3
    rows = int(math.ceil(len(selected) / cols))
    fig, axes = plt.subplots(rows, cols, figsize=(17, max(4.0, rows * 3.2)), squeeze=False)
    before = 24
    after = 36
    date_to_idx = {ts: i for i, ts in enumerate(df["date"])}
    for ax in axes.ravel():
        ax.axis("off")
    for ax, (_, event) in zip(axes.ravel(), selected.iterrows()):
        idx = date_to_idx.get(event["date"])
        if idx is None:
            continue
        start = max(0, idx - before)
        end = min(len(df), idx + after + 1)
        window = df.iloc[start:end].copy()
        signal_pos = idx - start
        ax.axis("on")
        draw_candles(ax, window, signal_pos, show_ema20=show_ema20)
        side = "LONG" if event["direction"] == "long" else "SHORT"
        h12 = event.get("net_bps_h12", np.nan)
        ax.set_title(
            f"{event['date'].strftime('%m-%d %H:%M')} {side} "
            f"z={event['range_zscore']:.2f} body={event['body_pct']:.2f} h12={h12:.1f}bps",
            fontsize=8,
        )
        tick_positions = np.linspace(0, len(window) - 1, min(4, len(window)), dtype=int)
        ax.set_xticks(tick_positions)
        ax.set_xticklabels([window.iloc[t]["date"].strftime("%H:%M") for t in tick_positions])
    fig.suptitle(f"{pair} {timeframe} top recent large-body momentum K slices", fontsize=13)
    fig.tight_layout(rect=(0, 0, 1, 0.97))
    fig.savefig(out_path, dpi=160)
    plt.close(fig)
    return True


def plot_daily_slice(
    day_df: pd.DataFrame,
    day_events: pd.DataFrame,
    pair: str,
    timeframe: str,
    day: pd.Timestamp,
    out_path: Path,
    show_ema20: bool,
) -> bool:
    if day_df.empty:
        return False
    fig, ax = plt.subplots(1, 1, figsize=(18, 5.8))
    date_to_pos = {ts: i for i, ts in enumerate(day_df["date"])}
    draw_candles(ax, day_df, -10, show_ema20=show_ema20)

    long_events = day_events[day_events["direction"] == "long"]
    short_events = day_events[day_events["direction"] == "short"]
    for events, marker, color, label in [
        (long_events, "^", "#0f8b4c", "long big body K"),
        (short_events, "v", "#c43c39", "short big body K"),
    ]:
        xs = []
        ys = []
        for _, event in events.iterrows():
            pos = date_to_pos.get(event["date"])
            if pos is None:
                continue
            xs.append(pos)
            if event["direction"] == "long":
                ys.append(float(event["low"]) * 0.9995)
            else:
                ys.append(float(event["high"]) * 1.0005)
        if xs:
            ax.scatter(xs, ys, s=34, marker=marker, color=color, edgecolor="white", linewidth=0.4, zorder=5, label=label)

    if not day_events.empty:
        for _, event in day_events.sort_values("range_zscore", ascending=False).head(8).iterrows():
            pos = date_to_pos.get(event["date"])
            if pos is None:
                continue
            y = float(event["high"]) if event["direction"] == "short" else float(event["low"])
            offset = 14 if event["direction"] == "short" else -18
            ax.annotate(
                f"z={event['range_zscore']:.1f}",
                (pos, y),
                textcoords="offset points",
                xytext=(0, offset),
                ha="center",
                fontsize=6,
                color="#2f3542",
            )

    ticks = np.linspace(0, len(day_df) - 1, min(9, len(day_df)), dtype=int)
    ax.set_xticks(ticks)
    ax.set_xticklabels([day_df.iloc[t]["date"].strftime("%H:%M") for t in ticks])
    ax.set_title(
        f"{pair} {timeframe} {day.strftime('%Y-%m-%d')} "
        f"big body K: long={len(long_events)} short={len(short_events)} total={len(day_events)}",
        fontsize=12,
    )
    handles, labels = ax.get_legend_handles_labels()
    if handles:
        ax.legend(loc="upper left", fontsize=8)
    fig.tight_layout()
    fig.savefig(out_path, dpi=150)
    plt.close(fig)
    return True


def plot_daily_slices(
    recent_frames: dict[tuple[str, str], pd.DataFrame],
    events: pd.DataFrame,
    out_dir: Path,
    show_ema20: bool,
) -> list[Path]:
    rendered: list[Path] = []
    out_dir.mkdir(parents=True, exist_ok=True)
    for (pair, timeframe), df in sorted(recent_frames.items()):
        if df.empty:
            continue
        pair_events = events[(events["pair"] == pair) & (events["timeframe"] == timeframe)]
        days = pd.Series(df["date"].dt.floor("D").unique()).sort_values()
        safe_pair = pair.replace("/", "_").replace(":", "_")
        for day in days:
            day = pd.Timestamp(day)
            day_df = df[df["date"].dt.floor("D") == day].reset_index(drop=True)
            day_events = pair_events[pair_events["date"].dt.floor("D") == day]
            out_path = out_dir / f"{safe_pair}_{timeframe}_{day.strftime('%Y-%m-%d')}.png"
            if plot_daily_slice(day_df, day_events, pair, timeframe, day, out_path, show_ema20=show_ema20):
                rendered.append(out_path)
    return rendered


def plot_recent_overview(frames: dict[tuple[str, str], pd.DataFrame], events: pd.DataFrame, timeframe: str, out_path: Path) -> bool:
    items = [(pair, df) for (pair, tf), df in frames.items() if tf == timeframe]
    if not items:
        return False
    cols = 2
    rows = int(math.ceil(len(items) / cols))
    fig, axes = plt.subplots(rows, cols, figsize=(17, max(5, rows * 2.9)), squeeze=False)
    for ax in axes.ravel():
        ax.axis("off")
    for ax, (pair, df) in zip(axes.ravel(), items):
        ax.axis("on")
        if df.empty:
            continue
        normalized = df["close"] / df["close"].iloc[0] * 100.0
        ax.plot(df["date"], normalized, color="#30343f", linewidth=0.65, alpha=0.9)
        sub = events[(events["pair"] == pair) & (events["timeframe"] == timeframe)]
        plotted_signals = 0
        if not sub.empty:
            lookup = df[["date", "close"]].set_index("date")["close"]
            long_dates = sub[sub["direction"] == "long"]["date"]
            short_dates = sub[sub["direction"] == "short"]["date"]
            long_y = lookup.reindex(long_dates).dropna()
            short_y = lookup.reindex(short_dates).dropna()
            plotted_signals = len(long_y) + len(short_y)
            if not long_y.empty:
                ax.scatter(long_y.index, long_y / df["close"].iloc[0] * 100.0, s=8, color="#0f8b4c", alpha=0.7)
            if not short_y.empty:
                ax.scatter(short_y.index, short_y / df["close"].iloc[0] * 100.0, s=8, color="#c43c39", alpha=0.7)
        ax.set_title(f"{pair} {timeframe} recent signals={plotted_signals}", fontsize=9)
        ax.grid(True, alpha=0.15)
        ax.xaxis.set_major_formatter(mdates.DateFormatter("%m-%d"))
        ax.tick_params(axis="x", labelsize=7)
        ax.tick_params(axis="y", labelsize=7)
    fig.suptitle(f"Recent large-body momentum K overview ({timeframe})", fontsize=14)
    fig.tight_layout(rect=(0, 0, 1, 0.97))
    fig.savefig(out_path, dpi=160)
    plt.close(fig)
    return True


def write_html_index(out_dir: Path, images: list[Path]) -> None:
    lines = [
        "<!doctype html>",
        "<meta charset='utf-8'>",
        "<title>Big Body Momentum K Slices</title>",
        "<style>body{font-family:Arial,sans-serif;margin:24px;background:#f8f8f8;color:#222}"
        "img{max-width:100%;border:1px solid #ddd;background:white;margin:12px 0}"
        "h2{margin-top:28px}</style>",
        "<h1>Big Body Momentum K Slices</h1>",
    ]
    for image in images:
        rel = image.relative_to(out_dir).as_posix()
        lines.append(f"<h2>{rel}</h2>")
        lines.append(f"<img src='{rel}' alt='{rel}'>")
    (out_dir / "screenshot_index.html").write_text("\n".join(lines), encoding="utf-8")


def main() -> None:
    args = parse_args()
    data_dir = Path(args.data_dir)
    out_dir = Path(args.out_dir)
    charts_dir = out_dir / "charts"
    slices_dir = charts_dir / "event_slices"
    out_dir.mkdir(parents=True, exist_ok=True)
    charts_dir.mkdir(parents=True, exist_ok=True)
    slices_dir.mkdir(parents=True, exist_ok=True)

    pair_filter = set(args.pairs) if args.pairs else None
    files = []
    for timeframe in args.timeframes:
        files.extend(sorted(data_dir.glob(f"*-{timeframe}-futures.feather")))

    horizons = [3, 6, 12, 24]
    all_events: list[pd.DataFrame] = []
    recent_frames: dict[tuple[str, str], pd.DataFrame] = {}
    rendered_images: list[Path] = []
    coverage_rows = []

    for path in files:
        parsed = parse_file(path)
        if parsed is None:
            continue
        pair, timeframe = parsed
        if pair_filter and pair not in pair_filter:
            continue
        df = pd.read_feather(path).sort_values("date").reset_index(drop=True)
        if df.empty:
            continue
        df = add_signal_columns(
            df,
            timeframe,
            args.body_pct,
            args.range_zscore,
            args.range_filter,
            args.range_window_days,
            args.range_quantile,
            args.robust_range_zscore,
            args.tod_lookback_days,
        )
        events = event_returns(df, horizons, args.fee_bps)
        if not events.empty:
            events.insert(0, "pair", pair)
            events.insert(1, "timeframe", timeframe)
            all_events.append(events)
        latest = df["date"].max()
        latest_day = latest.floor("D")
        recent_start = latest_day - pd.Timedelta(days=args.recent_days - 1)
        recent_df = df[df["date"] >= recent_start].reset_index(drop=True)
        recent_frames[(pair, timeframe)] = recent_df
        recent_events = events[events["date"] >= recent_start] if not events.empty else pd.DataFrame()

        safe_name = pair.replace("/", "_").replace(":", "_")
        image_path = slices_dir / f"{safe_name}_{timeframe}_top{args.max_slices_per_file}.png"
        if plot_contact_sheet(
            recent_df,
            recent_events,
            pair,
            timeframe,
            image_path,
            args.max_slices_per_file,
            show_ema20=args.show_ema20,
        ):
            rendered_images.append(image_path)

        coverage_rows.append(
            {
                "pair": pair,
                "timeframe": timeframe,
                "rows": len(df),
                "from": df["date"].min(),
                "to": latest,
                "signals_all": int(df["is_big_body_momentum_k"].sum()),
                "signals_recent": int(recent_df["is_big_body_momentum_k"].sum()),
                "zscore_window_bars": default_zscore_window(timeframe),
            }
        )

    if all_events:
        events_all = pd.concat(all_events, ignore_index=True)
    else:
        events_all = pd.DataFrame()

    events_all.to_csv(out_dir / "big_body_momentum_k_events.csv", index=False, encoding="utf-8-sig")
    pd.DataFrame(coverage_rows).to_csv(out_dir / "data_coverage_and_signal_counts.csv", index=False, encoding="utf-8-sig")

    if not events_all.empty:
        summary = summarize_events(events_all, horizons)
        summary.to_csv(out_dir / "event_backtest_summary_by_pair_direction.csv", index=False, encoding="utf-8-sig")
        latest_global = events_all["date"].max()
        recent_start_global = latest_global - pd.Timedelta(days=args.recent_days)
        recent_counts(events_all, recent_start_global).to_csv(
            out_dir / "recent_signal_counts_by_day.csv",
            index=False,
            encoding="utf-8-sig",
        )
        recent_counts_from_frames(events_all, recent_frames).to_csv(
            out_dir / "recent_signal_counts_by_pair_day.csv",
            index=False,
            encoding="utf-8-sig",
        )
        recent_events = events_all[events_all["date"] >= recent_start_global]
    else:
        summary = pd.DataFrame()
        recent_events = pd.DataFrame()

    for timeframe in args.timeframes:
        image_path = charts_dir / f"recent_{args.recent_days}d_overview_{timeframe}.png"
        if plot_recent_overview(recent_frames, events_all, timeframe, image_path):
            rendered_images.insert(0, image_path)

    if args.daily_slices and not events_all.empty:
        daily_images = plot_daily_slices(
            recent_frames,
            events_all,
            charts_dir / "daily_slices",
            show_ema20=args.show_ema20,
        )
        rendered_images.extend(daily_images)

    write_html_index(out_dir, rendered_images)

    report = [
        "# Big Body Momentum K Event Backtest",
        "",
        f"- body_pct_min: {args.body_pct}",
        f"- range_filter: {args.range_filter}",
        f"- range_zscore_min: {args.range_zscore}",
        f"- range_window_days: {args.range_window_days}",
        f"- range_quantile: {args.range_quantile}",
        f"- robust_range_zscore: {args.robust_range_zscore}",
        f"- tod_lookback_days: {args.tod_lookback_days}",
        f"- recent_days: {args.recent_days}",
        f"- fee_bps_roundtrip: {args.fee_bps}",
        f"- files_scanned: {len(files)}",
        f"- total_events: {len(events_all)}",
        "",
        "Outputs:",
        "- big_body_momentum_k_events.csv",
        "- event_backtest_summary_by_pair_direction.csv",
        "- data_coverage_and_signal_counts.csv",
        "- recent_signal_counts_by_day.csv",
        "- charts/recent_*_overview_*.png",
        "- charts/event_slices/*.png",
        "- screenshot_index.html",
        "",
        "Method:",
        "Signal candle is known only after its close. Event return enters at the next candle open,",
        "then exits at fixed holding horizons of 3, 6, 12, and 24 bars. Events are overlapping;",
        "this is a signal-definition study, not a portfolio execution model.",
    ]
    (out_dir / "README.md").write_text("\n".join(report), encoding="utf-8")

    print(f"out_dir={out_dir}")
    print(f"events={len(events_all)}")
    if not summary.empty:
        display_cols = ["pair", "timeframe", "direction", "signals", "mean_net_bps_h12", "winrate_h12"]
        print(summary[display_cols].sort_values(["timeframe", "pair", "direction"]).to_string(index=False))


if __name__ == "__main__":
    main()
