from __future__ import annotations

from datetime import datetime
from pathlib import Path
import sys
from typing import Any

import numpy as np
import pandas as pd


STRATEGY_DIR = Path(__file__).resolve().parent
if str(STRATEGY_DIR) not in sys.path:
    sys.path.insert(0, str(STRATEGY_DIR))

from SarkazFollowthroughProbes import SarkazConfirmCloseBalancedSizingV1  # noqa: E402


class SarkazBalancedMegaWeakHalfV1(SarkazConfirmCloseBalancedSizingV1):
    """
    IS-first composite exposure probe.

    This combines two already-studied, causal sizing labels without changing
    entries, exits, stops, trailing, regimes, or Signal-K definition:

    - follow-through quality:
      high confirmation gets 1.25x leverage, low confirmation gets 0.75x stake;
    - effort/result risk:
      if Signal-K volume is `mega_gt_10` but range result is not exceptional,
      multiply stake by 0.5.

    Rationale: confirmation quality expresses market follow-through after the
    signal, while effort/result expresses whether extreme volume produced
    enough price displacement. Both are known before the native fill.
    """

    ENTER_TAG_BASE = "sarkaz_balanced_mega_weak_low_v1"
    ENTER_TAG_HIGH = "sarkaz_balanced_mega_weak_high_1p25x_v1"

    MEGA_VOLUME_Z = 10.0
    EXCEPTIONAL_RANGE_FILTER_SCORE = 2.0
    WEAK_RESULT_STAKE_SCALE = 0.5

    def populate_indicators(self, dataframe: pd.DataFrame, metadata: dict) -> pd.DataFrame:
        enriched = super().populate_indicators(dataframe, metadata)
        if enriched.empty or "native_candidate_core" not in enriched:
            enriched["native_signal_volume_zscore"] = None
            enriched["native_signal_range_filter_score"] = None
            enriched["native_signal_mega_weak_result"] = False
            return enriched

        candidate = enriched["native_candidate_core"].fillna(False).astype(bool)
        enriched["native_signal_volume_zscore"] = enriched["volume_zscore"].where(candidate).shift(1)
        enriched["native_signal_range_filter_score"] = enriched["range_filter_score"].where(candidate).shift(1)
        enriched["native_signal_mega_weak_result"] = (
            enriched["native_entry_confirm"].fillna(False).astype(bool)
            & (enriched["native_signal_volume_zscore"].astype(float) > self.MEGA_VOLUME_Z)
            & (
                enriched["native_signal_range_filter_score"].astype(float)
                < self.EXCEPTIONAL_RANGE_FILTER_SCORE
            )
        )
        return enriched

    def _mega_weak_result_at_entry(self, pair: str, current_time: datetime) -> bool:
        dataframe = self._analyzed_dataframe(pair)
        if dataframe is None:
            return False
        row = self._row_before(dataframe, current_time)
        if row is None:
            return False
        volume_zscore = self._float_or_none(row.get("native_signal_volume_zscore"))
        range_filter_score = self._float_or_none(row.get("native_signal_range_filter_score"))
        if volume_zscore is None or range_filter_score is None:
            return False
        return bool(
            volume_zscore > self.MEGA_VOLUME_Z
            and range_filter_score < self.EXCEPTIONAL_RANGE_FILTER_SCORE
        )

    def custom_stake_amount(
        self,
        pair: str,
        current_time: datetime,
        current_rate: float,
        proposed_stake: float,
        min_stake: float | None,
        max_stake: float,
        leverage: float,
        entry_tag: str | None,
        side: str,
        **kwargs: Any,
    ) -> float:
        stake = super().custom_stake_amount(
            pair,
            current_time,
            current_rate,
            proposed_stake,
            min_stake,
            max_stake,
            leverage,
            entry_tag,
            side,
            **kwargs,
        )
        if self._mega_weak_result_at_entry(pair, current_time):
            stake *= self.WEAK_RESULT_STAKE_SCALE
        if min_stake is not None:
            stake = max(stake, float(min_stake))
        if np.isfinite(max_stake) and max_stake > 0:
            stake = min(stake, float(max_stake))
        return float(stake)


