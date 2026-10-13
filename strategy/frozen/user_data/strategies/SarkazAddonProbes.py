from __future__ import annotations

from datetime import datetime
from pathlib import Path
import sys
from typing import Any

import numpy as np
import pandas as pd
from freqtrade.strategy import stoploss_from_absolute


STRATEGY_DIR = Path(__file__).resolve().parent
if str(STRATEGY_DIR) not in sys.path:
    sys.path.insert(0, str(STRATEGY_DIR))

from SarkazCompositeProbes import SarkazFiniteWeightTableGrowthV1  # noqa: E402


class SarkazWGLaunchAdd25Close1RV1(SarkazFiniteWeightTableGrowthV1):
    """
    IS-first launch add-on probe for the current WeightTableGrowth family.

    It keeps the same entry filters, exposure table, Signal-K stop, +1R
    breakeven, 4h trail, and 24h time exit. The only new behavior is one
    post-entry add after the market proves the breakout by closing above +1R.

    Margin-neutral implementation idea:
    - initial stake is multiplied by 0.80;
    - leverage is multiplied by 1.25, preserving initial notional exposure;
    - the reserved 20% margin funds one add equal to 25% of initial stake;
    - add is allowed once, after a completed candle close is >= entry + 1R.

    This avoids the earlier reserve-pyramid problem where all non-added trades
    were under-exposed from the start.
    """

    ENTER_TAG_BASE = "sarkaz_wg_launch_add25_1r_low_v1"
    ENTER_TAG_HIGH = "sarkaz_wg_launch_add25_1r_high_v1"

    position_adjustment_enable = True
    max_entry_position_adjustment = 1

    INITIAL_STAKE_SCALE = 0.80
    LEVERAGE_RESERVE_MULT = 1.0 / INITIAL_STAKE_SCALE
    ADD_STAKE_FRACTION_OF_INITIAL = 0.25
    ADD_TRIGGER_R = 1.0

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
        stake *= self.INITIAL_STAKE_SCALE
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
        return float(min(float(base_leverage) * self.LEVERAGE_RESERVE_MULT, float(max_leverage)))

    def adjust_trade_position(
        self,
        trade,
        current_time: datetime,
        current_rate: float,
        current_profit: float,
        min_stake: float | None,
        max_stake: float,
        current_entry_rate: float,
        current_exit_rate: float,
        current_entry_profit: float,
        current_exit_profit: float,
        **kwargs: Any,
    ) -> float | None | tuple[float | None, str | None]:
        if getattr(trade, "nr_of_successful_entries", 1) >= 2:
            return None

        context = self._ensure_context(trade.pair, trade)
        if context is None:
            return None

        dataframe = self._analyzed_dataframe(trade.pair)
        if dataframe is None:
            return None
        row = self._row_before(dataframe, current_time)
        if row is None:
            return None

        add_trigger = float(trade.open_rate) + self.ADD_TRIGGER_R * float(context["risk_abs"])
        if float(row["close"]) < add_trigger:
            return None

        add_stake = float(trade.stake_amount) * self.ADD_STAKE_FRACTION_OF_INITIAL
        if min_stake is not None and add_stake < float(min_stake):
            return None
        if np.isfinite(max_stake) and max_stake > 0:
            add_stake = min(add_stake, float(max_stake))
        if add_stake <= 0:
            return None

        trade.set_custom_data("launch_add_trigger_time", str(current_time))
        trade.set_custom_data("launch_add_trigger_close", float(row["close"]))
        trade.set_custom_data("launch_add_trigger_r", self.ADD_TRIGGER_R)
        return float(add_stake), "launch_add25_after_close_1r"


