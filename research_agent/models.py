from __future__ import annotations

from typing import Literal
import pandas as pd
from pydantic import BaseModel, ConfigDict, Field, model_validator


class ResearchRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    question: str = Field(default="BTC 动量策略的历史表现有多稳健？提高交易成本后，收益和回撤如何变化？", min_length=5, max_length=600)
    asset: Literal["BTC/USDT:USDT"] = "BTC/USDT:USDT"
    start: str = "2020-01-01T00:00:00+00:00"
    end_exclusive: str = "2026-10-03T12:05:00+00:00"
    fee_bps: float = Field(default=5.0, ge=0, le=50, allow_inf_nan=False)
    slippage_bps: float = Field(default=0.0, ge=0, le=50, allow_inf_nan=False)
    mode: Literal["offline", "openai"] = "offline"
    scenario: Literal["normal", "prompt_injection", "numeric_mismatch", "missing_data", "tool_abuse"] = "normal"
    external_text: str = Field(default="", max_length=8000)

    @model_validator(mode="after")
    def dates(self):
        start, end = pd.Timestamp(self.start), pd.Timestamp(self.end_exclusive)
        if start.tzinfo is None or end.tzinfo is None:
            raise ValueError("时间必须含时区；本项目统一采用 UTC。")
        if not start < end or (end - start).total_seconds() < 86400:
            raise ValueError("请选择至少一天的有效研究区间。")
        if start.year < 1900 or end.year > 2100:
            raise ValueError("研究区间超出支持范围。")
        self.start = start.tz_convert("UTC").isoformat()
        self.end_exclusive = end.tz_convert("UTC").isoformat()
        return self


class Claim(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    metric: str
    value: float = Field(allow_inf_nan=False)
    unit: Literal["ratio", "number", "USDT"]
    evidence_id: str


class Draft(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    summary: str = Field(max_length=1400)
    findings: list[str] = Field(max_length=8)
    claims: list[Claim] = Field(min_length=1, max_length=20)
    evidence_ids: list[str] = Field(min_length=1, max_length=12)


METRIC_INFO = {
    "trade_count": ("交易笔数", "number"),
    "total_return": ("累计收益", "ratio"),
    "cagr": ("复合年化收益", "ratio"),
    "max_drawdown": ("最大已实现回撤", "ratio"),
    "daily_sharpe": ("每日账户收益 Sharpe", "number"),
    "profit_factor": ("盈利因子 PF", "number"),
    "win_rate": ("胜率", "ratio"),
    "final_equity": ("期末权益", "USDT"),
    "added_fee_usdt": ("额外成本", "USDT"),
}


def format_metric(key: str, value: float | None) -> str:
    if value is None:
        return "不适用"
    unit = METRIC_INFO[key][1]
    if unit == "ratio":
        return f"{value:.2%}"
    if key == "trade_count":
        return f"{value:,.0f}"
    if unit == "USDT":
        return f"{value:,.2f}"
    return f"{value:.3f}"

