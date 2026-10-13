from __future__ import annotations

from dataclasses import dataclass, field
from collections.abc import Mapping

import numpy as np
import pandas as pd

from .core import RegimeRecognitionError


@dataclass(frozen=True)
class CausalHysteresisConfig:
    """
    Causal state persistence rule for noisy regime labels.

    A new label is accepted only after it has persisted for enough completed
    bars and the previous stable label has lived long enough. The algorithm
    never backfills old rows, so accepted switches are delayed rather than
    revised into the past.
    """

    min_candidate_bars: int = 3
    min_current_dwell_bars: int = 3
    min_quality_bars: int = 1
    min_confidence: float | None = None
    max_entropy: float | None = None
    label_min_candidate_bars: Mapping[str, int] = field(default_factory=dict)
    label_min_current_dwell_bars: Mapping[str, int] = field(default_factory=dict)
    label_min_quality_bars: Mapping[str, int] = field(default_factory=dict)
    missing_label: str = "unknown"

    def validate(self) -> None:
        int_fields = {
            "min_candidate_bars": self.min_candidate_bars,
            "min_current_dwell_bars": self.min_current_dwell_bars,
            "min_quality_bars": self.min_quality_bars,
        }
        bad = [name for name, value in int_fields.items() if int(value) < 1]
        if bad:
            raise RegimeRecognitionError(f"Hysteresis config values must be >= 1: {bad}")
        if self.min_confidence is not None and not 0.0 <= float(self.min_confidence) <= 1.0:
            raise RegimeRecognitionError("min_confidence must be between 0 and 1")
        if self.max_entropy is not None and float(self.max_entropy) < 0.0:
            raise RegimeRecognitionError("max_entropy must be non-negative")
        for name, mapping in [
            ("label_min_candidate_bars", self.label_min_candidate_bars),
            ("label_min_current_dwell_bars", self.label_min_current_dwell_bars),
            ("label_min_quality_bars", self.label_min_quality_bars),
        ]:
            bad_labels = [label for label, value in mapping.items() if int(value) < 1]
            if bad_labels:
                raise RegimeRecognitionError(f"{name} values must be >= 1: {bad_labels}")

    def candidate_bars_for(self, label: str) -> int:
        return int(self.label_min_candidate_bars.get(label, self.min_candidate_bars))

    def dwell_bars_for(self, label: str) -> int:
        return int(self.label_min_current_dwell_bars.get(label, self.min_current_dwell_bars))

    def quality_bars_for(self, label: str) -> int:
        return int(self.label_min_quality_bars.get(label, self.min_quality_bars))


@dataclass(frozen=True)
class TransitionRiskConfig:
    """
    Causal sidecar for state-switch risk.

    This is not a future-outcome label and not an alpha score. It summarizes
    whether the current stable state may be stale, noisy, or in transition
    using only labels and confidence available at the current completed bar.
    """

    pending_age_scale_bars: int = 3
    recent_stable_switch_bars: int = 3
    raw_flicker_bars: int = 2
    high_threshold: float = 0.70
    elevated_threshold: float = 0.45
    watch_threshold: float = 0.25
    pending_weight: float = 0.35
    recent_switch_weight: float = 0.20
    quality_weight: float = 0.25
    raw_flicker_weight: float = 0.20

    def validate(self) -> None:
        int_fields = {
            "pending_age_scale_bars": self.pending_age_scale_bars,
            "recent_stable_switch_bars": self.recent_stable_switch_bars,
            "raw_flicker_bars": self.raw_flicker_bars,
        }
        bad = [name for name, value in int_fields.items() if int(value) < 1]
        if bad:
            raise RegimeRecognitionError(f"Transition risk config values must be >= 1: {bad}")
        thresholds = [self.watch_threshold, self.elevated_threshold, self.high_threshold]
        if not all(0.0 <= float(value) <= 1.0 for value in thresholds):
            raise RegimeRecognitionError("Transition risk thresholds must be in [0, 1]")
        if thresholds != sorted(thresholds):
            raise RegimeRecognitionError("Transition risk thresholds must be ordered watch <= elevated <= high")
        weights = [
            self.pending_weight,
            self.recent_switch_weight,
            self.quality_weight,
            self.raw_flicker_weight,
        ]
        if any(float(weight) < 0.0 for weight in weights):
            raise RegimeRecognitionError("Transition risk weights must be non-negative")
        if sum(float(weight) for weight in weights) <= 0.0:
            raise RegimeRecognitionError("At least one transition risk weight must be positive")


def _clean_label(value: object) -> str | None:
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
        label = _clean_label(value)
        if label is None:
            age = age + 1 if previous is None else age + 1
        elif label != previous:
            previous = label
            age = 1
        else:
            age += 1
        ages.append(age)
    return pd.Series(ages, index=series.index, dtype="int64")