class SarkazWGLaunchAdd25Close2RV1(SarkazWGLaunchAdd25Close1RV1):
    """
    Natural confirmation-depth control for the launch add-on probe.

    Same margin-neutral implementation as `SarkazWGLaunchAdd25Close1RV1`, but
    the add requires a completed candle close at or above +2R. This checks
    whether +1R is adding too early without introducing a new indicator.
    """

    ENTER_TAG_BASE = "sarkaz_wg_launch_add25_2r_low_v1"
    ENTER_TAG_HIGH = "sarkaz_wg_launch_add25_2r_high_v1"
    ADD_TRIGGER_R = 2.0

    def adjust_trade_position(
        self,
        trade,
        current_time: datetime,
        current_rate: float,
        current_profit: float,
        min_stake: float | None,
        max_stake: float,
        current_entry_rate: float,
        current_exit_rate: float,
        current_entry_profit: float,
        current_exit_profit: float,
        **kwargs: Any,
    ) -> float | None | tuple[float | None, str | None]:
        result = super().adjust_trade_position(
            trade,
            current_time,
            current_rate,
            current_profit,
            min_stake,
            max_stake,
            current_entry_rate,
            current_exit_rate,
            current_entry_profit,
            current_exit_profit,
            **kwargs,
        )
        if isinstance(result, tuple):
            return result[0], "launch_add25_after_close_2r"
        return result


class SarkazWGLaunchAdd25Close1ROriginalBEV1(SarkazWGLaunchAdd25Close1RV1):
    """
    Implementation-control variant for add-on stop handling.

    Freqtrade updates `trade.open_rate` to the average entry after a position
    adjustment. The inherited breakeven stop therefore moves to the average
    entry after adding, which can eject a valid trend immediately after the add.

    This variant keeps the original entry price as the +1R breakeven reference
    while leaving all entry, add, trail, and time-exit rules unchanged.
    """

    ENTER_TAG_BASE = "sarkaz_wg_launch_add25_1r_origbe_low_v1"
    ENTER_TAG_HIGH = "sarkaz_wg_launch_add25_1r_origbe_high_v1"

    def _original_entry_rate(self, trade) -> float:
        stored = self._float_or_none(trade.get_custom_data("launch_initial_open_rate"))
        if stored is not None:
            return stored
        return float(trade.open_rate)

    def adjust_trade_position(
        self,
        trade,
        current_time: datetime,
        current_rate: float,
        current_profit: float,
        min_stake: float | None,
        max_stake: float,
        current_entry_rate: float,
        current_exit_rate: float,
        current_entry_profit: float,
        current_exit_profit: float,
        **kwargs: Any,
    ) -> float | None | tuple[float | None, str | None]:
        result = super().adjust_trade_position(
            trade,
            current_time,
            current_rate,
            current_profit,
            min_stake,
            max_stake,
            current_entry_rate,
            current_exit_rate,
            current_entry_profit,
            current_exit_profit,
            **kwargs,
        )
        if result is not None:
            trade.set_custom_data("launch_initial_open_rate", float(trade.open_rate))
            if isinstance(result, tuple):
                return result[0], "launch_add25_after_close_1r_origbe"
        return result

    def custom_stoploss(
        self,
        pair: str,
        trade,
        current_time: datetime,
        current_rate: float,
        current_profit: float,
        after_fill: bool,
        **kwargs: Any,
    ) -> float | None:
        context = self._ensure_context(pair, trade)
        if context is None:
            return self.stoploss

        active_stop = float(context["stop_loss"])
        dataframe = self._analyzed_dataframe(pair)
        if dataframe is not None:
            path = self._rows_since_open(dataframe, trade, current_time)
            if not path.empty and float(path["high"].max()) >= float(context["target_1r"]):
                active_stop = max(active_stop, self._original_entry_rate(trade))
                current_row = self._row_before(dataframe, current_time)
                if current_row is not None:
                    trail = self._float_or_none(current_row.get("native_prior_2h_low_pre"))
                    if trail is not None:
                        active_stop = max(active_stop, trail)

        if active_stop >= current_rate:
            active_stop = current_rate * 0.999
        leverage = float(getattr(trade, "leverage", 1.0) or 1.0)
        return stoploss_from_absolute(active_stop, current_rate, is_short=False, leverage=leverage)