class SarkazRangeFloorBalancedSizingV1(SarkazConfirmCloseBalancedSizingV1):
    """
    IS-only composite launch-quality probe.

    This combines two already fixed, causal ideas without changing stops,
    trailing, max hold, Signal-K definition, regime labels, or volume gate:

    - RangeFloor: Signal-K is only valid when prior 1h range is at least the
      prior 3d median 1h range (`range_ratio_1h_vs_3d_pre >= 1.0`);
    - Balanced follow-through sizing: high confirmation gets 1.25x leverage,
      low confirmation stays in the book but uses 0.75x stake.

    This is not an active promotion. Because both components have already been
    studied, use this only as an IS interaction check unless explicitly frozen
    for a future forward/dry-run observation.
    """

    ENTER_TAG_BASE = "sarkaz_range_floor_balanced_low_0p75x_v1"
    ENTER_TAG_HIGH = "sarkaz_range_floor_balanced_high_1p25x_v1"
    MIN_RANGE_RATIO_1H_VS_3D = 1.0

    def populate_indicators(self, dataframe: pd.DataFrame, metadata: dict) -> pd.DataFrame:
        enriched = super().populate_indicators(dataframe, metadata)
        if enriched.empty or "native_candidate_core" not in enriched:
            enriched["signal_range_floor_ok"] = False
            return enriched

        range_floor_ok = enriched["range_ratio_1h_vs_3d_pre"].astype(float) >= self.MIN_RANGE_RATIO_1H_VS_3D
        filtered_core = enriched["native_candidate_core"].fillna(False).astype(bool) & range_floor_ok
        enriched["native_candidate_core"] = filtered_core
        enriched["native_entry_confirm"] = filtered_core.shift(1).fillna(False)
        enriched["native_candidate_stop_loss"] = enriched["low"].where(filtered_core).shift(1)
        enriched["native_candidate_signal_date"] = enriched["date"].where(filtered_core).shift(1)
        enriched["signal_range_floor_ok"] = range_floor_ok

        signal_close = enriched["close"].where(filtered_core)
        enriched["native_signal_close"] = signal_close.shift(1)
        enriched["native_confirm_close_ge_signal_close"] = (
            enriched["native_entry_confirm"].fillna(False).astype(bool)
            & enriched["native_signal_close"].notna()
            & (enriched["close"].astype(float) >= enriched["native_signal_close"].astype(float))
        )
        return enriched


class SarkazBalancedClimaxBodyVolumeHalfV1(SarkazConfirmCloseBalancedSizingV1):
    """
    Frozen composite sizing probe.

    Base system is SarkazConfirmCloseBalancedSizingV1:
    - high confirmation gets 1.25x leverage and full stake;
    - low confirmation gets 1.0x leverage and 0.75x stake.

    Additional Signal-K buying-climax risk label:
    - if the completed Signal-K has `body_pct >= 0.90` and
      `volume_zscore > 10.0`, multiply stake by 0.5.

    No entries, exits, stops, trails, regimes, or volume gates are changed.
    """

    ENTER_TAG_BASE = "sarkaz_balanced_climax_low_v1"
    ENTER_TAG_HIGH = "sarkaz_balanced_climax_high_1p25x_v1"
    CLIMAX_BODY_PCT = 0.90
    CLIMAX_VOLUME_Z = 10.0
    CLIMAX_STAKE_SCALE = 0.5

    def populate_indicators(self, dataframe: pd.DataFrame, metadata: dict) -> pd.DataFrame:
        enriched = super().populate_indicators(dataframe, metadata)
        if enriched.empty or "native_candidate_core" not in enriched:
            enriched["native_signal_body_pct"] = None
            enriched["native_signal_volume_zscore"] = None
            enriched["native_signal_climax_body_volume"] = False
            return enriched

        candidate = enriched["native_candidate_core"].fillna(False).astype(bool)
        enriched["native_signal_body_pct"] = enriched["body_pct"].where(candidate).shift(1)
        enriched["native_signal_volume_zscore"] = enriched["volume_zscore"].where(candidate).shift(1)
        enriched["native_signal_climax_body_volume"] = (
            enriched["native_entry_confirm"].fillna(False).astype(bool)
            & (enriched["native_signal_body_pct"].astype(float) >= self.CLIMAX_BODY_PCT)
            & (enriched["native_signal_volume_zscore"].astype(float) > self.CLIMAX_VOLUME_Z)
        )
        return enriched

    def _climax_body_volume_at_entry(self, pair: str, current_time: datetime) -> bool:
        dataframe = self._analyzed_dataframe(pair)
        if dataframe is None:
            return False
        row = self._row_before(dataframe, current_time)
        if row is None:
            return False
        body_pct = self._float_or_none(row.get("native_signal_body_pct"))
        volume_zscore = self._float_or_none(row.get("native_signal_volume_zscore"))
        if body_pct is None or volume_zscore is None:
            return False
        return bool(body_pct >= self.CLIMAX_BODY_PCT and volume_zscore > self.CLIMAX_VOLUME_Z)

    def custom_stake_amount(
        self,
        pair: str,
        current_time: datetime,
        current_rate: float,
        proposed_stake: float,
        min_stake: float | None,
        max_stake: float,
        leverage: float,
        entry_tag: str | None,
        side: str,
        **kwargs: Any,
    ) -> float:
        stake = super().custom_stake_amount(
            pair,
            current_time,
            current_rate,
            proposed_stake,
            min_stake,
            max_stake,
            leverage,
            entry_tag,
            side,
            **kwargs,
        )
        if self._climax_body_volume_at_entry(pair, current_time):
            stake *= self.CLIMAX_STAKE_SCALE
        if min_stake is not None:
            stake = max(stake, float(min_stake))
        if np.isfinite(max_stake) and max_stake > 0:
            stake = min(stake, float(max_stake))
        return float(stake)


