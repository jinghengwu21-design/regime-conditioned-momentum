"""Independent stdlib reviewer: rebuild metrics directly from packaged CSV.

No imports from metrics.py. A calculation regression cannot automatically become
the review's expected answer. Independent raw fills also validate cost exposure.
"""
from __future__ import annotations

import csv
from datetime import datetime, timedelta, timezone
import json
import math
from pathlib import Path
import re
import statistics

from .models import Draft, METRIC_INFO
from .security import narrative_has_numbers


def dt(value: str) -> datetime:
    return datetime.fromisoformat(value.replace("Z", "+00:00"))


def reference_metrics(directory: Path, start: str, end: str, fee: float, slip: float) -> dict:
    meta = json.loads((directory / "manifest.json").read_text(encoding="utf-8"))
    left, right = max(dt(start), dt(meta["start"])), min(dt(end), dt(meta["end_exclusive"]))
    if left >= right:
        raise ValueError("No overlap")
    with (directory / "trades.csv").open(encoding="utf-8", newline="") as file:
        rows = sorted(csv.DictReader(file), key=lambda x: (dt(x["close_date"]), dt(x["open_date"]), x["trade_id"]))
    notionals = {}
    with (directory / "fills.csv").open(encoding="utf-8", newline="") as file:
        for fill in csv.DictReader(file):
            notional = float(fill["amount"]) * float(fill["price"])
            notionals[fill["trade_id"]] = notionals.get(fill["trade_id"], 0.0) + notional
    opening = float(meta["starting_balance"]) + math.fsum(float(t["profit_abs"]) for t in rows if dt(t["close_date"]) < left)
    selected = [t for t in rows if left <= dt(t["close_date"]) < right]
    rate = (fee - float(meta["base_fee_bps_per_side"]) + slip) / 10000
    pnl, events, daily = [], {}, {}
    extra = 0.0
    for row in selected:
        stamp = dt(row["close_date"])
        turnover = notionals[row["trade_id"]]
        ledger_turnover = float(row["entry_notional_usdt"]) + float(row["exit_notional_usdt"])
        if not math.isclose(turnover, ledger_turnover, rel_tol=1e-9, abs_tol=1e-5):
            raise ValueError(f"Fill notional mismatch: {row['trade_id']}")
        cost = turnover * rate
        extra += cost
        profit = float(row["profit_abs"]) - cost
        if abs(profit) < 0.0000001:
            profit = 0.0
        pnl.append(profit)
        events[stamp] = events.get(stamp, 0.0) + profit
        daily[stamp.date()] = daily.get(stamp.date(), 0.0) + profit
    balance, peak, max_dd, solvent = opening, opening, 0.0, opening > 0
    for _, value in sorted(events.items()):
        balance += value
        peak = max(peak, balance)
        max_dd = max(max_dd, 1 - balance / peak)
        solvent = solvent and balance > 0
    final = opening + math.fsum(pnl)
    current, last = left.date(), (right - timedelta(microseconds=1)).date()
    daily_returns, daily_balance = [], opening
    while current <= last:
        day_pnl = daily.get(current, 0.0)
        daily_returns.append(day_pnl / daily_balance if daily_balance else 0.0)
        daily_balance += day_pnl
        current += timedelta(days=1)
    days = (min(right, dt(meta["metric_end"])) - max(left, dt(meta["metric_start"]))).days
    sd = statistics.stdev(daily_returns) if len(daily_returns) > 1 else 0
    gains = math.fsum(x for x in pnl if x > 0)
    losses = -math.fsum(x for x in pnl if x < 0)
    return {"trade_count": len(selected), "total_return": final / opening - 1, "cagr": (final / opening) ** (365 / days) - 1 if days > 0 and solvent else None, "max_drawdown": max_dd, "daily_sharpe": statistics.mean(daily_returns) / sd * math.sqrt(365) if sd and solvent else None, "profit_factor": gains / losses if losses else None, "win_rate": sum(x > 0 for x in pnl) / len(pnl) if pnl else None, "final_equity": final, "added_fee_usdt": extra}


def review(draft: dict, expected: dict, known_evidence: set[str]) -> dict:
    findings = []
    try:
        parsed = Draft.model_validate(draft)
    except Exception:
        return {"passed": False, "checked_claims": 0, "findings": [{"code": "INVALID_DRAFT", "detail": "输出不符合研究报告契约"}], "reviewer": "independent-python-review-v1"}
    seen = set()
    for claim in parsed.claims:
        key = claim.metric
        if key in seen:
            findings.append({"code": "DUPLICATE_METRIC", "metric": key})
        seen.add(key)
        if key not in METRIC_INFO or key not in expected:
            findings.append({"code": "UNKNOWN_METRIC", "metric": key})
        elif expected[key] is None or not math.isclose(claim.value, expected[key], rel_tol=1e-8, abs_tol=1e-7):
            findings.append({"code": "NUMERIC_MISMATCH", "metric": key, "observed": claim.value, "expected": expected[key]})
        elif claim.unit != METRIC_INFO[key][1]:
            findings.append({"code": "UNIT_MISMATCH", "metric": key, "expected": METRIC_INFO[key][1]})
        if claim.evidence_id != "CALC-BASE":
            findings.append({"code": "WRONG_NUMERIC_SOURCE", "metric": key, "evidence_id": claim.evidence_id})
    required = {k for k in ["trade_count", "total_return", "cagr", "max_drawdown", "daily_sharpe"] if expected.get(k) is not None}
    if required - seen:
        findings.append({"code": "MISSING_KEY_CLAIMS", "metrics": sorted(required - seen)})
    if any(e not in known_evidence for e in parsed.evidence_ids):
        findings.append({"code": "UNKNOWN_CITATION"})
    if "CALC-BASE" not in parsed.evidence_ids:
        findings.append({"code": "MISSING_CALC_CITATION"})
    narrative = parsed.summary + "\n" + "\n".join(parsed.findings)
    inline = set(re.findall(r"\[((?:E|CALC)-[A-Z-]+)\]", narrative))
    if inline - known_evidence or inline - set(parsed.evidence_ids):
        findings.append({"code": "UNBOUND_INLINE_CITATION"})
    if re.search(r"稳赚|必赚|保证收益|无风险收益|保证盈利|guaranteed\s*(profit|return)", narrative, re.I):
        findings.append({"code": "UNSUPPORTED_GUARANTEE"})
    if narrative_has_numbers(narrative):
        findings.append({"code": "UNBOUND_PROSE_NUMBER", "detail": "数字必须通过结构化指标及证据引用生成。"})
    return {"passed": not findings, "checked_claims": len(parsed.claims), "findings": findings, "reviewer": "independent-python-review-v1"}