class SarkazWGLaunchAdd25OrigBESignalStopScaleBaseV1(SarkazWGLaunchAdd25Close1ROriginalBEV1):
    """
    Research base for Signal-K-length initial stop probes.

    The frozen OriginalBE system uses the Signal-K low as the initial stop. This
    family keeps entries, add-on, breakeven, trail, and time-exit mechanics, but
    defines the initial risk as a fixed fraction of the completed Signal-K full
    range measured down from the actual entry price.
    """

    SIGNAL_RANGE_STOP_MULT = 1.0

    def populate_indicators(self, dataframe: pd.DataFrame, metadata: dict) -> pd.DataFrame:
        enriched = super().populate_indicators(dataframe, metadata)
        if enriched.empty or "native_candidate_core" not in enriched:
            enriched["native_signal_range_abs"] = None
            return enriched

        candidate = enriched["native_candidate_core"].fillna(False).astype(bool)
        signal_range = (enriched["high"].astype(float) - enriched["low"].astype(float)).where(candidate)
        enriched["native_signal_range_abs"] = signal_range.shift(1)
        return enriched

    def _ensure_context(self, pair: str, trade) -> dict[str, float] | None:
        stop_loss = self._float_or_none(trade.get_custom_data("candidate_stop_loss"))
        risk_abs = self._float_or_none(trade.get_custom_data("candidate_risk_abs"))
        target_1r = self._float_or_none(trade.get_custom_data("candidate_target_1r"))
        if stop_loss is not None and risk_abs is not None and target_1r is not None:
            return {"stop_loss": stop_loss, "risk_abs": risk_abs, "target_1r": target_1r}

        dataframe = self._analyzed_dataframe(pair)
        if dataframe is None:
            return None
        entry_row = self._row_before(dataframe, trade.open_date_utc)
        if entry_row is None:
            return None

        signal_range = self._float_or_none(entry_row.get("native_signal_range_abs"))
        if signal_range is None or signal_range <= 0:
            return super()._ensure_context(pair, trade)

        risk_abs = float(signal_range) * float(self.SIGNAL_RANGE_STOP_MULT)
        if risk_abs <= 0:
            return None
        stop_loss = float(trade.open_rate) - risk_abs
        target_1r = float(trade.open_rate) + risk_abs
        trade.set_custom_data("candidate_stop_loss", stop_loss)
        trade.set_custom_data("candidate_risk_abs", risk_abs)
        trade.set_custom_data("candidate_target_1r", target_1r)
        signal_date = entry_row.get("native_candidate_signal_date")
        if pd.notna(signal_date):
            trade.set_custom_data("candidate_signal_date", str(signal_date))
        trade.set_custom_data("signal_range_stop_mult", float(self.SIGNAL_RANGE_STOP_MULT))
        return {"stop_loss": stop_loss, "risk_abs": risk_abs, "target_1r": target_1r}


class SarkazWGLaunchAdd25OrigBESignalStop75V1(SarkazWGLaunchAdd25OrigBESignalStopScaleBaseV1):
    """
    IS-first risk-definition probe: initial stop is 75% of Signal-K full range
    below the actual entry price.
    """

    ENTER_TAG_BASE = "sarkaz_wg_launch_add25_origbe_stop75_low_v1"
    ENTER_TAG_HIGH = "sarkaz_wg_launch_add25_origbe_stop75_high_v1"
    SIGNAL_RANGE_STOP_MULT = 0.75


class SarkazWGLaunchAdd25OrigBESignalStop50V1(SarkazWGLaunchAdd25OrigBESignalStopScaleBaseV1):
    """
    IS-first risk-definition probe: initial stop is 50% of Signal-K full range
    below the actual entry price.
    """

    ENTER_TAG_BASE = "sarkaz_wg_launch_add25_origbe_stop50_low_v1"
    ENTER_TAG_HIGH = "sarkaz_wg_launch_add25_origbe_stop50_high_v1"
    SIGNAL_RANGE_STOP_MULT = 0.50


class SarkazWGLaunchAdd25OrigBESignalStop125V1(SarkazWGLaunchAdd25OrigBESignalStopScaleBaseV1):
    """
    IS-first risk-definition probe: initial stop is 125% of Signal-K full range
    below the actual entry price.
    """

    ENTER_TAG_BASE = "sarkaz_wg_launch_add25_origbe_stop125_low_v1"
    ENTER_TAG_HIGH = "sarkaz_wg_launch_add25_origbe_stop125_high_v1"
    SIGNAL_RANGE_STOP_MULT = 1.25


class SarkazWGLaunchAdd25OrigBESignalStop150V1(SarkazWGLaunchAdd25OrigBESignalStopScaleBaseV1):
    """
    IS-first risk-definition probe: initial stop is 150% of Signal-K full range
    below the actual entry price.
    """

    ENTER_TAG_BASE = "sarkaz_wg_launch_add25_origbe_stop150_low_v1"
    ENTER_TAG_HIGH = "sarkaz_wg_launch_add25_origbe_stop150_high_v1"
    SIGNAL_RANGE_STOP_MULT = 1.50