class SarkazBalancedClimaxBodyVolumeZ3HalfV1(SarkazBalancedClimaxBodyVolumeHalfV1):
    """
    IS-first volume-confirmation relaxation probe for the current strongest
    shadow candidate.

    It keeps the Balanced confirmation sizing and Climax body+volume half-size
    overlay unchanged, and changes only the Signal-K participation gate:
    `volume_zscore > 4.0` becomes `volume_zscore > 3.0`.

    This is intentionally not a promotion. It tests whether the current volume
    gate is redundant with entity momentum or whether the z3-only bucket adds
    lower-quality noise.
    """

    ENTER_TAG_BASE = "sarkaz_balanced_climax_z3_low_v1"
    ENTER_TAG_HIGH = "sarkaz_balanced_climax_z3_high_1p25x_v1"
    FROZEN_VOLUME_Z_MIN = 3.0


class SarkazBalancedClimaxWeekendHalfV1(SarkazBalancedClimaxBodyVolumeHalfV1):
    """
    IS-first calendar-liquidity exposure probe.

    Base system is the frozen Balanced + Climax body/volume half-size shadow
    candidate. This probe changes no entry, exit, stop, trail, Signal-K,
    regime, volume, confirmation, or climax rule. It only halves the final
    stake for entries opened on Saturday or Sunday UTC.

    Rationale: BTC trades 24/7, but weekend participation can be thinner and
    less institutionally supported. This is a coarse liquidity-mode sizing
    check, not a calendar alpha promotion.
    """

    ENTER_TAG_BASE = "sarkaz_balanced_climax_weekend_low_v1"
    ENTER_TAG_HIGH = "sarkaz_balanced_climax_weekend_high_1p25x_v1"
    WEEKEND_STAKE_SCALE = 0.5

    def custom_stake_amount(
        self,
        pair: str,
        current_time: datetime,
        current_rate: float,
        proposed_stake: float,
        min_stake: float | None,
        max_stake: float,
        leverage: float,
        entry_tag: str | None,
        side: str,
        **kwargs: Any,
    ) -> float:
        stake = super().custom_stake_amount(
            pair,
            current_time,
            current_rate,
            proposed_stake,
            min_stake,
            max_stake,
            leverage,
            entry_tag,
            side,
            **kwargs,
        )
        if current_time.weekday() >= 5:
            stake *= self.WEEKEND_STAKE_SCALE
        if min_stake is not None:
            stake = max(stake, float(min_stake))
        if np.isfinite(max_stake) and max_stake > 0:
            stake = min(stake, float(max_stake))
        return float(stake)


