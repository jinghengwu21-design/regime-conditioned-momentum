from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

import numpy as np
import pandas as pd

from .core import RegimeRecognitionError, attach_state_asof
from .smoothing import CausalHysteresisConfig
from .xgboost import (
    DEFAULT_ROOT,
    DEFAULT_V3X_FAMILY_HYSTERESIS,
    DEFAULT_V3X_PATH,
    add_v3x_family_hysteresis,
    add_v3x_transition_risk,
    add_v3x_v2_aligned_axes,
    xgb_v3x_family,
)


REGIME_V4_VERSION = "regime_v4_ohlcv_structure_v0_2026_07_01"
DEFAULT_REGIME_V4_DIR = DEFAULT_ROOT / "research" / "market_regime_v4_2026-07-01"
DEFAULT_REGIME_V4_PATH = DEFAULT_REGIME_V4_DIR / "regime_v4_table.feather"
DEFAULT_REGIME_V4_SOURCE_PATH = DEFAULT_V3X_PATH
DEFAULT_REGIME_V4_SOURCE = "v3x_walkforward_stable_family_aligned_v2_vocabulary"

REGIME_V4_COLUMNS = [
    "date",
    "close",
    "v4_version",
    "v4_state_source",
    "regime_v4",
    "v4_state",
    "v4_trend_axis",
    "v4_vol_axis",
    "v4_participation_axis",
    "v4_value_axis",
    "v4_vwap_agreement",
    "v4_family",
    "v4_raw_family",
    "v4_raw_state",
    "v4_family_state_agrees",
    "v4_confidence",
    "v4_entropy",
    "v4_quality",
    "v4_state_age_bars",
    "v4_family_age_bars",
    "v4_family_pending_age_bars",
    "v4_family_switch_delay_bars",
    "v4_transition_risk_score",
    "v4_transition_risk_bucket",
    "v4_use_boundary",
    "v4_context_quality",
    "v4_available_at",
    "v4_source_train_end",
    "v4_source_predict_start",
    "v4_source_predict_end",
    "artifact_latest_utc",
    "artifact_age_hours",
    "artifact_is_fresh",
]


@dataclass(frozen=True)
class RegimeV4Config:
    """
    Fixed V4 packaging config.

    V4 is the deployable-facing name for the current V3X-derived recognizer.
    It keeps the OHLCV/K-line/price-structure source, emits V2-compatible axes,
    and makes completed-bar availability explicit for strategy consumption.
    """

    hysteresis: CausalHysteresisConfig = field(default_factory=lambda: DEFAULT_V3X_FAMILY_HYSTERESIS)
    version: str = REGIME_V4_VERSION
    source_name: str = DEFAULT_REGIME_V4_SOURCE
    availability_offset: str | pd.Timedelta = "5min"
    freshness_reference_time: pd.Timestamp | None = None
    stale_after_hours: float = 48.0
    context_min_confidence: float = 0.70
    context_max_entropy: float = 0.45

    def availability_timedelta(self) -> pd.Timedelta:
        return pd.Timedelta(self.availability_offset)

    def reference_time_utc(self) -> pd.Timestamp:
        if self.freshness_reference_time is None:
            return pd.Timestamp.now(tz="UTC")
        timestamp = pd.Timestamp(self.freshness_reference_time)
        if timestamp.tzinfo is None:
            return timestamp.tz_localize("UTC")
        return timestamp.tz_convert("UTC")


def _require_columns(frame: pd.DataFrame, columns: list[str]) -> None:
    missing = [col for col in columns if col not in frame.columns]
    if missing:
        raise RegimeRecognitionError(f"Missing columns for Regime V4: {missing}")


def _read_table(path: str | Path) -> pd.DataFrame:
    source = Path(path)
    if source.suffix.lower() == ".feather":
        frame = pd.read_feather(source)
    elif source.suffix.lower() == ".csv":
        frame = pd.read_csv(source)
    else:
        raise RegimeRecognitionError(f"Unsupported Regime V4 source format: {source}")
    return frame


def _age_since_change(series: pd.Series) -> pd.Series:
    labels = series.astype("string")
    run_id = labels.ne(labels.shift()).cumsum()
    return labels.groupby(run_id, dropna=False).cumcount().add(1).astype("int64")


