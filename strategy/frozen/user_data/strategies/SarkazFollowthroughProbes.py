from __future__ import annotations

from pathlib import Path
import sys
from datetime import datetime
from typing import Any

import numpy as np
import pandas as pd
from freqtrade.persistence import Trade


STRATEGY_DIR = Path(__file__).resolve().parent
if str(STRATEGY_DIR) not in sys.path:
    sys.path.insert(0, str(STRATEGY_DIR))

from Sarkaz import Sarkaz  # noqa: E402


class SarkazConfirmHoldMidV1(Sarkaz):
    """
    IS-only follow-through probe.

    Entry, exit, Signal-K, regime, and volume logic are unchanged from Sarkaz.

    Additional causal execution condition:
    - Signal K appears on bar t.
    - Confirmation bar t+1 must hold above the midpoint of Signal K.
    - Freqtrade then enters on the next available fill.

    This tests price acceptance after the signal, not a new indicator stack.
    """

    ENTER_TAG = "sarkaz_confirm_hold_mid_v1"

    def populate_indicators(self, dataframe: pd.DataFrame, metadata: dict) -> pd.DataFrame:
        enriched = super().populate_indicators(dataframe, metadata)
        if enriched.empty or "native_candidate_core" not in enriched:
            enriched["native_entry_confirm_hold_mid"] = False
            return enriched

        signal_mid = ((enriched["high"].astype(float) + enriched["low"].astype(float)) / 2.0).where(
            enriched["native_candidate_core"].fillna(False).astype(bool)
        )
        enriched["native_signal_midpoint"] = signal_mid.shift(1)
        enriched["native_entry_confirm_hold_mid"] = (
            enriched["native_entry_confirm"].fillna(False).astype(bool)
            & enriched["native_signal_midpoint"].notna()
            & (enriched["low"].astype(float) >= enriched["native_signal_midpoint"].astype(float))
        )
        return enriched

    def populate_entry_trend(self, dataframe: pd.DataFrame, metadata: dict) -> pd.DataFrame:
        dataframe["enter_long"] = 0
        dataframe["enter_tag"] = None
        if "native_entry_confirm_hold_mid" not in dataframe:
            return dataframe
        mask = dataframe["native_entry_confirm_hold_mid"].fillna(False).astype(bool)
        dataframe.loc[mask, "enter_long"] = 1
        dataframe.loc[mask, "enter_tag"] = self.ENTER_TAG
        return dataframe


class SarkazConfirmCloseLeverage125V1(Sarkaz):
    """
    IS-only confirmation-confidence sizing probe.

    Entry, exit, Signal-K, regime/structure, volume gate, and management are
    unchanged from current Sarkaz. No trades are filtered out.

    The only change:
    - if the completed confirmation candle closes at or above the Signal-K
      close before Freqtrade's next available fill, use 1.25x leverage;
    - otherwise use the baseline 1.0x leverage.

    Rationale: strong confirmation was too destructive as an entry filter, but
    it may be a causal confidence signal for sizing without deleting slow-start
    trend winners.
    """

    ENTER_TAG_BASE = "sarkaz_confirm_sizing_base_v1"
    ENTER_TAG_HIGH = "sarkaz_confirm_close_ge_signal_close_1p25x_v1"
    HIGH_CONFIRM_LEVERAGE = 1.25

    def populate_indicators(self, dataframe: pd.DataFrame, metadata: dict) -> pd.DataFrame:
        enriched = super().populate_indicators(dataframe, metadata)
        if enriched.empty or "native_candidate_core" not in enriched:
            enriched["native_signal_close"] = None
            enriched["native_confirm_close_ge_signal_close"] = False
            return enriched

        signal_close = enriched["close"].where(enriched["native_candidate_core"].fillna(False).astype(bool))
        enriched["native_signal_close"] = signal_close.shift(1)
        enriched["native_confirm_close_ge_signal_close"] = (
            enriched["native_entry_confirm"].fillna(False).astype(bool)
            & enriched["native_signal_close"].notna()
            & (enriched["close"].astype(float) >= enriched["native_signal_close"].astype(float))
        )
        return enriched

    def _high_confirm_at_entry(self, pair: str, current_time: datetime) -> bool:
        dataframe = self._analyzed_dataframe(pair)
        if dataframe is None:
            return False
        row = self._row_before(dataframe, current_time)
        if row is None:
            return False
        return bool(row.get("native_confirm_close_ge_signal_close", False))

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
        if self._high_confirm_at_entry(pair, current_time):
            return float(min(self.HIGH_CONFIRM_LEVERAGE, float(max_leverage)))
        return 1.0

    def populate_entry_trend(self, dataframe: pd.DataFrame, metadata: dict) -> pd.DataFrame:
        dataframe["enter_long"] = 0
        dataframe["enter_tag"] = None
        if "native_entry_confirm" not in dataframe:
            return dataframe
        base_mask = dataframe["native_entry_confirm"].fillna(False).astype(bool)
        high_mask = base_mask & dataframe["native_confirm_close_ge_signal_close"].fillna(False).astype(bool)
        normal_mask = base_mask & ~high_mask
        dataframe.loc[normal_mask, "enter_long"] = 1
        dataframe.loc[normal_mask, "enter_tag"] = self.ENTER_TAG_BASE
        dataframe.loc[high_mask, "enter_long"] = 1
        dataframe.loc[high_mask, "enter_tag"] = self.ENTER_TAG_HIGH
        return dataframe