class SarkazBalancedClimaxWeekendCompressedHalfV1(SarkazBalancedClimaxWeekendHalfV1):
    """
    IS-first liquidity-state exposure probe.

    Base system is the validated Balanced + Climax + Weekend half-stake shadow
    candidate. This probe changes no entry, exit, stop, trail, Signal-K,
    regime, volume, confirmation, climax, or weekend rule. It only halves the
    final stake again when the causal pre-entry regime axis says the prior 1h
    range state was compressed.

    Rationale: a breakout system needs market expansion and participation. A
    Signal-K fired out of a compressed pre-entry state can still work, but the
    false-launch risk deserves smaller exposure rather than deletion.
    """

    ENTER_TAG_BASE = "sarkaz_balanced_climax_weekend_compressed_low_v1"
    ENTER_TAG_HIGH = "sarkaz_balanced_climax_weekend_compressed_high_1p25x_v1"
    COMPRESSED_STAKE_SCALE = 0.5

    def _compressed_state_at_entry(self, pair: str, current_time: datetime) -> bool:
        dataframe = self._analyzed_dataframe(pair)
        if dataframe is None:
            return False
        row = self._row_before(dataframe, current_time)
        if row is None:
            return False
        return str(row.get("vol_axis", "")) == "compressed"

    def custom_stake_amount(
        self,
        pair: str,
        current_time: datetime,
        current_rate: float,
        proposed_stake: float,
        min_stake: float | None,
        max_stake: float,
        leverage: float,
        entry_tag: str | None,
        side: str,
        **kwargs: Any,
    ) -> float:
        stake = super().custom_stake_amount(
            pair,
            current_time,
            current_rate,
            proposed_stake,
            min_stake,
            max_stake,
            leverage,
            entry_tag,
            side,
            **kwargs,
        )
        if self._compressed_state_at_entry(pair, current_time):
            stake *= self.COMPRESSED_STAKE_SCALE
        if min_stake is not None:
            stake = max(stake, float(min_stake))
        if np.isfinite(max_stake) and max_stake > 0:
            stake = min(stake, float(max_stake))
        return float(stake)


class SarkazBalancedClimaxWeekendCompressedFreshBoostV1(SarkazBalancedClimaxWeekendCompressedHalfV1):
    """
    IS-first positive exposure probe.

    Base system is `SarkazBalancedClimaxWeekendCompressedHalfV1`. This probe
    changes no entries, exits, stops, trails, Signal-K definition, regime,
    volume gate, confirmation label, or risk-reduction labels.

    The only positive exposure rule:
    - if the Signal-K is fresh after more than 24h without a prior Signal-K,
    - the confirmation candle is high quality,
    - and the trade is not weekend, Climax Body, or compressed-state risk,
      increase the high-confirm leverage by 10% (`1.25x` -> `1.375x`).

    Rationale: after a long quiet interval, a clean confirmed breakout may
    deserve more participation. The boost is deliberately mild and applies only
    when the existing risk labels are absent.
    """

    ENTER_TAG_BASE = "sarkaz_balanced_climax_weekend_compressed_fresh_low_v1"
    ENTER_TAG_HIGH = "sarkaz_balanced_climax_weekend_compressed_fresh_high_v1"
    FRESH_SIGNAL_GAP_HOURS = 24.0
    FRESH_HIGH_CONFIRM_LEVERAGE_MULT = 1.10

    def populate_indicators(self, dataframe: pd.DataFrame, metadata: dict) -> pd.DataFrame:
        enriched = super().populate_indicators(dataframe, metadata)
        if enriched.empty or "native_candidate_core" not in enriched:
            enriched["native_signal_fresh_gt_24h"] = False
            return enriched

        candidate = enriched["native_candidate_core"].fillna(False).astype(bool)
        signal_dates = enriched["date"].where(candidate)
        previous_signal_dates = signal_dates.ffill().shift(1)
        gap_hours = (
            pd.to_datetime(enriched["date"], utc=True)
            - pd.to_datetime(previous_signal_dates, utc=True)
        ).dt.total_seconds() / 3600.0
        fresh_signal = candidate & (gap_hours.astype(float) > self.FRESH_SIGNAL_GAP_HOURS)
        enriched["native_signal_fresh_gt_24h"] = fresh_signal.shift(1).fillna(False)
        return enriched

    def _fresh_signal_at_entry(self, pair: str, current_time: datetime) -> bool:
        dataframe = self._analyzed_dataframe(pair)
        if dataframe is None:
            return False
        row = self._row_before(dataframe, current_time)
        if row is None:
            return False
        return bool(row.get("native_signal_fresh_gt_24h", False))

    def _fresh_high_confirm_nonrisk_at_entry(self, pair: str, current_time: datetime) -> bool:
        return bool(
            self._fresh_signal_at_entry(pair, current_time)
            and self._high_confirm_at_entry(pair, current_time)
            and current_time.weekday() < 5
            and not self._climax_body_volume_at_entry(pair, current_time)
            and not self._compressed_state_at_entry(pair, current_time)
        )

    def leverage(
        self,
        pair: str,
        current_time: datetime,
        current_rate: float,
        proposed_leverage: float,
        max_leverage: float,
        entry_tag: str | None,
        side: str,
        **kwargs: Any,
    ) -> float:
        base_leverage = super().leverage(
            pair,
            current_time,
            current_rate,
            proposed_leverage,
            max_leverage,
            entry_tag,
            side,
            **kwargs,
        )
        if self._fresh_high_confirm_nonrisk_at_entry(pair, current_time):
            return float(min(base_leverage * self.FRESH_HIGH_CONFIRM_LEVERAGE_MULT, float(max_leverage)))
        return float(base_leverage)


