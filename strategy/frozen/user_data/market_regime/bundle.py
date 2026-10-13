from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
from pathlib import Path

import numpy as np
import pandas as pd

from .core import RegimeRecognitionError, attach_state_asof


DEFAULT_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_REGIME_BUNDLE_PATH = (
    DEFAULT_ROOT
    / "research"
    / "market_regime_component_review_2026-06-30"
    / "regime_component_bundle"
    / "regime_component_bundle.feather"
)
DEFAULT_PATH_QUALITY_COL = "quiet_path_quality_axis_stable_v3_w6_eff25_dir55"
BUNDLE_VERSION = "regime_bundle_v0_2026_07_01"
DEFAULT_BOUNDARY_SEVERITY = {
    "context_ok": 0,
    "disagreement_overlay_only": 1,
    "risk_context_only": 2,
    "transition_review_only": 3,
    "review_only": 4,
}

REQUIRED_COLUMNS = [
    "date",
    "close",
    "rule_trend_axis",
    "rule_vol_axis",
    "rule_participation_axis",
    "rule_value_axis",
    "xgb_v3x_state",
    "xgb_v3x_family",
    "xgb_v3x_family_stable",
    "xgb_v3x_confidence",
    "xgb_v3x_entropy",
    "xgb_v3x_state_age_bars",
    "xgb_v3x_family_stable_age_bars",
    "xgb_v3x_transition_risk_bucket",
    "bocpd_risk_bucket",
    "bocpd_expected_run_bars",
    "jm_simple_state",
    "consensus_bucket",
    "any_transition_watch",
    "any_transition_high",
]

BUNDLE_COLUMNS = [
    "date",
    "close",
    "component_version",
    "component_state",
    "component_state_source",
    "component_use_boundary",
    "component_trust_bucket",
    "transition_risk_bucket",
    "market_prototype",
    "consensus_bucket",
    "v3x_family_stable",
    "diagnostic_raw_v3x_family",
    "diagnostic_raw_v3x_state",
    "v2_trend_axis",
    "v2_vol_axis",
    "v2_participation_axis",
    "v2_value_axis",
    "quiet_path_quality_overlay",
    "quiet_path_quality_side",
    "xgb_v3x_confidence",
    "xgb_v3x_entropy",
    "xgb_v3x_state_age_bars",
    "xgb_v3x_family_stable_age_bars",
    "xgb_v3x_transition_risk_bucket",
    "bocpd_risk_bucket",
    "bocpd_expected_run_bars",
    "artifact_latest_utc",
    "artifact_age_hours",
    "artifact_is_fresh",
]


@dataclass(frozen=True)
class RegimeBundleConfig:
    """
    Fixed field contract for the deployable-facing regime context bundle.

    The bundle is still a market-state context object, not a strategy signal.
    It promotes persistent/simple state and uncertainty boundaries while keeping
    raw V3X labels under diagnostic field names.
    """

    freshness_reference_time: pd.Timestamp | None = None
    stale_after_hours: float = 48.0
    path_quality_col: str = DEFAULT_PATH_QUALITY_COL
    version: str = BUNDLE_VERSION

    def reference_time_utc(self) -> pd.Timestamp:
        if self.freshness_reference_time is None:
            return pd.Timestamp.now(tz="UTC")
        timestamp = pd.Timestamp(self.freshness_reference_time)
        if timestamp.tzinfo is None:
            return timestamp.tz_localize("UTC")
        return timestamp.tz_convert("UTC")


@dataclass(frozen=True)
class RegimeBundleRuntimeConfig:
    """
    Runtime-consumption guard for a completed-bar regime bundle.

    Riskier boundary changes are emitted immediately. Relaxations toward cleaner
    context require a completed-bar dwell period. This is a consumer-side gate,
    not a rewrite of the underlying market-state labels.
    """

    availability_offset: str | pd.Timedelta = "5min"
    relax_dwell_bars: int = 3
    boundary_severity: Mapping[str, int] = field(default_factory=lambda: DEFAULT_BOUNDARY_SEVERITY.copy())
    unknown_boundary: str = "review_only"
    reset_relax_on_state_change: bool = True
    require_fresh_artifact: bool = True

    def validate(self) -> None:
        if int(self.relax_dwell_bars) < 1:
            raise RegimeRecognitionError("relax_dwell_bars must be >= 1")
        if self.unknown_boundary not in self.boundary_severity:
            raise RegimeRecognitionError("unknown_boundary must exist in boundary_severity")
        missing = set(DEFAULT_BOUNDARY_SEVERITY) - set(self.boundary_severity)
        if missing:
            raise RegimeRecognitionError(f"Missing required runtime boundary severities: {sorted(missing)}")

    def availability_timedelta(self) -> pd.Timedelta:
        return pd.Timedelta(self.availability_offset)

    def severity_for(self, boundary: object) -> int:
        label = _clean_text(boundary)
        if label is None:
            label = self.unknown_boundary
        return int(self.boundary_severity.get(label, self.boundary_severity[self.unknown_boundary]))