def _quality_ok(
    row: pd.Series,
    *,
    confidence_col: str | None,
    entropy_col: str | None,
    config: CausalHysteresisConfig,
) -> bool:
    if confidence_col and config.min_confidence is not None:
        confidence = row.get(confidence_col)
        if pd.isna(confidence) or float(confidence) < float(config.min_confidence):
            return False
    if entropy_col and config.max_entropy is not None:
        entropy = row.get(entropy_col)
        if pd.isna(entropy) or float(entropy) > float(config.max_entropy):
            return False
    return True


def apply_causal_hysteresis(
    dataframe: pd.DataFrame,
    *,
    label_col: str,
    confidence_col: str | None = None,
    entropy_col: str | None = None,
    output_col: str | None = None,
    config: CausalHysteresisConfig | None = None,
) -> pd.DataFrame:
    """
    Add a stable, causal label column to a regime table.

    This function only uses the current row and previously emitted labels. If a
    candidate label becomes stable after N bars, the switch is emitted on the
    current row; previous candidate rows keep the old stable label.
    """

    cfg = config or CausalHysteresisConfig()
    cfg.validate()
    required = [label_col]
    if confidence_col:
        required.append(confidence_col)
    if entropy_col:
        required.append(entropy_col)
    missing = [col for col in required if col not in dataframe.columns]
    if missing:
        raise RegimeRecognitionError(f"Missing columns for causal hysteresis: {missing}")

    out = dataframe.copy()
    stable_col = output_col or f"{label_col}_stable"
    changed_col = f"{stable_col}_changed"
    age_col = f"{stable_col}_age_bars"
    pending_col = f"{stable_col}_pending_label"
    pending_age_col = f"{stable_col}_pending_age_bars"
    pending_quality_age_col = f"{stable_col}_pending_quality_age_bars"
    delay_col = f"{stable_col}_switch_delay_bars"
    reason_col = f"{stable_col}_reason"

    stable_values: list[str] = []
    changed_values: list[bool] = []
    age_values: list[int] = []
    pending_values: list[str | None] = []
    pending_age_values: list[int] = []
    pending_quality_age_values: list[int] = []
    delay_values: list[float | None] = []
    reason_values: list[str] = []

    current: str | None = None
    current_age = 0
    pending: str | None = None
    pending_age = 0
    pending_quality_age = 0
    previous_output: str | None = None

    for _, row in out.iterrows():
        raw = _clean_label(row[label_col])
        quality_ok = _quality_ok(row, confidence_col=confidence_col, entropy_col=entropy_col, config=cfg)
        switched = False
        switch_delay: float | None = None

        if raw is None:
            if current is None:
                stable = cfg.missing_label
                current_age = 0
                reason = "missing_before_initial_state"
            else:
                current_age += 1
                stable = current
                reason = "hold_missing_candidate"
            pending = None
            pending_age = 0
            pending_quality_age = 0
        elif current is None:
            current = raw
            current_age = 1
            stable = current
            reason = "initialize"
        elif raw == current:
            current_age += 1
            stable = current
            pending = None
            pending_age = 0
            pending_quality_age = 0
            reason = "same_as_stable"
        else:
            if raw == pending:
                pending_age += 1
            else:
                pending = raw
                pending_age = 1
                pending_quality_age = 0

            if quality_ok:
                pending_quality_age += 1
            else:
                pending_quality_age = 0

            candidate_ready = pending_age >= cfg.candidate_bars_for(raw)
            quality_ready = pending_quality_age >= cfg.quality_bars_for(raw)
            dwell_ready = current_age >= cfg.dwell_bars_for(current)
            if candidate_ready and quality_ready and dwell_ready:
                current = raw
                current_age = 1
                stable = current
                switched = True
                switch_delay = float(pending_age - 1)
                pending = None
                pending_age = 0
                pending_quality_age = 0
                reason = "accepted_candidate"
            else:
                current_age += 1
                stable = current
                blocked = []
                if not candidate_ready:
                    blocked.append("candidate_age")
                if not quality_ready:
                    blocked.append("quality")
                if not dwell_ready:
                    blocked.append("current_dwell")
                reason = "hold_pending_" + "_".join(blocked)

        stable_values.append(stable)
        changed_values.append(previous_output is not None and switched and stable != previous_output)
        age_values.append(int(current_age))
        pending_values.append(pending)
        pending_age_values.append(int(pending_age))
        pending_quality_age_values.append(int(pending_quality_age))
        delay_values.append(switch_delay)
        reason_values.append(reason)
        previous_output = stable

    out[stable_col] = stable_values
    out[changed_col] = changed_values
    out[age_col] = age_values
    out[pending_col] = pending_values
    out[pending_age_col] = pending_age_values
    out[pending_quality_age_col] = pending_quality_age_values
    out[delay_col] = delay_values
    out[reason_col] = reason_values
    return out