class SarkazWGLaunchAdd25OrigBENoAddExit60V1(SarkazWGLaunchAdd25Close1ROriginalBEV1):
    """
    IS-first startup-failure management probe.

    This keeps the frozen OriginalBE add-on system unchanged for trades that
    launch. It only exits no-add trades after a completed 60-minute startup
    window fails:

    - the trade has not added yet;
    - at least 60 minutes have passed;
    - price has not touched +0.5R since entry;
    - the latest completed candle closes below the original entry price.

    The rule is deliberately broad but causal. It is a native check for the
    event-simulation result that no-add losses are the remaining weak bucket.
    """

    ENTER_TAG_BASE = "sarkaz_wg_launch_add25_origbe_noadd60_low_v1"
    ENTER_TAG_HIGH = "sarkaz_wg_launch_add25_origbe_noadd60_high_v1"

    NOADD_EXIT_DELAY_MINUTES = 60
    NOADD_HALF_R = 0.5

    def custom_exit(
        self,
        pair: str,
        trade,
        current_time: datetime,
        current_rate: float,
        current_profit: float,
        **kwargs: Any,
    ) -> str | bool | None:
        base_exit = super().custom_exit(pair, trade, current_time, current_rate, current_profit, **kwargs)
        if base_exit:
            return base_exit

        if getattr(trade, "nr_of_successful_entries", 1) >= 2:
            return None

        context = self._ensure_context(pair, trade)
        dataframe = self._analyzed_dataframe(pair)
        if context is None or dataframe is None:
            return None

        original_entry = self._original_entry_rate(trade)
        row = self._row_before(dataframe, current_time)
        if row is None:
            return None

        open_time = self._utc(trade.open_date_utc)
        row_time = self._utc(row["date"])
        if row_time - open_time < pd.Timedelta(minutes=self.NOADD_EXIT_DELAY_MINUTES):
            return None

        path = self._rows_since_open(dataframe, trade, row["date"])
        if path.empty:
            return None

        half_r_price = original_entry + self.NOADD_HALF_R * float(context["risk_abs"])
        no_half_r = float(path["high"].max()) < half_r_price
        below_entry = float(row["close"]) < original_entry
        if no_half_r and below_entry:
            return "noadd_failed_launch_60m_exit"
        return None


class SarkazWGLaunchAdd25OrigBEDynamicAddBaseV1(SarkazWGLaunchAdd25Close1ROriginalBEV1):
    """
    Research base for add-on expression probes.

    It keeps the frozen OriginalBE launch add-on entry, initial stake/leverage,
    stop, trail, and max-hold behavior. Subclasses may only change the size of
    the single +1R add using data from the completed trigger candle.
    """

    def _add_fraction_for_trigger(self, row: pd.Series) -> float:
        return float(self.ADD_STAKE_FRACTION_OF_INITIAL)

    def _add_tag_for_trigger(self, row: pd.Series, fraction: float) -> str:
        return "launch_add_dynamic_after_close_1r_origbe"

    def adjust_trade_position(
        self,
        trade,
        current_time: datetime,
        current_rate: float,
        current_profit: float,
        min_stake: float | None,
        max_stake: float,
        current_entry_rate: float,
        current_exit_rate: float,
        current_entry_profit: float,
        current_exit_profit: float,
        **kwargs: Any,
    ) -> float | None | tuple[float | None, str | None]:
        if getattr(trade, "nr_of_successful_entries", 1) >= 2:
            return None

        context = self._ensure_context(trade.pair, trade)
        if context is None:
            return None

        dataframe = self._analyzed_dataframe(trade.pair)
        if dataframe is None:
            return None
        row = self._row_before(dataframe, current_time)
        if row is None:
            return None

        original_entry = self._original_entry_rate(trade)
        add_trigger = float(original_entry) + self.ADD_TRIGGER_R * float(context["risk_abs"])
        if float(row["close"]) < add_trigger:
            return None

        fraction = float(self._add_fraction_for_trigger(row))
        if not np.isfinite(fraction) or fraction <= 0:
            return None

        add_stake = float(trade.stake_amount) * fraction
        if min_stake is not None and add_stake < float(min_stake):
            return None
        if np.isfinite(max_stake) and max_stake > 0:
            add_stake = min(add_stake, float(max_stake))
        if add_stake <= 0:
            return None

        trade.set_custom_data("launch_initial_open_rate", float(original_entry))
        trade.set_custom_data("launch_add_trigger_time", str(current_time))
        trade.set_custom_data("launch_add_trigger_close", float(row["close"]))
        trade.set_custom_data("launch_add_trigger_r", self.ADD_TRIGGER_R)
        trade.set_custom_data("launch_add_fraction", fraction)
        return float(add_stake), self._add_tag_for_trigger(row, fraction)