def _require_columns(frame: pd.DataFrame, columns: list[str]) -> None:
    missing = [col for col in columns if col not in frame.columns]
    if missing:
        raise RegimeRecognitionError(f"Missing columns for regime bundle: {missing}")


def _clean_text(value: object) -> str | None:
    if pd.isna(value):
        return None
    label = str(value)
    if not label or label.lower() in {"nan", "none", "nat"}:
        return None
    return label


def _age_since_change(series: pd.Series) -> pd.Series:
    ages: list[int] = []
    previous: str | None = None
    age = 0
    for value in series:
        label = _clean_text(value)
        if label is None:
            age = age + 1 if previous is None else age + 1
        elif label != previous:
            previous = label
            age = 1
        else:
            age += 1
        ages.append(age)
    return pd.Series(ages, index=series.index, dtype="int64")


def _trust_bucket(consensus: pd.Series) -> pd.Series:
    label = consensus.astype("string")
    return pd.Series(
        np.select(
            [
                label.str.startswith("clear_", na=False).to_numpy(dtype=bool),
                label.str.contains("transition", regex=False, na=False).to_numpy(dtype=bool),
                label.eq("model_disagreement").to_numpy(dtype=bool),
                label.eq("active_mixed_pressure").to_numpy(dtype=bool),
            ],
            [
                "clear_context",
                "transition_uncertainty",
                "model_disagreement",
                "active_mixed_pressure",
            ],
            default="review_only",
        ),
        index=consensus.index,
        dtype="string",
    )


def _combined_transition_bucket(frame: pd.DataFrame) -> pd.Series:
    high = frame["any_transition_high"].fillna(False).astype(bool)
    watch = frame["any_transition_watch"].fillna(False).astype(bool)
    return pd.Series(
        np.select(
            [high, watch],
            ["high_transition_risk", "watch_transition_risk"],
            default="stable_context",
        ),
        index=frame.index,
        dtype="string",
    )


def _use_boundary(frame: pd.DataFrame, trust: pd.Series, transition: pd.Series) -> pd.Series:
    stable_transition = transition.eq("stable_context")
    clear = trust.eq("clear_context") & stable_transition
    disagreement = trust.eq("model_disagreement") & stable_transition
    mixed = trust.eq("active_mixed_pressure") & stable_transition
    return pd.Series(
        np.select(
            [
                clear.to_numpy(dtype=bool),
                disagreement.to_numpy(dtype=bool),
                mixed.to_numpy(dtype=bool),
                (trust.eq("transition_uncertainty") | ~stable_transition).to_numpy(dtype=bool),
            ],
            [
                "context_ok",
                "disagreement_overlay_only",
                "risk_context_only",
                "transition_review_only",
            ],
            default="review_only",
        ),
        index=frame.index,
        dtype="string",
    )


def _path_overlay(frame: pd.DataFrame, path_col: str) -> tuple[pd.Series, pd.Series]:
    if path_col not in frame.columns:
        none = pd.Series("none", index=frame.index, dtype="string")
        return none, none.copy()

    label = frame[path_col].astype("string")
    overlay = pd.Series(
        np.select(
            [
                label.eq("quiet_up_path_consistent").to_numpy(dtype=bool),
                label.eq("quiet_down_path_consistent").to_numpy(dtype=bool),
            ],
            [
                "quiet_up_path_consistent",
                "quiet_down_path_consistent",
            ],
            default="none",
        ),
        index=frame.index,
        dtype="string",
    )
    side = pd.Series(
        np.select(
            [
                overlay.eq("quiet_up_path_consistent").to_numpy(dtype=bool),
                overlay.eq("quiet_down_path_consistent").to_numpy(dtype=bool),
            ],
            ["up", "down"],
            default="none",
        ),
        index=frame.index,
        dtype="string",
    )
    return overlay, side