def _v4_use_boundary(frame: pd.DataFrame, config: RegimeV4Config) -> pd.Series:
    risk = frame["xgb_v3x_transition_risk_bucket"].astype("string")
    confidence = pd.to_numeric(frame["xgb_v3x_confidence"], errors="coerce")
    entropy = pd.to_numeric(frame["xgb_v3x_entropy"], errors="coerce")
    stable_quality = (
        frame["v4_family_state_agrees"].fillna(False).astype(bool)
        & confidence.ge(float(config.context_min_confidence)).fillna(False)
        & entropy.le(float(config.context_max_entropy)).fillna(False)
    )
    return pd.Series(
        np.select(
            [
                risk.isin(["high_transition_risk", "elevated_transition_risk"]).to_numpy(dtype=bool),
                risk.eq("watch_transition_risk").to_numpy(dtype=bool),
                (risk.eq("stable_context") & stable_quality).to_numpy(dtype=bool),
            ],
            [
                "transition_review_only",
                "risk_context_only",
                "context_ok",
            ],
            default="review_only",
        ),
        index=frame.index,
        dtype="string",
    )


def _v4_context_quality(frame: pd.DataFrame, config: RegimeV4Config) -> pd.Series:
    confidence = pd.to_numeric(frame["xgb_v3x_confidence"], errors="coerce")
    entropy = pd.to_numeric(frame["xgb_v3x_entropy"], errors="coerce")
    risk = frame["xgb_v3x_transition_risk_bucket"].astype("string")
    family_agrees = frame["v4_family_state_agrees"].fillna(False).astype(bool)
    high_quality = (
        confidence.ge(float(config.context_min_confidence)).fillna(False)
        & entropy.le(float(config.context_max_entropy)).fillna(False)
        & family_agrees
        & risk.eq("stable_context")
    )
    medium_quality = confidence.ge(0.55).fillna(False) & entropy.le(0.60).fillna(False)
    return pd.Series(
        np.select(
            [
                high_quality.to_numpy(dtype=bool),
                (medium_quality & risk.eq("stable_context")).to_numpy(dtype=bool),
                risk.ne("stable_context").to_numpy(dtype=bool),
            ],
            [
                "high_confidence_stable_context",
                "medium_confidence_stable_context",
                "transition_or_risk_context",
            ],
            default="review_or_low_confidence",
        ),
        index=frame.index,
        dtype="string",
    )


def build_regime_v4_table(
    source: pd.DataFrame | str | Path = DEFAULT_REGIME_V4_SOURCE_PATH,
    *,
    config: RegimeV4Config | None = None,
) -> pd.DataFrame:
    """
    Build the fixed V4 state table from a walk-forward V3X prediction table.

    This function does not train a model. It packages completed-bar V3X labels
    into V2-compatible V4 fields, adds causal hysteresis and transition-risk
    sidecars, and emits an explicit next-bar availability timestamp.
    """

    cfg = config or RegimeV4Config()
    frame = _read_table(source) if isinstance(source, (str, Path)) else source.copy()
    required = [
        "date",
        "xgb_v3x_state",
        "xgb_v3x_confidence",
        "xgb_v3x_entropy",
        "xgb_v3x_quality",
    ]
    _require_columns(frame, required)
    frame["date"] = pd.to_datetime(frame["date"], utc=True)
    frame = frame.sort_values("date").reset_index(drop=True)

    if "xgb_v3x_family" not in frame.columns:
        frame["xgb_v3x_family"] = frame["xgb_v3x_state"].map(xgb_v3x_family)
    frame = add_v3x_family_hysteresis(frame, config=cfg.hysteresis)
    frame = add_v3x_transition_risk(frame, hysteresis_config=cfg.hysteresis)
    frame = add_v3x_v2_aligned_axes(
        frame,
        state_col="xgb_v3x_state",
        family_col="xgb_v3x_family_stable",
        output_prefix="v4",
    )

    out = pd.DataFrame(index=frame.index)
    out["date"] = frame["date"]
    out["close"] = pd.to_numeric(frame["close"], errors="coerce") if "close" in frame.columns else np.nan
    out["v4_version"] = cfg.version
    out["v4_state_source"] = cfg.source_name
    out["regime_v4"] = frame["v4_regime_v2"].astype("string")
    out["v4_state"] = out["regime_v4"]
    out["v4_trend_axis"] = frame["v4_trend_axis"].astype("string")
    out["v4_vol_axis"] = frame["v4_vol_axis"].astype("string")
    out["v4_participation_axis"] = frame["v4_participation_axis"].astype("string")
    out["v4_value_axis"] = frame["v4_value_axis"].astype("string")
    out["v4_vwap_agreement"] = frame["v4_vwap_agreement"].astype("string")
    out["v4_family"] = frame["v4_family"].astype("string")
    out["v4_raw_family"] = frame["v4_raw_family"].astype("string")
    out["v4_raw_state"] = frame["xgb_v3x_state"].astype("string")
    out["v4_family_state_agrees"] = frame["v4_family_state_agrees"].fillna(False).astype(bool)
    out["v4_confidence"] = pd.to_numeric(frame["xgb_v3x_confidence"], errors="coerce")
    out["v4_entropy"] = pd.to_numeric(frame["xgb_v3x_entropy"], errors="coerce")
    out["v4_quality"] = frame["xgb_v3x_quality"].astype("string")
    out["v4_state_age_bars"] = _age_since_change(out["regime_v4"])
    out["v4_family_age_bars"] = pd.to_numeric(
        frame["xgb_v3x_family_stable_age_bars"],
        errors="coerce",
    ).astype("Int64")
    out["v4_family_pending_age_bars"] = pd.to_numeric(
        frame["xgb_v3x_family_stable_pending_age_bars"],
        errors="coerce",
    ).astype("Int64")
    out["v4_family_switch_delay_bars"] = pd.to_numeric(
        frame["xgb_v3x_family_stable_switch_delay_bars"],
        errors="coerce",
    )
    out["v4_transition_risk_score"] = pd.to_numeric(
        frame["xgb_v3x_transition_risk_score"],
        errors="coerce",
    )
    out["v4_transition_risk_bucket"] = frame["xgb_v3x_transition_risk_bucket"].astype("string")
    out["v4_use_boundary"] = _v4_use_boundary(frame, cfg)
    out["v4_context_quality"] = _v4_context_quality(frame, cfg)
    out["v4_available_at"] = out["date"] + cfg.availability_timedelta()

    for source_col, target_col in [
        ("train_end", "v4_source_train_end"),
        ("predict_start", "v4_source_predict_start"),
        ("predict_end", "v4_source_predict_end"),
    ]:
        if source_col in frame.columns:
            out[target_col] = pd.to_datetime(frame[source_col], utc=True)
        else:
            out[target_col] = pd.NaT

    latest = out["date"].max()
    reference = cfg.reference_time_utc()
    age_hours = (reference - latest).total_seconds() / 3600.0
    out["artifact_latest_utc"] = latest
    out["artifact_age_hours"] = float(age_hours)
    out["artifact_is_fresh"] = bool(age_hours <= float(cfg.stale_after_hours))
    return out[REGIME_V4_COLUMNS]