class SarkazWGLaunchAdd25OrigBEAddRangeBoost35V1(SarkazWGLaunchAdd25OrigBEDynamicAddBaseV1):
    """
    IS-first add-expression probe.

    If the completed +1R trigger candle itself shows exceptional range
    expansion, add a little more. This is a continuation-expression rule, not
    a new entry filter.
    """

    ENTER_TAG_BASE = "sarkaz_wg_launch_add_range35_low_v1"
    ENTER_TAG_HIGH = "sarkaz_wg_launch_add_range35_high_v1"

    EXCEPTIONAL_TRIGGER_RANGE_SCORE = 2.0
    RANGE_BOOST_ADD_FRACTION = 0.35

    def _add_fraction_for_trigger(self, row: pd.Series) -> float:
        score = self._float_or_none(row.get("range_filter_score"))
        if score is not None and score >= self.EXCEPTIONAL_TRIGGER_RANGE_SCORE:
            return float(self.RANGE_BOOST_ADD_FRACTION)
        return float(self.ADD_STAKE_FRACTION_OF_INITIAL)

    def _add_tag_for_trigger(self, row: pd.Series, fraction: float) -> str:
        if fraction > self.ADD_STAKE_FRACTION_OF_INITIAL:
            return "launch_add35_after_close_1r_range2_origbe"
        return "launch_add25_after_close_1r_origbe"


class SarkazWGLaunchAdd25OrigBEAddNormalHalfV1(SarkazWGLaunchAdd25OrigBEDynamicAddBaseV1):
    """
    IS-first add-expression probe.

    If the +1R trigger candle fires while the regime engine still labels the
    prior 1h range state as normal, cut only the add size in half. The initial
    trade remains unchanged.
    """

    ENTER_TAG_BASE = "sarkaz_wg_launch_add_normalhalf_low_v1"
    ENTER_TAG_HIGH = "sarkaz_wg_launch_add_normalhalf_high_v1"

    NORMAL_VOL_AXIS_ADD_FRACTION = 0.125

    def _add_fraction_for_trigger(self, row: pd.Series) -> float:
        if str(row.get("vol_axis", "")) == "normal":
            return float(self.NORMAL_VOL_AXIS_ADD_FRACTION)
        return float(self.ADD_STAKE_FRACTION_OF_INITIAL)

    def _add_tag_for_trigger(self, row: pd.Series, fraction: float) -> str:
        if fraction < self.ADD_STAKE_FRACTION_OF_INITIAL:
            return "launch_add12p5_after_close_1r_normal_origbe"
        return "launch_add25_after_close_1r_origbe"


class SarkazWGLaunchAdd25OrigBEAddExpansionOnlyV1(SarkazWGLaunchAdd25OrigBEDynamicAddBaseV1):
    """
    IS-first add-expression probe.

    Keep the initial trade unchanged, but pyramid only when the +1R trigger
    arrives outside the regime engine's normal volatility state. This treats
    +1R in a normal range state as acceptance without enough expansion for a
    second unit.
    """

    ENTER_TAG_BASE = "sarkaz_wg_launch_add_expansiononly_low_v1"
    ENTER_TAG_HIGH = "sarkaz_wg_launch_add_expansiononly_high_v1"

    def _add_fraction_for_trigger(self, row: pd.Series) -> float:
        if str(row.get("vol_axis", "")) == "normal":
            return 0.0
        return float(self.ADD_STAKE_FRACTION_OF_INITIAL)

    def _add_tag_for_trigger(self, row: pd.Series, fraction: float) -> str:
        return "launch_add25_after_close_1r_expansion_origbe"