class SarkazConfirmCloseLev125RiskCapV1(SarkazConfirmCloseLeverage125V1):
    """
    IS-only risk-normalized confirmation sizing probe.

    No entries are filtered. Entry/exit logic is unchanged.

    Sizing rule:
    - high-confirm trades still use up to 1.25x leverage;
    - normal-confirm trades use 1.0x leverage;
    - stake is reduced when the intended leveraged notional would risk more
      than 1% from entry to the Signal-K stop.

    Rationale: the pure 1.25x confirmation candidate improved return but
    widened drawdown. This probe keeps the same causal confidence signal while
    capping ex-ante initial stop risk in a standard, non-tuned way.
    """

    ENTER_TAG_BASE = "sarkaz_confirm_riskcap_base_v1"
    ENTER_TAG_HIGH = "sarkaz_confirm_riskcap_high_1p25x_v1"
    TARGET_INITIAL_RISK_PCT = 0.01

    def _candidate_risk_pct(self, pair: str, current_time: datetime, current_rate: float) -> float | None:
        dataframe = self._analyzed_dataframe(pair)
        if dataframe is None:
            return None
        row = self._row_before(dataframe, current_time)
        if row is None:
            return None
        stop_loss = self._float_or_none(row.get("native_candidate_stop_loss"))
        if stop_loss is None or stop_loss >= current_rate:
            return None
        risk_pct = (float(current_rate) - stop_loss) / float(current_rate)
        if not np.isfinite(risk_pct) or risk_pct <= 0:
            return None
        return float(risk_pct)

    def _intended_leverage(self, pair: str, current_time: datetime) -> float:
        if self._high_confirm_at_entry(pair, current_time):
            return float(self.HIGH_CONFIRM_LEVERAGE)
        return 1.0

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
        risk_pct = self._candidate_risk_pct(pair, current_time, current_rate)
        intended_leverage = self._intended_leverage(pair, current_time)
        if risk_pct is not None:
            leveraged_risk_pct = risk_pct * intended_leverage
            if leveraged_risk_pct > self.TARGET_INITIAL_RISK_PCT:
                stake = float(base) * self.TARGET_INITIAL_RISK_PCT / leveraged_risk_pct
        if min_stake is not None:
            stake = max(stake, float(min_stake))
        if np.isfinite(max_stake) and max_stake > 0:
            stake = min(stake, float(max_stake))
        return float(stake)


class SarkazConfirmCloseBalancedSizingV1(SarkazConfirmCloseLeverage125V1):
    """
    IS-first balanced follow-through sizing probe.

    Entry, exit, Signal-K, regime/structure, volume gate, and management are
    unchanged from current Sarkaz. No trades are filtered out.

    The only change is coarse exposure expression using the completed
    confirmation candle before Freqtrade's next available fill:
    - confirmation close >= Signal-K close: 1.25x leverage, full stake;
    - otherwise: 1.0x leverage, 0.75x stake.

    Rationale: strong confirmation was valuable but filtering weak confirmation
    deleted too many delayed-continuation winners. This keeps every trade while
    giving more capital to clean follow-through and less capital to slow starts.
    The 25% up/down step is deliberately coarse, symmetric, and not a fitted
    threshold sweep.
    """

    ENTER_TAG_BASE = "sarkaz_confirm_balanced_low_0p75x_v1"
    ENTER_TAG_HIGH = "sarkaz_confirm_balanced_high_1p25x_v1"
    LOW_CONFIRM_STAKE_SCALE = 0.75

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
        if not self._high_confirm_at_entry(pair, current_time):
            stake *= self.LOW_CONFIRM_STAKE_SCALE
        if min_stake is not None:
            stake = max(stake, float(min_stake))
        if np.isfinite(max_stake) and max_stake > 0:
            stake = min(stake, float(max_stake))
        return float(stake)