class SarkazFiniteWeightTableGrowthV1(SarkazBalancedClimaxWeekendCompressedFreshBoostV1):
    """
    IS-first finite exposure table probe.

    This keeps the same entries, exits, Signal-K definition, regime/structure,
    volume gate, and management as FreshBoost. It changes only how exposure is
    expressed after a trade has already qualified.

    The exposure table is intentionally coarse:
    - low confirmation, clean state: 0.75x stake and 1.00x leverage;
    - low confirmation, any risk label: 0.50x stake and 1.00x leverage;
    - high confirmation, any risk label: 0.75x stake and 1.25x leverage;
    - high confirmation, clean state: 1.00x stake and 1.50x leverage;
    - fresh high confirmation, clean state: 1.00x stake and 1.75x leverage.

    Risk labels are the existing causal labels known before the native fill:
    weekend UTC, Climax Body, and compressed pre-entry volatility state.
    No ETH/XAU or OOS data is used for this BTC-only probe.
    """

    ENTER_TAG_BASE = "sarkaz_weight_table_low_v1"
    ENTER_TAG_HIGH = "sarkaz_weight_table_high_v1"

    CLEAN_LOW_STAKE_SCALE = 0.75
    RISK_LOW_STAKE_SCALE = 0.50
    RISK_HIGH_STAKE_SCALE = 0.75
    RISK_HIGH_LEVERAGE = 1.25
    CLEAN_HIGH_LEVERAGE = 1.50
    FRESH_CLEAN_HIGH_LEVERAGE = 1.75

    def _any_risk_label_at_entry(self, pair: str, current_time: datetime) -> bool:
        return bool(
            current_time.weekday() >= 5
            or self._climax_body_volume_at_entry(pair, current_time)
            or self._compressed_state_at_entry(pair, current_time)
        )

    def custom_stake_amount(
        self,
        pair: str,
        current_time: datetime,
        current_rate: float,
        proposed_stake: float,
        min_stake: float | None,
        max_stake: float,
        leverage: float,
        entry_tag: str | None,
        side: str,
        **kwargs: Any,
    ) -> float:
        base = max_stake if np.isfinite(max_stake) and max_stake > 0 else proposed_stake
        stake = float(base)
        high_confirm = self._high_confirm_at_entry(pair, current_time)
        risk_label = self._any_risk_label_at_entry(pair, current_time)

        if high_confirm and risk_label:
            stake *= self.RISK_HIGH_STAKE_SCALE
        elif not high_confirm and risk_label:
            stake *= self.RISK_LOW_STAKE_SCALE
        elif not high_confirm:
            stake *= self.CLEAN_LOW_STAKE_SCALE

        if min_stake is not None:
            stake = max(stake, float(min_stake))
        if np.isfinite(max_stake) and max_stake > 0:
            stake = min(stake, float(max_stake))
        return float(stake)

    def leverage(
        self,
        pair: str,
        current_time: datetime,
        current_rate: float,
        proposed_leverage: float,
        max_leverage: float,
        entry_tag: str | None,
        side: str,
        **kwargs: Any,
    ) -> float:
        if not self._high_confirm_at_entry(pair, current_time):
            return 1.0
        if self._fresh_high_confirm_nonrisk_at_entry(pair, current_time):
            return float(min(self.FRESH_CLEAN_HIGH_LEVERAGE, float(max_leverage)))
        if self._any_risk_label_at_entry(pair, current_time):
            return float(min(self.RISK_HIGH_LEVERAGE, float(max_leverage)))
        return float(min(self.CLEAN_HIGH_LEVERAGE, float(max_leverage)))
