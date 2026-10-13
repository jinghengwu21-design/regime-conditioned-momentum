from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd

from .core import normalize_ohlcv_frame, safe_divide


BARS_PER_HOUR = 12
BARS_PER_DAY = 288

VWAP_REGIME_COLUMNS = [
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


@dataclass(frozen=True)
class VWAPRegimeRecognizer:
    """
    Causal VWAP/range/volume market-state recognizer.

    It reproduces the existing BTC `regime_v2` semantics while living outside
    any strategy class. Every feature ending in `_pre` is built only from bars
    completed before the labelled row.
    """

    bars_per_hour: int = BARS_PER_HOUR
    bars_per_day: int = BARS_PER_DAY

    def add_vwap_features(self, dataframe: pd.DataFrame) -> pd.DataFrame:
        out = normalize_ohlcv_frame(dataframe)
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

        out["rolling24_pv_sum_pre"] = (
            pv.rolling(self.bars_per_day, min_periods=self.bars_per_day // 4).sum().shift(1)
        )
        out["rolling24_vol_sum_pre"] = (
            out["volume"].rolling(self.bars_per_day, min_periods=self.bars_per_day // 4).sum().shift(1)
        )
        out["rolling24_vwap_pre"] = safe_divide(out["rolling24_pv_sum_pre"], out["rolling24_vol_sum_pre"])
        out["rolling24_vwap_slope_1h_pre"] = (
            out["rolling24_vwap_pre"] - out["rolling24_vwap_pre"].shift(self.bars_per_hour)
        )
        return out

    def transform(self, dataframe: pd.DataFrame) -> pd.DataFrame:
        out = self.add_vwap_features(dataframe)
        prior_close = out["close"].shift(1)
        high_low_range = out["high"] - out["low"]
        logret = np.log(out["close"] / out["close"].shift(1))

        out["median_range_3d_pre"] = (
            high_low_range.rolling(self.bars_per_day * 3, min_periods=self.bars_per_day).median().shift(1)
        )
        out["median_range_1h_pre"] = (
            high_low_range.rolling(self.bars_per_hour, min_periods=8).median().shift(1)
        )
        out["range_ratio_1h_vs_3d_pre"] = safe_divide(out["median_range_1h_pre"], out["median_range_3d_pre"])

        out["ret_1h_bps_pre"] = (
            prior_close / out["close"].shift(self.bars_per_hour + 1) - 1.0
        ) * 10000.0
        out["ret_4h_bps_pre"] = (
            prior_close / out["close"].shift(self.bars_per_hour * 4 + 1) - 1.0
        ) * 10000.0
        out["ret_24h_bps_pre"] = (
            prior_close / out["close"].shift(self.bars_per_day + 1) - 1.0
        ) * 10000.0

        out["rv_1h_pre"] = (
            logret.rolling(self.bars_per_hour, min_periods=8).std(ddof=0).shift(1)
            * np.sqrt(self.bars_per_hour)
        )
        out["rv_24h_pre"] = (
            logret.rolling(self.bars_per_day, min_periods=self.bars_per_day // 2).std(ddof=0).shift(1)
            * np.sqrt(self.bars_per_day)
        )
        out["rv_ratio_1h_vs_24h_pre"] = safe_divide(out["rv_1h_pre"], out["rv_24h_pre"])

        out["rolling24_vwap_dist_range_units_pre"] = safe_divide(
            prior_close - out["rolling24_vwap_pre"],
            out["median_range_3d_pre"],
        )
        out["session_vwap_dist_range_units_pre"] = safe_divide(
            prior_close - out["session_vwap_pre"],
            out["median_range_3d_pre"],
        )
        out["rolling24_vwap_slope_1h_range_units_pre"] = safe_divide(
            out["rolling24_vwap_slope_1h_pre"],
            out["median_range_3d_pre"],
        )

        volume_1h_pre = out["volume"].rolling(self.bars_per_hour, min_periods=8).sum().shift(1)
        median_volume_1h_3d_pre = (
            volume_1h_pre.rolling(self.bars_per_day * 3, min_periods=self.bars_per_day).median().shift(1)
        )
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
                out["trend_axis"] == "up",
                (out["trend_axis"] == "down") & out["vol_axis"].isin(["active", "shock"]),
                out["trend_axis"] == "down",
                (out["vol_axis"] == "compressed") & (out["vwap_agreement"] == "near_both_vwap"),
                out["vwap_agreement"].isin(["above_both_vwap", "mixed_above_value"]),
                out["vwap_agreement"].isin(["below_both_vwap", "mixed_below_value"]),
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
        return out[VWAP_REGIME_COLUMNS]


def build_regime_v2(dataframe: pd.DataFrame) -> pd.DataFrame:
    return VWAPRegimeRecognizer().transform(dataframe)
