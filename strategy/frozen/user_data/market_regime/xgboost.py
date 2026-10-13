from __future__ import annotations

from dataclasses import dataclass, field
import json
from pathlib import Path
import sys

import numpy as np
import pandas as pd

from .core import RegimeRecognitionError, attach_state_asof, normalize_ohlcv_frame, safe_divide
from .smoothing import (
    CausalHysteresisConfig,
    TransitionRiskConfig,
    add_transition_risk,
    apply_causal_hysteresis,
)
from .vwap import BARS_PER_DAY, BARS_PER_HOUR, build_regime_v2


DEFAULT_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_XGB_STATE_DIR = DEFAULT_ROOT / "research" / "btc_regime_xgb_state_v1_2026-06-25"
DEFAULT_V3X_PATH = (
    DEFAULT_ROOT
    / "research"
    / "btc_regime_v3x_walkforward_2026-06-26"
    / "btc_regime_v3x_walkforward_predictions.feather"
)

TARGETS = {
    "regime_v2": "xgb_regime_v2",
    "trend_axis": "xgb_trend_axis",
    "vol_axis": "xgb_vol_axis",
    "participation_axis": "xgb_participation_axis",
    "vwap_agreement": "xgb_vwap_agreement",
}

AXIS_PREFIXES = [
    "xgb_trend_axis",
    "xgb_vol_axis",
    "xgb_participation_axis",
    "xgb_vwap_agreement",
]
ALL_PREFIXES = ["xgb_regime_v2", *AXIS_PREFIXES]

CONFIRMED_MEAN_CONF = 0.75
STRONG_MEAN_CONF = 0.85
STRONG_MIN_CONF = 0.60

V3X_COLUMNS = [
    "date",
    "xgb_v3x_state",
    "xgb_v3x_confidence",
    "xgb_v3x_entropy",
    "xgb_v3x_quality",
]

V3X_ALIGNED_SUFFIXES = [
    "raw_family",
    "family",
    "family_state_agrees",
    "trend_axis",
    "vol_axis",
    "participation_axis",
    "value_axis",
    "vwap_agreement",
    "regime_v2",
    "source",
]
V3X_ALIGNED_AXIS_SUFFIXES = [
    "trend_axis",
    "vol_axis",
    "participation_axis",
    "value_axis",
    "vwap_agreement",
]
V3X_ALIGNED_REGIME_LABELS = {
    "active_uptrend_acceptance",
    "quiet_uptrend_acceptance",
    "active_downtrend_acceptance",
    "quiet_downtrend_acceptance",
    "compressed_balance_near_vwap",
    "upper_value_rotation_or_extension",
    "lower_value_rotation_or_extension",
    "balanced_rotation_near_vwap",
    "mixed_vwap_transition",
}

DEFAULT_V3X_FAMILY_HYSTERESIS = CausalHysteresisConfig(
    min_candidate_bars=3,
    min_current_dwell_bars=3,
    min_quality_bars=1,
    min_confidence=0.55,
    max_entropy=0.60,
    label_min_candidate_bars={"transition": 2},
)


