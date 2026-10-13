from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd


OHLCV_COLUMNS = ["open", "high", "low", "close", "volume"]


class RegimeRecognitionError(RuntimeError):
    """Raised when a market-state recognizer cannot produce causal labels."""


def safe_divide(numerator: pd.Series, denominator: pd.Series) -> pd.Series:
    return numerator / denominator.replace(0, np.nan)


def normalize_ohlcv_frame(
    dataframe: pd.DataFrame,
    *,
    date_col: str = "date",
    required_columns: list[str] | None = None,
) -> pd.DataFrame:
    required = [date_col, *(required_columns or OHLCV_COLUMNS)]
    missing = [col for col in required if col not in dataframe.columns]
    if missing:
        raise RegimeRecognitionError(f"Missing required OHLCV columns: {missing}")

    out = dataframe.copy()
    out[date_col] = pd.to_datetime(out[date_col], utc=True)
    out = out.sort_values(date_col).reset_index(drop=True)
    for col in required_columns or OHLCV_COLUMNS:
        out[col] = out[col].astype(float)
    return out


def attach_state_asof(
    left: pd.DataFrame,
    state: pd.DataFrame | str | Path,
    *,
    left_on: str = "date",
    right_on: str = "date",
    direction: str = "backward",
    tolerance: pd.Timedelta | None = None,
    drop_right_on: bool = False,
) -> pd.DataFrame:
    left_frame = left.copy()
    left_frame[left_on] = pd.to_datetime(left_frame[left_on], utc=True)

    if isinstance(state, (str, Path)):
        path = Path(state)
        if path.suffix.lower() == ".feather":
            state_frame = pd.read_feather(path)
        elif path.suffix.lower() == ".csv":
            state_frame = pd.read_csv(path)
        else:
            raise RegimeRecognitionError(f"Unsupported state table format: {path}")
    else:
        state_frame = state.copy()

    state_frame[right_on] = pd.to_datetime(state_frame[right_on], utc=True)
    out = pd.merge_asof(
        left_frame.sort_values(left_on),
        state_frame.sort_values(right_on),
        left_on=left_on,
        right_on=right_on,
        direction=direction,
        tolerance=tolerance,
    )
    if drop_right_on and right_on != left_on and right_on in out.columns:
        out = out.drop(columns=[right_on])
    return out
