from __future__ import annotations

from datetime import datetime, timedelta, timezone
from pathlib import Path
import sys
from typing import Any

import numpy as np
import pandas as pd

from freqtrade.persistence import Trade
from freqtrade.strategy import IStrategy, stoploss_from_absolute


PROJECT_ROOT = Path(__file__).resolve().parents[2]
RESEARCH_DIR = PROJECT_ROOT / "scripts" / "research"
USER_DATA_DIR = PROJECT_ROOT / "user_data"
if str(USER_DATA_DIR) not in sys.path:
    sys.path.insert(0, str(USER_DATA_DIR))
if str(RESEARCH_DIR) not in sys.path:
    sys.path.insert(0, str(RESEARCH_DIR))

from backtest_big_body_momentum_k import add_signal_columns  # noqa: E402
from backtest_btc_structure_regime_long_v2_management import (  # noqa: E402
    add_structure_features,
    select_structure_candidates,
)
from market_regime import build_regime_v2  # noqa: E402


class BtcNextCloseBayesLongV1Strategy(IStrategy):
    """
    Research-only native Freqtrade candidate for the frozen BTC V1 logic.

    Boundary:
    - Implements the frozen Signal K + regime/structure + extreme-volume core.
    - Implements the signal-low stop, +1R breakeven, prior-2h-low trail, and 24h time exit.
    - Does not implement the outcome-dependent Bayesian trade/pass layer as a static indicator.

    Execution note:
    The research simulator enters at bar t+1 close after a signal on bar t. A no-lookahead
    Freqtrade backtest cannot know the t+1 close at the t+1 open, so this native strategy
    confirms on t+1 and enters on the next available Freqtrade fill.
    """

    timeframe = "5m"
    can_short = False
    process_only_new_candles = True
    startup_candle_count = 1000

    minimal_roi = {"0": 100.0}
    stoploss = -0.99
    use_custom_stoploss = True

    trailing_stop = False
    ignore_roi_if_entry_signal = False
    position_adjustment_enable = False

    order_types = {
        "entry": "limit",
        "exit": "limit",
        "stoploss": "market",
        "stoploss_on_exchange": False,
    }
    order_time_in_force = {"entry": "GTC", "exit": "GTC"}

    FROZEN_BODY_PCT_MIN = 0.70
    FROZEN_RANGE_WINDOW_DAYS = 3
    FROZEN_RANGE_QUANTILE = 0.90
    FROZEN_VOLUME_Z_MIN = 4.0
    TRAIL_2H_LOOKBACK_BARS = 24
    MAX_HOLD = timedelta(hours=24)

    ALLOWED_LONG_REGIMES = {
        "active_uptrend_acceptance",
        "quiet_uptrend_acceptance",
        "upper_value_rotation_or_extension",
    }
    SUPPORTED_PAIRS: set[str] | None = {"BTC/USDT:USDT"}

    @staticmethod
    def _utc(value: Any) -> pd.Timestamp:
        ts = pd.Timestamp(value)
        if ts.tzinfo is None:
            return ts.tz_localize("UTC")
        return ts.tz_convert("UTC")

    @staticmethod
    def _float_or_none(value: Any) -> float | None:
        try:
            out = float(value)
        except (TypeError, ValueError):
            return None
        return out if np.isfinite(out) else None

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
        return 1.0

    def populate_indicators(self, dataframe: pd.DataFrame, metadata: dict) -> pd.DataFrame:
        if dataframe.empty:
            return dataframe

        if self.SUPPORTED_PAIRS is not None and metadata.get("pair") not in self.SUPPORTED_PAIRS:
            dataframe["native_candidate_core"] = False
            dataframe["native_entry_confirm"] = False
            return dataframe

        bars = dataframe.copy()
        bars["date"] = pd.to_datetime(bars["date"], utc=True)
        bars = bars.sort_values("date").reset_index(drop=True)
        for col in ["open", "high", "low", "close", "volume"]:
            bars[col] = bars[col].astype(float)

        signals = add_signal_columns(
            bars,
            timeframe=self.timeframe,
            body_pct_min=self.FROZEN_BODY_PCT_MIN,
            range_z_min=1.0,
            range_filter="rolling_quantile",
            range_window_days=self.FROZEN_RANGE_WINDOW_DAYS,
            range_quantile=self.FROZEN_RANGE_QUANTILE,
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
        enriched = pd.merge_asof(
            signals.sort_values("date"),
            regimes[regime_cols].sort_values("date"),
            on="date",
            direction="backward",
        )
        enriched = add_structure_features(enriched)
        enriched["regime_long_ok"] = enriched["regime_v2"].isin(self.ALLOWED_LONG_REGIMES)

        selected = select_structure_candidates(enriched)
        enriched["native_structure_selected"] = False
        if not selected.empty:
            enriched.loc[selected.index, "native_structure_selected"] = True

        enriched["volume_tier_bin"] = pd.cut(
            enriched["volume_zscore"],
            bins=[4.0, 6.0, 10.0, np.inf],
            labels=["extreme_4_6", "ultra_6_10", "mega_gt_10"],
            include_lowest=True,
        ).astype("object").fillna("unknown")

        enriched["native_candidate_core"] = (
            enriched["native_structure_selected"].astype(bool)
            & enriched["regime_v2"].isin(self.ALLOWED_LONG_REGIMES)
            & (enriched["volume_zscore"] > self.FROZEN_VOLUME_Z_MIN)
        )
        enriched["native_entry_confirm"] = enriched["native_candidate_core"].shift(1).fillna(False)
        enriched["native_candidate_stop_loss"] = enriched["low"].where(enriched["native_candidate_core"]).shift(1)
        enriched["native_candidate_signal_date"] = enriched["date"].where(enriched["native_candidate_core"]).shift(1)
        enriched["native_prior_2h_low_pre"] = (
            enriched["low"].rolling(self.TRAIL_2H_LOOKBACK_BARS, min_periods=self.TRAIL_2H_LOOKBACK_BARS // 2).min().shift(1)
        )

        return enriched

    def populate_entry_trend(self, dataframe: pd.DataFrame, metadata: dict) -> pd.DataFrame:
        dataframe["enter_long"] = 0
        dataframe["enter_tag"] = None
        if "native_entry_confirm" not in dataframe:
            return dataframe
        mask = dataframe["native_entry_confirm"].fillna(False).astype(bool)
        dataframe.loc[mask, "enter_long"] = 1
        dataframe.loc[mask, "enter_tag"] = "btc_next_close_core_native_v1"
        return dataframe

    def populate_exit_trend(self, dataframe: pd.DataFrame, metadata: dict) -> pd.DataFrame:
        dataframe["exit_long"] = 0
        return dataframe

    def _analyzed_dataframe(self, pair: str) -> pd.DataFrame | None:
        if not self.dp:
            return None
        try:
            dataframe, _ = self.dp.get_analyzed_dataframe(pair, self.timeframe)
        except Exception:
            return None
        if dataframe is None or dataframe.empty:
            return None
        out = dataframe.copy()
        out["date"] = pd.to_datetime(out["date"], utc=True)
        return out.sort_values("date").reset_index(drop=True)

    def _row_before(self, dataframe: pd.DataFrame, when: datetime | pd.Timestamp) -> pd.Series | None:
        ts = self._utc(when)
        rows = dataframe[dataframe["date"] < ts]
        if rows.empty:
            return None
        return rows.iloc[-1]

    def _rows_since_open(self, dataframe: pd.DataFrame, trade: Trade, current_time: datetime) -> pd.DataFrame:
        open_ts = self._utc(trade.open_date_utc)
        current_ts = self._utc(current_time)
        return dataframe[(dataframe["date"] >= open_ts) & (dataframe["date"] <= current_ts)]

    def _ensure_context(self, pair: str, trade: Trade) -> dict[str, float] | None:
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
        stop_loss = self._float_or_none(entry_row.get("native_candidate_stop_loss"))
        if stop_loss is None or stop_loss >= float(trade.open_rate):
            return None
        risk_abs = float(trade.open_rate) - stop_loss
        if risk_abs <= 0:
            return None
        target_1r = float(trade.open_rate) + risk_abs
        trade.set_custom_data("candidate_stop_loss", stop_loss)
        trade.set_custom_data("candidate_risk_abs", risk_abs)
        trade.set_custom_data("candidate_target_1r", target_1r)
        signal_date = entry_row.get("native_candidate_signal_date")
        if pd.notna(signal_date):
            trade.set_custom_data("candidate_signal_date", str(signal_date))
        return {"stop_loss": stop_loss, "risk_abs": risk_abs, "target_1r": target_1r}

    def custom_stoploss(
        self,
        pair: str,
        trade: Trade,
        current_time: datetime,
        current_rate: float,
        current_profit: float,
        after_fill: bool,
        **kwargs: Any,
    ) -> float | None:
        context = self._ensure_context(pair, trade)
        if context is None:
            return self.stoploss

        active_stop = context["stop_loss"]
        dataframe = self._analyzed_dataframe(pair)
        if dataframe is not None:
            path = self._rows_since_open(dataframe, trade, current_time)
            if not path.empty and float(path["high"].max()) >= context["target_1r"]:
                active_stop = max(active_stop, float(trade.open_rate))
                current_row = self._row_before(dataframe, current_time)
                if current_row is not None:
                    trail = self._float_or_none(current_row.get("native_prior_2h_low_pre"))
                    if trail is not None:
                        active_stop = max(active_stop, trail)

        if active_stop >= current_rate:
            active_stop = current_rate * 0.999
        leverage = float(getattr(trade, "leverage", 1.0) or 1.0)
        return stoploss_from_absolute(active_stop, current_rate, is_short=False, leverage=leverage)

    def custom_exit(
        self,
        pair: str,
        trade: Trade,
        current_time: datetime,
        current_rate: float,
        current_profit: float,
        **kwargs: Any,
    ) -> str | bool | None:
        open_time = trade.open_date_utc
        if open_time.tzinfo is None:
            open_time = open_time.replace(tzinfo=timezone.utc)
        if current_time.tzinfo is None:
            current_time = current_time.replace(tzinfo=timezone.utc)
        if current_time - open_time >= self.MAX_HOLD:
            return "time_exit_24h"
        return None