def add_common_state_features(
    bars: pd.DataFrame,
    regime_v2: pd.DataFrame | None = None,
) -> pd.DataFrame:
    base = normalize_ohlcv_frame(bars)
    regimes = build_regime_v2(base) if regime_v2 is None else regime_v2.copy()
    regimes["date"] = pd.to_datetime(regimes["date"], utc=True)
    out = pd.merge_asof(
        base.sort_values("date"),
        regimes[
            [
                "date",
                "regime_v2",
                "trend_axis",
                "vol_axis",
                "participation_axis",
                "vwap_agreement",
                "session_vwap_pre",
                "rolling24_vwap_pre",
            ]
        ].sort_values("date"),
        on="date",
        direction="backward",
    )

    logret = np.log(out["close"] / out["close"].shift(1))
    prior_close = out["close"].shift(1)

    out["ret_1h_bps_pre_ext"] = (prior_close / out["close"].shift(BARS_PER_HOUR + 1) - 1.0) * 10000.0
    out["ret_4h_bps_pre_ext"] = (prior_close / out["close"].shift(4 * BARS_PER_HOUR + 1) - 1.0) * 10000.0
    out["ret_24h_bps_pre_ext"] = (prior_close / out["close"].shift(BARS_PER_DAY + 1) - 1.0) * 10000.0

    out["rv_1h_bps_pre"] = (
        logret.rolling(BARS_PER_HOUR, min_periods=8).std(ddof=0).shift(1)
        * np.sqrt(BARS_PER_HOUR)
        * 10000.0
    )
    out["rv_4h_bps_pre"] = (
        logret.rolling(4 * BARS_PER_HOUR, min_periods=24).std(ddof=0).shift(1)
        * np.sqrt(4 * BARS_PER_HOUR)
        * 10000.0
    )
    out["rv_24h_bps_pre"] = (
        logret.rolling(BARS_PER_DAY, min_periods=BARS_PER_DAY // 2).std(ddof=0).shift(1)
        * np.sqrt(BARS_PER_DAY)
        * 10000.0
    )

    out["rv_1h_median_30d_pre"] = (
        out["rv_1h_bps_pre"].rolling(BARS_PER_DAY * 30, min_periods=BARS_PER_DAY * 10).median().shift(1)
    )
    out["rv_4h_median_30d_pre"] = (
        out["rv_4h_bps_pre"].rolling(BARS_PER_DAY * 30, min_periods=BARS_PER_DAY * 10).median().shift(1)
    )
    out["rv_1h_ratio_30d_pre"] = safe_divide(out["rv_1h_bps_pre"], out["rv_1h_median_30d_pre"])
    out["rv_4h_ratio_30d_pre"] = safe_divide(out["rv_4h_bps_pre"], out["rv_4h_median_30d_pre"])

    vol_1h_pre = out["volume"].rolling(BARS_PER_HOUR, min_periods=8).sum().shift(1)
    out["volume_ratio_1h_30d_pre"] = safe_divide(
        vol_1h_pre,
        vol_1h_pre.rolling(BARS_PER_DAY * 30, min_periods=BARS_PER_DAY * 10).median().shift(1),
    )

    out["ret_1h_vol_units_pre"] = safe_divide(out["ret_1h_bps_pre_ext"], out["rv_1h_bps_pre"])
    out["ret_4h_vol_units_pre"] = safe_divide(out["ret_4h_bps_pre_ext"], out["rv_4h_bps_pre"])
    out["ret_24h_vol_units_pre"] = safe_divide(out["ret_24h_bps_pre_ext"], out["rv_24h_bps_pre"])
    for col in ["rv_1h_ratio_30d_pre", "rv_4h_ratio_30d_pre", "volume_ratio_1h_30d_pre"]:
        out[f"{col}_log"] = np.log(out[col].clip(lower=1e-6))
    return out


def add_xgb_state_features(
    bars: pd.DataFrame,
    regime_v2: pd.DataFrame | None = None,
) -> tuple[pd.DataFrame, list[str]]:
    out = add_common_state_features(bars, regime_v2)
    close = out["close"].astype(float)
    open_ = out["open"].astype(float)
    high = out["high"].astype(float)
    low = out["low"].astype(float)
    volume = out["volume"].astype(float)

    candle_range = (high - low).replace(0, np.nan)
    body = (close - open_).abs()
    upper = high - np.maximum(open_, close)
    lower = np.minimum(open_, close) - low
    out["prev_range_bps"] = (candle_range / close * 10000.0).shift(1)
    out["prev_body_pct"] = safe_divide(body, candle_range).shift(1)
    out["prev_upper_pct"] = safe_divide(upper, candle_range).shift(1)
    out["prev_lower_pct"] = safe_divide(lower, candle_range).shift(1)
    out["prev_close_location"] = safe_divide(close - low, candle_range).shift(1)

    range_median_3d_pre = candle_range.rolling(BARS_PER_DAY * 3, min_periods=BARS_PER_DAY).median().shift(1)
    out["prev_range_vs_3d_median"] = safe_divide(candle_range.shift(1), range_median_3d_pre)
    out["range_1h_median_vs_3d"] = safe_divide(
        candle_range.rolling(BARS_PER_HOUR, min_periods=8).median().shift(1),
        range_median_3d_pre,
    )
    out["range_4h_median_vs_3d"] = safe_divide(
        candle_range.rolling(BARS_PER_HOUR * 4, min_periods=24).median().shift(1),
        range_median_3d_pre,
    )

    for bars_count, name in [
        (3, "15m"),
        (BARS_PER_HOUR, "1h"),
        (BARS_PER_HOUR * 2, "2h"),
        (BARS_PER_HOUR * 4, "4h"),
        (BARS_PER_DAY, "24h"),
    ]:
        out[f"ret_{name}_bps_pre_xgb"] = (close.shift(1) / close.shift(bars_count + 1) - 1.0) * 10000.0
        path = close.diff().abs().rolling(bars_count, min_periods=max(2, bars_count // 2)).sum().shift(1)
        net = close.shift(1) - close.shift(bars_count + 1)
        out[f"efficiency_{name}_pre"] = safe_divide(net, path)

    ema20 = close.ewm(span=20, adjust=False).mean().shift(1)
    ema50 = close.ewm(span=50, adjust=False).mean().shift(1)
    ema200 = close.ewm(span=200, adjust=False).mean().shift(1)
    out["close_dist_ema20_bps_pre"] = (close.shift(1) / ema20 - 1.0) * 10000.0
    out["close_dist_ema50_bps_pre"] = (close.shift(1) / ema50 - 1.0) * 10000.0
    out["close_dist_ema200_bps_pre"] = (close.shift(1) / ema200 - 1.0) * 10000.0
    out["ema20_slope_1h_bps_pre"] = (ema20 / ema20.shift(BARS_PER_HOUR) - 1.0) * 10000.0
    out["ema50_slope_4h_bps_pre"] = (ema50 / ema50.shift(BARS_PER_HOUR * 4) - 1.0) * 10000.0

    vol_1h = volume.rolling(BARS_PER_HOUR, min_periods=8).sum().shift(1)
    vol_4h = volume.rolling(BARS_PER_HOUR * 4, min_periods=24).sum().shift(1)
    vol_1h_med_30d = vol_1h.rolling(BARS_PER_DAY * 30, min_periods=BARS_PER_DAY * 10).median().shift(1)
    vol_4h_med_30d = vol_4h.rolling(BARS_PER_DAY * 30, min_periods=BARS_PER_DAY * 10).median().shift(1)
    out["volume_1h_ratio_30d_pre_xgb"] = safe_divide(vol_1h, vol_1h_med_30d)
    out["volume_4h_ratio_30d_pre"] = safe_divide(vol_4h, vol_4h_med_30d)
    out["prev_volume_ratio_30d_pre"] = safe_divide(
        volume.shift(1),
        volume.rolling(BARS_PER_DAY * 30, min_periods=BARS_PER_DAY * 10).median().shift(1),
    )

    out["session_vwap_dist_bps_pre_xgb"] = (close.shift(1) / out["session_vwap_pre"] - 1.0) * 10000.0
    out["rolling24_vwap_dist_bps_pre_xgb"] = (close.shift(1) / out["rolling24_vwap_pre"] - 1.0) * 10000.0
    out["session_vwap_dist_range_units_pre_xgb"] = safe_divide(
        close.shift(1) - out["session_vwap_pre"],
        range_median_3d_pre,
    )
    out["rolling24_vwap_dist_range_units_pre_xgb"] = safe_divide(
        close.shift(1) - out["rolling24_vwap_pre"],
        range_median_3d_pre,
    )

    out["utc_hour"] = out["date"].dt.hour.astype(float)
    out["utc_dow"] = out["date"].dt.dayofweek.astype(float)
    out["hour_sin"] = np.sin(2.0 * np.pi * out["utc_hour"] / 24.0)
    out["hour_cos"] = np.cos(2.0 * np.pi * out["utc_hour"] / 24.0)
    out["dow_sin"] = np.sin(2.0 * np.pi * out["utc_dow"] / 7.0)
    out["dow_cos"] = np.cos(2.0 * np.pi * out["utc_dow"] / 7.0)

    features = [
        "ret_1h_bps_pre_ext",
        "ret_4h_bps_pre_ext",
        "ret_24h_bps_pre_ext",
        "rv_1h_bps_pre",
        "rv_4h_bps_pre",
        "rv_24h_bps_pre",
        "rv_1h_ratio_30d_pre",
        "rv_4h_ratio_30d_pre",
        "volume_ratio_1h_30d_pre",
        "ret_1h_vol_units_pre",
        "ret_4h_vol_units_pre",
        "ret_24h_vol_units_pre",
        "rv_1h_ratio_30d_pre_log",
        "rv_4h_ratio_30d_pre_log",
        "volume_ratio_1h_30d_pre_log",
        "prev_range_bps",
        "prev_body_pct",
        "prev_upper_pct",
        "prev_lower_pct",
        "prev_close_location",
        "prev_range_vs_3d_median",
        "range_1h_median_vs_3d",
        "range_4h_median_vs_3d",
        "ret_15m_bps_pre_xgb",
        "ret_1h_bps_pre_xgb",
        "ret_2h_bps_pre_xgb",
        "ret_4h_bps_pre_xgb",
        "ret_24h_bps_pre_xgb",
        "efficiency_15m_pre",
        "efficiency_1h_pre",
        "efficiency_2h_pre",
        "efficiency_4h_pre",
        "efficiency_24h_pre",
        "close_dist_ema20_bps_pre",
        "close_dist_ema50_bps_pre",
        "close_dist_ema200_bps_pre",
        "ema20_slope_1h_bps_pre",
        "ema50_slope_4h_bps_pre",
        "volume_1h_ratio_30d_pre_xgb",
        "volume_4h_ratio_30d_pre",
        "prev_volume_ratio_30d_pre",
        "session_vwap_dist_bps_pre_xgb",
        "rolling24_vwap_dist_bps_pre_xgb",
        "session_vwap_dist_range_units_pre_xgb",
        "rolling24_vwap_dist_range_units_pre_xgb",
        "hour_sin",
        "hour_cos",
        "dow_sin",
        "dow_cos",
    ]
    return out, features


def _load_xgb_classifier(xgb_deps: Path):
    if str(xgb_deps) not in sys.path:
        sys.path.append(str(xgb_deps))
    try:
        from xgboost import XGBClassifier
    except ModuleNotFoundError as exc:
        raise RegimeRecognitionError(
            f"xgboost is not importable. Expected local install under {xgb_deps}."
        ) from exc
    return XGBClassifier


def quality_from_parts(
    main_agree: pd.Series,
    axis_agree_count: pd.Series,
    mean_conf: pd.Series,
    min_conf: pd.Series,
) -> pd.Series:
    main_ok = main_agree.astype("boolean").fillna(False).astype(bool)
    strong = (
        main_ok
        & (axis_agree_count == 4)
        & (mean_conf >= STRONG_MEAN_CONF)
        & (min_conf >= STRONG_MIN_CONF)
    )
    confirmed = (
        main_ok
        & (axis_agree_count >= 3)
        & (mean_conf >= CONFIRMED_MEAN_CONF)
        & ~strong
    )
    model_challenge = (
        ~main_ok
        & (axis_agree_count >= 3)
        & (mean_conf >= CONFIRMED_MEAN_CONF)
    )
    return pd.Series(
        np.select(
            [strong, confirmed, model_challenge],
            ["strong_recognition", "confirmed_recognition", "model_challenge"],
            default="transition_or_ambiguous",
        ),
        index=main_agree.index,
    )


def add_v3_quality_columns(df: pd.DataFrame, *, agree_suffix: str = "agrees_v2") -> pd.DataFrame:
    out = df.copy()
    conf_cols = [f"{prefix}_confidence" for prefix in ALL_PREFIXES]
    axis_agree_cols = [f"{prefix}_{agree_suffix}" for prefix in AXIS_PREFIXES]
    main_agree_col = f"xgb_regime_v2_{agree_suffix}"
    missing = [col for col in [*conf_cols, *axis_agree_cols, main_agree_col, "regime_v2"] if col not in out.columns]
    if missing:
        raise RegimeRecognitionError(f"Missing columns for V3 quality layer: {missing}")

    out["v3_axis_agree_count"] = out[axis_agree_cols].astype("boolean").fillna(False).astype(bool).sum(axis=1)
    out["v3_confidence_mean"] = out[conf_cols].mean(axis=1)
    out["v3_confidence_min"] = out[conf_cols].min(axis=1)
    out["v3_state_quality"] = quality_from_parts(
        out[main_agree_col],
        out["v3_axis_agree_count"],
        out["v3_confidence_mean"],
        out["v3_confidence_min"],
    )
    warmup = (
        out["regime_v2"].astype(str).str.contains("unknown|warmup", case=False, regex=True)
        | out["v3_confidence_mean"].isna()
    )
    out.loc[warmup, "v3_state_quality"] = "warmup_unavailable"
    out["regime_v3"] = np.where(
        out["v3_state_quality"].isin(["strong_recognition", "confirmed_recognition"]),
        out["regime_v2"].astype(str),
        out["v3_state_quality"],
    )
    out["regime_v3_confirmed"] = out["v3_state_quality"].isin(
        ["strong_recognition", "confirmed_recognition"]
    )
    out["regime_v3_strong"] = out["v3_state_quality"].eq("strong_recognition")
    out["regime_v3_axis_signature"] = (
        out["trend_axis"].astype(str)
        + "|"
        + out["vol_axis"].astype(str)
        + "|"
        + out["participation_axis"].astype(str)
        + "|"
        + out["vwap_agreement"].astype(str)
    )
    out["regime_v3_strength_context"] = np.select(
        [
            out["regime_v3_confirmed"]
            & out["trend_axis"].eq("up")
            & out["vol_axis"].isin(["active", "shock"])
            & out["participation_axis"].isin(["normal", "high"]),
            out["regime_v3_confirmed"]
            & out["trend_axis"].eq("down")
            & out["vol_axis"].isin(["active", "shock"])
            & out["participation_axis"].isin(["normal", "high"]),
            out["regime_v3_confirmed"] & out["trend_axis"].eq("balance") & out["vol_axis"].eq("compressed"),
            out["regime_v3_confirmed"] & out["trend_axis"].eq("balance"),
        ],
        [
            "confirmed_strong_up_acceptance",
            "confirmed_strong_down_acceptance",
            "confirmed_compressed_balance",
            "confirmed_balance_or_rotation",
        ],
        default=np.where(out["regime_v3_confirmed"], "confirmed_other", out["v3_state_quality"]),
    )
    return out


@dataclass
class XGBoostRegimeV1Recognizer:
    """
    XGBoost recognition layer trained to reproduce `regime_v2` and its axes.

    The final models are loaded from the research artifact directory. This
    class predicts current market-state labels; it does not use future returns
    or strategy PnL.
    """

    model_dir: Path = field(default_factory=lambda: DEFAULT_XGB_STATE_DIR / "models")
    xgb_deps: Path = field(default_factory=lambda: DEFAULT_ROOT / ".deps" / "xgboost")

    def transform(self, bars: pd.DataFrame, *, include_v3: bool = True) -> pd.DataFrame:
        frame, features = add_xgb_state_features(bars)
        output_cols = ["date", "open", "high", "low", "close", "volume", *TARGETS.keys()]
        output = frame[output_cols].copy()
        valid_features = frame[features].replace([np.inf, -np.inf], np.nan)
        valid_mask = valid_features.notna().all(axis=1)

        XGBClassifier = _load_xgb_classifier(self.xgb_deps)
        for target, prefix in TARGETS.items():
            model_path = self.model_dir / f"{prefix}_final_model.json"
            classes_path = self.model_dir / f"{prefix}_final_classes.json"
            if not model_path.exists() or not classes_path.exists():
                raise RegimeRecognitionError(f"Missing XGB model artifacts for {prefix}: {model_path}")

            model = XGBClassifier()
            model.load_model(model_path)
            classes = np.array(json.loads(classes_path.read_text(encoding="utf-8")), dtype=str)
            pred_index = frame.index[valid_mask]
            proba = model.predict_proba(valid_features.loc[valid_mask, features])
            pred = classes[proba.argmax(axis=1)]
            confidence = proba.max(axis=1)
            output.loc[pred_index, f"{prefix}_pred"] = pred
            output.loc[pred_index, f"{prefix}_confidence"] = confidence
            output.loc[pred_index, f"{prefix}_agrees_v2"] = (
                output.loc[pred_index, target].astype(str).to_numpy() == pred
            )

        if include_v3:
            output = add_v3_quality_columns(output, agree_suffix="agrees_v2")
        return output


def xgb_v3x_family(state: object) -> str:
    label = str(state)
    if label.startswith("active_up_acceptance"):
        return "active_up"
    if label.startswith("quiet_up_acceptance"):
        return "quiet_up"
    if label.startswith("active_down_acceptance"):
        return "active_down"
    if label.startswith("quiet_down_acceptance"):
        return "quiet_down"
    if label.startswith("value_compression"):
        return "compression"
    if label.startswith("high_vol_transition"):
        return "transition"
    if "normal_normal" in label:
        return "value_rotation"
    return "other"


def _clean_label(value: object) -> str:
    if pd.isna(value):
        return ""
    label = str(value).strip()
    return "" if label.lower() in {"", "nan", "none", "nat", "<na>"} else label


def _v3x_vwap_agreement(value_axis: str, trend_axis: str) -> str:
    if value_axis == "above_value":
        return "above_both_vwap"
    if value_axis == "below_value":
        return "below_both_vwap"
    if value_axis == "near_value":
        return "near_both_vwap"
    if trend_axis == "up":
        return "mixed_above_value"
    if trend_axis == "down":
        return "mixed_below_value"
    return "mixed_or_warmup"


def _v3x_regime_v2_label(trend_axis: str, vol_axis: str, vwap_agreement: str) -> str:
    if trend_axis == "up" and vol_axis in {"active", "shock"}:
        return "active_uptrend_acceptance"
    if trend_axis == "up":
        return "quiet_uptrend_acceptance"
    if trend_axis == "down" and vol_axis in {"active", "shock"}:
        return "active_downtrend_acceptance"
    if trend_axis == "down":
        return "quiet_downtrend_acceptance"
    if vol_axis == "compressed" and vwap_agreement == "near_both_vwap":
        return "compressed_balance_near_vwap"
    if vwap_agreement in {"above_both_vwap", "mixed_above_value"}:
        return "upper_value_rotation_or_extension"
    if vwap_agreement in {"below_both_vwap", "mixed_below_value"}:
        return "lower_value_rotation_or_extension"
    if vwap_agreement == "near_both_vwap":
        return "balanced_rotation_near_vwap"
    return "mixed_vwap_transition"


def v3x_state_to_aligned_axes(state: object, family: object | None = None) -> dict[str, object]:
    """
    Translate a V3X state name into the V2 market-state vocabulary.

    This is a deterministic semantic bridge. It reads only the current V3X
    state/family labels and does not use future returns, trade outcomes, or PnL.
    """

    state_label = _clean_label(state)
    raw_family = xgb_v3x_family(state_label)
    family_label = _clean_label(family)
    if family_label not in {
        "active_up",
        "quiet_up",
        "active_down",
        "quiet_down",
        "compression",
        "transition",
        "value_rotation",
        "other",
    }:
        family_label = raw_family

    if family_label in {"active_up", "quiet_up"}:
        trend_axis = "up"
    elif family_label in {"active_down", "quiet_down"}:
        trend_axis = "down"
    else:
        trend_axis = "balance"

    if family_label in {"active_up", "active_down"}:
        vol_axis = "active"
    elif family_label == "compression":
        vol_axis = "compressed"
    elif family_label == "transition":
        vol_axis = "shock"
    else:
        vol_axis = "normal"

    if family_label in {"active_up", "active_down", "transition"}:
        participation_axis = "high"
    elif family_label == "compression":
        participation_axis = "low"
    else:
        participation_axis = "normal"

    if state_label.startswith("above_value"):
        value_axis = "above_value"
    elif state_label.startswith("below_value"):
        value_axis = "below_value"
    elif state_label.startswith("near_value") or state_label.startswith("value_compression"):
        value_axis = "near_value"
    elif state_label.startswith("mixed_value") or state_label.startswith("high_vol_transition"):
        value_axis = "mixed_value"
    elif state_label.startswith(("active_up", "quiet_up")):
        value_axis = "above_value"
    elif state_label.startswith(("active_down", "quiet_down")):
        value_axis = "below_value"
    else:
        value_axis = "mixed_value"

    vwap_agreement = _v3x_vwap_agreement(value_axis, trend_axis)
    regime_v2 = _v3x_regime_v2_label(trend_axis, vol_axis, vwap_agreement)
    family_state_agrees = family_label == raw_family
    if family_label == "transition" or raw_family == "transition":
        source = "transition_name_semantics_v0"
    elif family_state_agrees:
        source = "state_family_name_semantics_v0"
    else:
        source = "stable_family_with_raw_state_value_semantics_v0"

    return {
        "raw_family": raw_family,
        "family": family_label,
        "family_state_agrees": bool(family_state_agrees),
        "trend_axis": trend_axis,
        "vol_axis": vol_axis,
        "participation_axis": participation_axis,
        "value_axis": value_axis,
        "vwap_agreement": vwap_agreement,
        "regime_v2": regime_v2,
        "source": source,
    }


def add_v3x_v2_aligned_axes(
    frame: pd.DataFrame,
    *,
    state_col: str = "xgb_v3x_state",
    family_col: str | None = "xgb_v3x_family_stable",
    output_prefix: str = "v3x_aligned",
) -> pd.DataFrame:
    """
    Add V2-compatible semantic axes for a V3X state table.

    When a stable family column is supplied, trend/vol/participation use that
    stable family while value location still comes from the raw V3X state name.
    This keeps the deployable label less flickery without hiding raw-state
    disagreement from audit columns.
    """

    if state_col not in frame.columns:
        raise RegimeRecognitionError(f"Missing {state_col} for V3X/V2 axis alignment")

    out = frame.copy()
    if family_col is not None and family_col in out.columns:
        families = out[family_col]
    else:
        families = pd.Series([None] * len(out), index=out.index)
    records = [
        v3x_state_to_aligned_axes(state, family)
        for state, family in zip(out[state_col], families, strict=False)
    ]
    aligned = pd.DataFrame.from_records(records, index=out.index)
    for suffix in V3X_ALIGNED_SUFFIXES:
        out[f"{output_prefix}_{suffix}"] = aligned[suffix]
    return out


def load_v3x_state_table(path: str | Path = DEFAULT_V3X_PATH) -> pd.DataFrame:
    frame = pd.read_feather(path)
    missing = [col for col in V3X_COLUMNS if col not in frame.columns]
    if missing:
        raise RegimeRecognitionError(f"Missing V3X state columns: {missing}")
    out = frame[V3X_COLUMNS].copy()
    out["date"] = pd.to_datetime(out["date"], utc=True).astype("datetime64[ns, UTC]")
    out["xgb_v3x_family"] = out["xgb_v3x_state"].map(xgb_v3x_family)
    return out.sort_values("date").reset_index(drop=True)


def add_v3x_family_hysteresis(
    frame: pd.DataFrame,
    *,
    config: CausalHysteresisConfig | None = None,
) -> pd.DataFrame:
    """
    Add a causal, stable V3X family layer without mutating the raw state.

    The stable family is delayed until the candidate family has persisted. It
    never revises previous rows, so it is safe to attach in live or backtest
    pipelines after the completed-candle V3X table is available.
    """

    out = frame.copy()
    if "xgb_v3x_family" not in out.columns:
        if "xgb_v3x_state" not in out.columns:
            raise RegimeRecognitionError("Missing xgb_v3x_state or xgb_v3x_family for V3X hysteresis")
        out["xgb_v3x_family"] = out["xgb_v3x_state"].map(xgb_v3x_family)
    return apply_causal_hysteresis(
        out,
        label_col="xgb_v3x_family",
        confidence_col="xgb_v3x_confidence" if "xgb_v3x_confidence" in out.columns else None,
        entropy_col="xgb_v3x_entropy" if "xgb_v3x_entropy" in out.columns else None,
        output_col="xgb_v3x_family_stable",
        config=config or DEFAULT_V3X_FAMILY_HYSTERESIS,
    )


def add_v3x_transition_risk(
    frame: pd.DataFrame,
    *,
    hysteresis_config: CausalHysteresisConfig | None = None,
    risk_config: TransitionRiskConfig | None = None,
) -> pd.DataFrame:
    """
    Add causal transition-risk columns for the V3X family layer.

    The sidecar does not change raw or stable family labels. It only marks when
    the current stable label may be stale, recently switched, low-confidence, or
    flickery enough to deserve abstention or chart review.
    """

    out = frame.copy()
    if "xgb_v3x_family_stable" not in out.columns:
        out = add_v3x_family_hysteresis(out, config=hysteresis_config)
    return add_transition_risk(
        out,
        label_col="xgb_v3x_family",
        stable_col="xgb_v3x_family_stable",
        confidence_col="xgb_v3x_confidence" if "xgb_v3x_confidence" in out.columns else None,
        entropy_col="xgb_v3x_entropy" if "xgb_v3x_entropy" in out.columns else None,
        stable_age_col="xgb_v3x_family_stable_age_bars",
        pending_label_col="xgb_v3x_family_stable_pending_label",
        pending_age_col="xgb_v3x_family_stable_pending_age_bars",
        changed_col="xgb_v3x_family_stable_changed",
        output_prefix="xgb_v3x_transition",
        config=risk_config,
    )


@dataclass
class XGBoostV3XTableRecognizer:
    """Reusable as-of loader for the walk-forward XGB V3X state table."""

    state_path: Path = DEFAULT_V3X_PATH
    _cache: pd.DataFrame | None = field(default=None, init=False, repr=False)

    def labels(self) -> pd.DataFrame:
        if self._cache is None:
            self._cache = load_v3x_state_table(self.state_path)
        return self._cache

    def attach(self, dataframe: pd.DataFrame, *, on: str = "date") -> pd.DataFrame:
        return attach_state_asof(dataframe, self.labels(), left_on=on, right_on="date", direction="backward")