def add_transition_risk(
    dataframe: pd.DataFrame,
    *,
    label_col: str,
    stable_col: str,
    confidence_col: str | None = None,
    entropy_col: str | None = None,
    stable_age_col: str | None = None,
    pending_label_col: str | None = None,
    pending_age_col: str | None = None,
    changed_col: str | None = None,
    output_prefix: str = "transition",
    config: TransitionRiskConfig | None = None,
) -> pd.DataFrame:
    """
    Add causal transition-risk columns to a state table.

    Components:
    - pending disagreement between raw and stable label;
    - recent stable-state switch;
    - low confidence / high entropy;
    - very young raw-label run.

    The result is deliberately heuristic and auditable. It should be compared
    against HMM/BOCPD-style baselines before being used as a hard rule.
    """

    cfg = config or TransitionRiskConfig()
    cfg.validate()
    required = [label_col, stable_col]
    for col in [confidence_col, entropy_col, stable_age_col, pending_label_col, pending_age_col, changed_col]:
        if col:
            required.append(col)
    missing = [col for col in required if col not in dataframe.columns]
    if missing:
        raise RegimeRecognitionError(f"Missing columns for transition risk: {missing}")

    out = dataframe.copy()
    raw = out[label_col].astype("string")
    stable = out[stable_col].astype("string")
    raw_age = _age_since_change(raw).astype(float)

    mismatch = raw.ne(stable).fillna(False).astype(bool)
    if pending_label_col:
        pending_active = out[pending_label_col].notna() | mismatch
    else:
        pending_active = mismatch

    if pending_age_col:
        pending_age = pd.to_numeric(out[pending_age_col], errors="coerce").fillna(0.0)
    else:
        pending_age = raw_age.where(pending_active, 0.0)
    pending_component = (pending_age / float(cfg.pending_age_scale_bars)).clip(0.0, 1.0)
    pending_component = pending_component.where(pending_active, 0.0)

    if stable_age_col:
        stable_age = pd.to_numeric(out[stable_age_col], errors="coerce").fillna(np.inf)
    else:
        stable_age = _age_since_change(stable).astype(float)
    if changed_col:
        stable_changed = out[changed_col].astype("boolean").fillna(False).astype(bool)
    else:
        stable_changed = stable.ne(stable.shift()).fillna(False).astype(bool)
    recent_component = (
        stable_changed | (stable_age <= float(cfg.recent_stable_switch_bars))
    ).astype(float)

    quality_parts: list[pd.Series] = []
    if confidence_col:
        confidence = pd.to_numeric(out[confidence_col], errors="coerce").clip(0.0, 1.0)
        quality_parts.append((1.0 - confidence).fillna(0.0))
    if entropy_col:
        entropy = pd.to_numeric(out[entropy_col], errors="coerce").clip(0.0, 1.0)
        quality_parts.append(entropy.fillna(0.0))
    if quality_parts:
        quality_component = pd.concat(quality_parts, axis=1).mean(axis=1)
    else:
        quality_component = pd.Series(0.0, index=out.index)

    raw_changed = raw.ne(raw.shift()).fillna(False).astype(bool)
    raw_flicker_component = (raw_changed | (raw_age <= float(cfg.raw_flicker_bars))).astype(float)

    total_weight = (
        float(cfg.pending_weight)
        + float(cfg.recent_switch_weight)
        + float(cfg.quality_weight)
        + float(cfg.raw_flicker_weight)
    )
    score = (
        pending_component * float(cfg.pending_weight)
        + recent_component * float(cfg.recent_switch_weight)
        + quality_component * float(cfg.quality_weight)
        + raw_flicker_component * float(cfg.raw_flicker_weight)
    ) / total_weight
    score = score.clip(0.0, 1.0)

    out[f"{output_prefix}_raw_age_bars"] = raw_age.astype(int)
    out[f"{output_prefix}_raw_changed"] = raw_changed
    out[f"{output_prefix}_raw_stable_mismatch"] = mismatch
    out[f"{output_prefix}_pending_component"] = pending_component.astype(float)
    out[f"{output_prefix}_recent_switch_component"] = recent_component.astype(float)
    out[f"{output_prefix}_quality_component"] = quality_component.astype(float)
    out[f"{output_prefix}_raw_flicker_component"] = raw_flicker_component.astype(float)
    out[f"{output_prefix}_risk_score"] = score.astype(float)
    out[f"{output_prefix}_risk_bucket"] = np.select(
        [
            score >= float(cfg.high_threshold),
            score >= float(cfg.elevated_threshold),
            score >= float(cfg.watch_threshold),
        ],
        [
            "high_transition_risk",
            "elevated_transition_risk",
            "watch_transition_risk",
        ],
        default="stable_context",
    )
    return out