def load_regime_v4_table(path: str | Path = DEFAULT_REGIME_V4_PATH) -> pd.DataFrame:
    frame = _read_table(path)
    _require_columns(frame, REGIME_V4_COLUMNS)
    for col in [
        "date",
        "v4_available_at",
        "v4_source_train_end",
        "v4_source_predict_start",
        "v4_source_predict_end",
        "artifact_latest_utc",
    ]:
        frame[col] = pd.to_datetime(frame[col], utc=True)
    return frame.sort_values("date").reset_index(drop=True)


def prepare_regime_v4_for_asof(table: pd.DataFrame | str | Path = DEFAULT_REGIME_V4_PATH) -> pd.DataFrame:
    """Load/validate V4 and sort it by the causal availability timestamp."""

    frame = load_regime_v4_table(table) if isinstance(table, (str, Path)) else table.copy()
    _require_columns(frame, REGIME_V4_COLUMNS)
    frame["v4_available_at"] = pd.to_datetime(frame["v4_available_at"], utc=True)
    frame = frame.rename(columns={"date": "v4_state_date", "close": "v4_state_close"})
    return frame.sort_values("v4_available_at").reset_index(drop=True)


def attach_regime_v4_asof(
    dataframe: pd.DataFrame,
    table: pd.DataFrame | str | Path = DEFAULT_REGIME_V4_PATH,
    *,
    on: str = "date",
    use_available_at: bool = True,
    tolerance: pd.Timedelta | None = None,
) -> pd.DataFrame:
    """
    Attach V4 to another dataframe by causal as-of merge.

    By default this joins on `v4_available_at`, so a 5m state row is not visible
    until the next completed candle boundary.
    """

    state = prepare_regime_v4_for_asof(table) if use_available_at else load_regime_v4_table(table)
    return attach_state_asof(
        dataframe,
        state,
        left_on=on,
        right_on="v4_available_at" if use_available_at else "date",
        direction="backward",
        tolerance=tolerance,
    )


@dataclass
class RegimeV4TableRecognizer:
    """Reusable cached V4 table recognizer for strategies and research scripts."""

    state_path: Path = DEFAULT_REGIME_V4_PATH
    use_available_at: bool = True
    _cache: pd.DataFrame | None = field(default=None, init=False, repr=False)

    def labels(self) -> pd.DataFrame:
        if self._cache is None:
            self._cache = (
                prepare_regime_v4_for_asof(self.state_path)
                if self.use_available_at
                else load_regime_v4_table(self.state_path)
            )
        return self._cache

    def attach(self, dataframe: pd.DataFrame, *, on: str = "date") -> pd.DataFrame:
        return attach_state_asof(
            dataframe,
            self.labels(),
            left_on=on,
            right_on="v4_available_at" if self.use_available_at else "date",
            direction="backward",
        )