class SarkazBalancedSeqLowConfirmV1(SarkazConfirmCloseBalancedSizingV1):
    """
    IS-first sequential sizing probe.

    Base system is SarkazConfirmCloseBalancedSizingV1:
    - high confirmation: full stake with 1.25x leverage;
    - low confirmation: 0.75x stake with 1.0x leverage.

    Additional causal rule:
    - if the current trade is low-confirm and the prior 10 closed trades from
      this strategy have negative total absolute PnL, multiply stake by 0.75.

    Rationale: early failure exits cut too many delayed trend winners. This
    probe keeps every entry and expresses recent strategy coldness only through
    a coarse low-confirm exposure reduction. The prior-PnL threshold is the
    natural zero boundary and uses only closed trades before the new entry.
    """

    MODEL_VERSION = "sarkaz_balanced_seq_low_confirm_v1"
    ENTER_TAG_BASE = "sarkaz_balanced_seq_low_v1"
    ENTER_TAG_HIGH = "sarkaz_balanced_seq_high_1p25x_v1"
    COLD_HISTORY_TRADES = 10
    COLD_LOW_CONFIRM_STAKE_SCALE = 0.75

    def _closed_strategy_profit_abs(self, pair: str, current_time: datetime) -> list[float]:
        now = self._utc(current_time)
        rows: list[tuple[pd.Timestamp, float]] = []
        valid_tags = {self.ENTER_TAG_BASE, self.ENTER_TAG_HIGH}
        for trade in Trade.get_trades_proxy(pair=pair, is_open=False):
            close_date = getattr(trade, "close_date_utc", None)
            if close_date is None or self._utc(close_date) >= now:
                continue
            model_version = trade.get_custom_data("sarkaz_seq_model_version")
            enter_tag = str(getattr(trade, "enter_tag", "") or "")
            if model_version != self.MODEL_VERSION and enter_tag not in valid_tags:
                continue

            profit_abs = self._float_or_none(getattr(trade, "close_profit_abs", None))
            if profit_abs is None:
                profit_abs = self._float_or_none(getattr(trade, "realized_profit", None))
            if profit_abs is None:
                close_profit = self._float_or_none(getattr(trade, "close_profit", None))
                stake_amount = self._float_or_none(getattr(trade, "stake_amount", None))
                if close_profit is not None and stake_amount is not None:
                    profit_abs = close_profit * stake_amount
            if profit_abs is None:
                continue
            rows.append((self._utc(close_date), float(profit_abs)))
        return [profit for _, profit in sorted(rows, key=lambda item: item[0])]

    def _low_confirm_cold_state(self, pair: str, current_time: datetime) -> bool:
        if self._high_confirm_at_entry(pair, current_time):
            return False
        history = self._closed_strategy_profit_abs(pair, current_time)
        if len(history) < self.COLD_HISTORY_TRADES:
            return False
        return float(sum(history[-self.COLD_HISTORY_TRADES :])) < 0.0

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
        if self._low_confirm_cold_state(pair, current_time):
            stake *= self.COLD_LOW_CONFIRM_STAKE_SCALE
        if min_stake is not None:
            stake = max(stake, float(min_stake))
        if np.isfinite(max_stake) and max_stake > 0:
            stake = min(stake, float(max_stake))
        return float(stake)

    def _ensure_context(self, pair: str, trade: Trade) -> dict[str, float] | None:
        context = super()._ensure_context(pair, trade)
        if context is None:
            return None
        if trade.get_custom_data("sarkaz_seq_model_version") != self.MODEL_VERSION:
            trade.set_custom_data("sarkaz_seq_model_version", self.MODEL_VERSION)
        return context
