from __future__ import annotations

from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
from time import perf_counter

from pydantic import BaseModel, ConfigDict, Field

from .data import DataStore
from .metrics import calculate, market_snapshot
from .models import ResearchRequest


class EmptyArgs(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)


class ScopeArgs(EmptyArgs):
    asset: str
    start: str
    end_exclusive: str


class CostArgs(EmptyArgs):
    fee_bps: float = Field(ge=0, le=50, allow_inf_nan=False)
    slippage_bps: float = Field(ge=0, le=50, allow_inf_nan=False)


class SearchArgs(EmptyArgs):
    query: str = Field(min_length=1, max_length=160)


class EvidenceArgs(EmptyArgs):
    evidence_id: str = Field(pattern=r"^E-[A-Z]+$")


CONTRACTS = {
    "read_market": (ScopeArgs, "读取授权研究区间的行情覆盖、日线样本和缺口。"),
    "read_backtest": (ScopeArgs, "读取冻结回测身份、交易范围与费用口径。"),
    "calculate_metrics": (CostArgs, "计算当前请求的账户收益、已实现回撤、Sharpe 等；手续费及滑点必须与请求一致。"),
    "compare_costs": (EmptyArgs, "固定已成交订单路径，比较单边 5、8、12 bps 与请求费用；包含加仓。"),
    "search_evidence": (SearchArgs, "在版本化本地证据库中检索研究与工程证据；无网络或文件写权限。"),
    "read_evidence": (EvidenceArgs, "按证据编号读取本地来源摘要。"),
}


class ToolDenied(ValueError):
    pass


def schemas() -> list[dict]:
    return [{"type": "function", "name": name, "description": description, "parameters": cls.model_json_schema(), "strict": True} for name, (cls, description) in CONTRACTS.items()]


class ToolRunner:
    def __init__(self, store: DataStore, request: ResearchRequest, run_dir: Path):
        self.store, self.request, self.run_dir = store, request, run_dir
        self.events: list[dict] = []
        self.market: dict = {}
        self.base: dict = {}
        self.costs: list[dict] = []

    def event(self, node: str, action: str, inputs: dict, output: dict, status: str = "ok", elapsed_ms: float = 0) -> dict:
        record = {"sequence": len(self.events) + 1, "time_utc": datetime.now(timezone.utc).isoformat(), "node": node, "action": action, "status": status, "elapsed_ms": round(elapsed_ms, 2), "input": inputs, "output": output, "output_sha256": hashlib.sha256(json.dumps(output, ensure_ascii=False, sort_keys=True, allow_nan=False).encode()).hexdigest()}
        self.events.append(record)
        with (self.run_dir / "trace.jsonl").open("a", encoding="utf-8") as file:
            file.write(json.dumps(record, ensure_ascii=False, allow_nan=False) + "\n")
        return record

    def call(self, name: str, arguments: dict, node: str = "analysis") -> dict:
        before = perf_counter()
        try:
            if name not in CONTRACTS:
                raise ToolDenied("工具不在只读金融研究白名单中。")
            parsed = CONTRACTS[name][0].model_validate(arguments)
            if isinstance(parsed, ScopeArgs):
                expected = {k: getattr(self.request, k) for k in ("asset", "start", "end_exclusive")}
                if parsed.model_dump() != expected:
                    raise ToolDenied("工具不能改写用户确认的资产或时间范围。")
            if isinstance(parsed, CostArgs) and (parsed.fee_bps != self.request.fee_bps or parsed.slippage_bps != self.request.slippage_bps):
                raise ToolDenied("主指标费用必须匹配请求；请用 compare_costs 查看其他费用。")
            result = self._execute(name, parsed.model_dump())
        except Exception as error:
            result = {"error": type(error).__name__, "message": str(error)[:300] if isinstance(error, ToolDenied) else "参数或数据不符合工具契约。"}
            self.event(node, name, arguments, result, "denied", (perf_counter() - before) * 1000)
            return result
        self.event(node, name, arguments, result, "ok", (perf_counter() - before) * 1000)
        return result

    def _execute(self, name: str, args: dict) -> dict:
        req, store = self.request, self.store
        if name == "read_market":
            self.market = market_snapshot(store, req.start, req.end_exclusive)
            return {"evidence_id": "E-MARKET", **{k: v for k, v in self.market.items() if k != "bars"}, "recent_bars": self.market["bars"][-5:]}
        if name == "read_backtest":
            m = store.manifest
            return {"evidence_id": "E-BACKTEST", **{k: m[k] for k in ["dataset_id", "strategy", "engine", "engine_timeframe", "start", "end_exclusive", "metric_start", "metric_end", "base_fee_bps_per_side", "funding", "equity_basis", "code_fingerprint"]}, "source_archive_sha256": m["original_archive"]["sha256"], "ledger_trades": len(store.trades)}
        if name == "calculate_metrics":
            self.base = calculate(store, req.start, req.end_exclusive, **args)
            return {"evidence_id": "CALC-BASE", **{k: v for k, v in self.base.items() if k not in ("curve", "yearly")}}
        if name == "compare_costs":
            self.costs = []
            for fee in sorted({5.0, 8.0, 12.0, req.fee_bps}):
                result = calculate(store, req.start, req.end_exclusive, fee, req.slippage_bps)
                self.costs.append({"fee_bps": fee, "slippage_bps": req.slippage_bps, "metrics": result["metrics"], "curve": result["curve"]})
            return {"evidence_id": "CALC-COST", "assumption": "固定成交路径、全量进出/加仓名义金额、平仓追加成本；不重算仓位或资金费。", "scenarios": [{k: v for k, v in s.items() if k != "curve"} for s in self.costs]}
        if name == "search_evidence":
            query = args["query"].lower()
            terms = query.split()
            rows = sorted(store.evidence_rows(), key=lambda r: sum(t in (r["title"] + r["text"]).lower() for t in terms), reverse=True)
            return {"results": rows[:4], "retrieval": "bounded lexical ranking over curated evidence; no embedding index"}
        if name == "read_evidence":
            for row in store.evidence_rows():
                if row["id"] == args["evidence_id"]:
                    return row
            raise ToolDenied("不存在的证据编号。")
        raise ToolDenied("Unknown tool")