def build_regime_bundle(
    dataframe: pd.DataFrame,
    *,
    config: RegimeBundleConfig | None = None,
) -> pd.DataFrame:
    """
    Build a fixed market-state bundle from the latest consensus/path frame.

    The bundle deliberately uses `jm_simple_state` as `component_state`, because
    it is the persistent prototype. Raw V3X labels remain diagnostic fields.
    """

    cfg = config or RegimeBundleConfig()
    _require_columns(dataframe, REQUIRED_COLUMNS)

    frame = dataframe.copy()
    frame["date"] = pd.to_datetime(frame["date"], utc=True)
    frame = frame.sort_values("date").reset_index(drop=True)

    latest = frame["date"].max()
    reference_time = cfg.reference_time_utc()
    age_hours = (reference_time - latest).total_seconds() / 3600.0
    artifact_is_fresh = bool(age_hours <= float(cfg.stale_after_hours))

    trust = _trust_bucket(frame["consensus_bucket"])
    transition = _combined_transition_bucket(frame)
    use_boundary = _use_boundary(frame, trust, transition)
    overlay, overlay_side = _path_overlay(frame, cfg.path_quality_col)

    out = pd.DataFrame(index=frame.index)
    out["date"] = frame["date"]
    out["close"] = frame["close"].astype(float)
    out["component_version"] = cfg.version
    out["component_state"] = frame["jm_simple_state"].astype("string")
    out["component_state_source"] = "jumpmodel_p25"
    out["component_use_boundary"] = use_boundary
    out["component_trust_bucket"] = trust
    out["transition_risk_bucket"] = transition
    out["market_prototype"] = frame["jm_simple_state"].astype("string")
    out["consensus_bucket"] = frame["consensus_bucket"].astype("string")
    out["v3x_family_stable"] = frame["xgb_v3x_family_stable"].astype("string")
    out["diagnostic_raw_v3x_family"] = frame["xgb_v3x_family"].astype("string")
    out["diagnostic_raw_v3x_state"] = frame["xgb_v3x_state"].astype("string")
    out["v2_trend_axis"] = frame["rule_trend_axis"].astype("string")
    out["v2_vol_axis"] = frame["rule_vol_axis"].astype("string")
    out["v2_participation_axis"] = frame["rule_participation_axis"].astype("string")
    out["v2_value_axis"] = frame["rule_value_axis"].astype("string")
    out["quiet_path_quality_overlay"] = overlay
    out["quiet_path_quality_side"] = overlay_side
    out["xgb_v3x_confidence"] = pd.to_numeric(frame["xgb_v3x_confidence"], errors="coerce")
    out["xgb_v3x_entropy"] = pd.to_numeric(frame["xgb_v3x_entropy"], errors="coerce")
    out["xgb_v3x_state_age_bars"] = pd.to_numeric(frame["xgb_v3x_state_age_bars"], errors="coerce")
    out["xgb_v3x_family_stable_age_bars"] = pd.to_numeric(frame["xgb_v3x_family_stable_age_bars"], errors="coerce")
    out["xgb_v3x_transition_risk_bucket"] = frame["xgb_v3x_transition_risk_bucket"].astype("string")
    out["bocpd_risk_bucket"] = frame["bocpd_risk_bucket"].astype("string")
    out["bocpd_expected_run_bars"] = pd.to_numeric(frame["bocpd_expected_run_bars"], errors="coerce")
    out["artifact_latest_utc"] = latest
    out["artifact_age_hours"] = float(age_hours)
    out["artifact_is_fresh"] = artifact_is_fresh
    return out[BUNDLE_COLUMNS]


def load_regime_bundle(path: str | Path = DEFAULT_REGIME_BUNDLE_PATH) -> pd.DataFrame:
    """Load and validate a saved regime component bundle."""

    bundle_path = Path(path)
    if bundle_path.suffix.lower() == ".feather":
        frame = pd.read_feather(bundle_path)
    elif bundle_path.suffix.lower() == ".csv":
        frame = pd.read_csv(bundle_path)
    else:
        raise RegimeRecognitionError(f"Unsupported regime bundle format: {bundle_path}")
    _require_columns(frame, BUNDLE_COLUMNS)
    frame["date"] = pd.to_datetime(frame["date"], utc=True)
    return frame.sort_values("date").reset_index(drop=True)


def prepare_regime_bundle_for_asof(
    bundle: pd.DataFrame,
    *,
    config: RegimeBundleRuntimeConfig | None = None,
) -> pd.DataFrame:
    """
    Add an explicit availability timestamp for as-of consumption.

    The default offset is one 5m bar because this BTC bundle is built from
    completed 5m candles. Use a zero offset only for after-close chart review.
    """

    cfg = config or RegimeBundleRuntimeConfig()
    cfg.validate()
    _require_columns(bundle, BUNDLE_COLUMNS)
    out = bundle.copy()
    out["date"] = pd.to_datetime(out["date"], utc=True)
    out = out.rename(columns={"date": "component_state_date"})
    out["component_available_at"] = out["component_state_date"] + cfg.availability_timedelta()
    return out.sort_values("component_available_at").reset_index(drop=True)


def attach_regime_bundle_asof(
    dataframe: pd.DataFrame,
    bundle: pd.DataFrame | str | Path = DEFAULT_REGIME_BUNDLE_PATH,
    *,
    left_on: str = "date",
    tolerance: pd.Timedelta | str | None = None,
    config: RegimeBundleRuntimeConfig | None = None,
    add_runtime_columns: bool = True,
) -> pd.DataFrame:
    """
    Attach the regime bundle to a dataframe using causal as-of semantics.

    `component_available_at` is separated from `component_state_date` so live
    users can model when a completed-bar state is actually consumable.
    """

    if isinstance(bundle, (str, Path)):
        bundle_frame = load_regime_bundle(bundle)
    else:
        bundle_frame = bundle.copy()
    state = prepare_regime_bundle_for_asof(bundle_frame, config=config)
    tol = pd.Timedelta(tolerance) if tolerance is not None else None
    out = attach_state_asof(
        dataframe,
        state,
        left_on=left_on,
        right_on="component_available_at",
        direction="backward",
        tolerance=tol,
    )
    if add_runtime_columns:
        out = add_regime_bundle_runtime_columns(out, config=config)
    return out


def add_regime_bundle_runtime_columns(
    dataframe: pd.DataFrame,
    *,
    config: RegimeBundleRuntimeConfig | None = None,
    state_col: str = "component_state",
    boundary_col: str = "component_use_boundary",
    fresh_col: str = "artifact_is_fresh",
) -> pd.DataFrame:
    """
    Add causal runtime-consumption metadata to an attached regime bundle.

    The raw component fields are preserved. The runtime boundary delays only
    relaxations toward less restrictive context; riskier moves are immediate.
    """

    cfg = config or RegimeBundleRuntimeConfig()
    cfg.validate()
    required = [state_col, boundary_col]
    if cfg.require_fresh_artifact and fresh_col:
        required.append(fresh_col)
    _require_columns(dataframe, required)

    out = dataframe.copy()
    state = out[state_col].astype("string")
    raw_boundary = out[boundary_col].astype("string")
    out["component_runtime_state_age_bars"] = _age_since_change(state)
    out["component_runtime_raw_boundary_age_bars"] = _age_since_change(raw_boundary)

    runtime_values: list[str] = []
    changed_values: list[bool] = []
    age_values: list[int] = []
    pending_values: list[str | None] = []
    pending_age_values: list[int] = []
    reason_values: list[str] = []

    current: str | None = None
    current_age = 0
    pending: str | None = None
    pending_age = 0
    previous_state: str | None = None
    previous_output: str | None = None

    for idx, row in out.iterrows():
        row_state = _clean_text(row[state_col])
        raw = _clean_text(row[boundary_col]) or cfg.unknown_boundary
        if raw not in cfg.boundary_severity:
            raw = cfg.unknown_boundary
        if cfg.require_fresh_artifact and fresh_col and not bool(row.get(fresh_col, False)):
            raw = cfg.unknown_boundary

        state_changed = previous_state is not None and row_state != previous_state
        if cfg.reset_relax_on_state_change and state_changed:
            pending = None
            pending_age = 0

        if current is None:
            current = raw
            current_age = 1
            reason = "initialize"
        elif raw == current:
            current_age += 1
            pending = None
            pending_age = 0
            reason = "same_boundary"
        elif cfg.severity_for(raw) >= cfg.severity_for(current):
            current = raw
            current_age = 1
            pending = None
            pending_age = 0
            reason = "immediate_restrictive_change"
        else:
            if raw == pending:
                pending_age += 1
            else:
                pending = raw
                pending_age = 1
            if pending_age >= int(cfg.relax_dwell_bars):
                current = raw
                current_age = 1
                pending = None
                pending_age = 0
                reason = "accepted_relax_after_dwell"
            else:
                current_age += 1
                reason = "hold_relax_pending"

        runtime_values.append(current)
        changed = previous_output is not None and current != previous_output
        changed_values.append(changed)
        age_values.append(int(current_age))
        pending_values.append(pending)
        pending_age_values.append(int(pending_age))
        reason_values.append(reason)
        previous_state = row_state
        previous_output = current

    out["component_runtime_boundary"] = pd.Series(runtime_values, index=out.index, dtype="string")
    out["component_runtime_boundary_changed"] = changed_values
    out["component_runtime_boundary_age_bars"] = age_values
    out["component_runtime_pending_relax_boundary"] = pd.Series(pending_values, index=out.index, dtype="string")
    out["component_runtime_pending_relax_age_bars"] = pending_age_values
    out["component_runtime_boundary_reason"] = pd.Series(reason_values, index=out.index, dtype="string")
    out["component_runtime_context_ok"] = out["component_runtime_boundary"].eq("context_ok")
    out["component_runtime_review_required"] = ~out["component_runtime_context_ok"]
    return out
