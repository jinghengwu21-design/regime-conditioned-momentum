from __future__ import annotations

from datetime import datetime, timezone
import importlib.metadata
import json
from pathlib import Path
from typing import TypedDict
import uuid
import sys

from langgraph.graph import END, START, StateGraph

from .audit import reference_metrics, review
from .data import DataStore, ROOT
from .models import METRIC_INFO, ResearchRequest
from .provider import run_model
from .security import ATTACKS, screen_external
from .tools import ToolRunner


class State(TypedDict, total=False):
    request: dict
    external: dict
    draft: dict
    original_draft: dict
    reviews: list[dict]
    repaired: bool
    result: dict


def canonical_draft(metrics: dict) -> dict:
    claims = [{"metric": key, "value": float(metrics[key]), "unit": unit, "evidence_id": "CALC-BASE"} for key, (_, unit) in METRIC_INFO.items() if metrics.get(key) is not None]
    return {"summary": "历史账户呈现趋势获利与连续亏损交替的特征。评估重点是收益来源、已实现回撤和成交成本敏感性。[CALC-BASE]", "findings": ["使用冻结交易账本重建账户权益，指标与原始记录逐项绑定。[E-BACKTEST]", "成本情景覆盖入场、退出和盈利加仓；固定成交路径便于对照费用变化。[CALC-COST]", "市场状态、突破确认与风险表达共同构成策略研究链路。[E-STRATEGY]"], "claims": claims, "evidence_ids": ["CALC-BASE", "CALC-COST", "E-BACKTEST", "E-STRATEGY"]}


def run_research(request: ResearchRequest, output_root: Path | None = None, store: DataStore | None = None, client=None, model=None) -> dict:
    store = store or DataStore()
    run_id = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ") + "-" + uuid.uuid4().hex[:8]
    run_dir = Path(output_root or ROOT / "outputs/runs") / run_id
    run_dir.mkdir(parents=True, exist_ok=False)
    runner = ToolRunner(store, request, run_dir)
    known = {r["id"] for r in store.evidence} | {"CALC-BASE", "CALC-COST", "E-MARKET"}

    def save(name: str, obj: object):
        (run_dir / name).write_text(json.dumps(obj, ensure_ascii=False, indent=2, allow_nan=False), encoding="utf-8")

    def plan(state: State):
        store.window(request.start, request.end_exclusive)
        save("request.json", request.model_dump())
        runner.event("plan", "freeze_research_scope", request.model_dump(exclude={"external_text"}), {"steps": ["上下文入库", "行情与账本分析", "成本情景", "独立复核", "研究报告"], "dataset": store.manifest["dataset_id"], "question_handling": "LLM interprets question" if request.mode == "openai" else "固定的历史绩效/成本研究模板；自定义问题作为标题保存", "mode": request.mode})
        return {"request": request.model_dump(), "reviews": [], "repaired": False}

    def context(state: State):
        raw = request.external_text or ATTACKS.get(request.scenario, "")
        document = screen_external(raw)
        save("context.json", {"request": request.model_dump(exclude={"external_text"}), "external_document": document, "evidence_ids": [e["id"] for e in store.evidence], "prompt_version": "researcher.v2"})
        runner.event("context", "classify_external_document", {"chars": len(raw), "scenario": request.scenario}, document, "quarantined" if document["quarantined"] else "ok")
        return {"external": document}

    def analysis(state: State):
        if request.scenario == "missing_data":
            # Fault injection is a view-only mutation; packaged files stay unchanged.
            store.market = store.market.loc[store.market.date.dt.strftime("%Y-%m-%d") != "2024-05-20"].copy()
            runner.event("analysis", "inject_missing_market_day", {}, {"fixture": "2024-05-20", "target": "in-memory market view"}, "injected")
        if request.scenario == "tool_abuse":
            runner.call("execute_shell", {"command": "read .env"}, node="context")
        if request.mode == "openai":
            draft = run_model(runner, state["external"], client=client, model=model)
        else:
            scope = {k: getattr(request, k) for k in ("asset", "start", "end_exclusive")}
            for name, arguments in [("read_market", scope), ("read_backtest", scope), ("calculate_metrics", {"fee_bps": request.fee_bps, "slippage_bps": request.slippage_bps}), ("compare_costs", {}), ("search_evidence", {"query": "风险 成本 工程"}), ("read_evidence", {"evidence_id": "E-STRATEGY"})]:
                output = runner.call(name, arguments)
                if "error" in output:
                    raise ValueError(f"Required tool failed: {name}")
            draft = canonical_draft(runner.base["metrics"])
        if request.scenario == "numeric_mismatch":
            for claim in draft["claims"]:
                if claim["metric"] == "total_return":
                    before = claim["value"]
                    claim["value"] += 1.0
                    runner.event("draft", "inject_wrong_number", {"metric": "total_return"}, {"original": before, "injected": claim["value"], "change": "+100 percentage points"}, "injected")
                    break
        save("draft.original.json", draft)
        runner.event("draft", "compose_structured_claims", {"mode": request.mode}, {"claims": draft["claims"], "evidence_ids": draft["evidence_ids"]})
        return {"draft": draft, "original_draft": draft}

    def audit(state: State):
        expected = reference_metrics(store.directory, request.start, request.end_exclusive, request.fee_bps, request.slippage_bps)
        # Verify the displayed engine results too, not just the model's claims.
        engine_review = review(canonical_draft(runner.base["metrics"]), expected, known)
        if not engine_review["passed"]:
            runner.event("review", "engine_integrity", {}, engine_review, "blocked")
            raise ValueError("主计算与独立复核不一致；停止报告导出。")
        for scenario in runner.costs:
            check = reference_metrics(store.directory, request.start, request.end_exclusive, scenario["fee_bps"], scenario["slippage_bps"])
            if not review(canonical_draft(scenario["metrics"]), check, known)["passed"]:
                raise ValueError("成本情景与独立逐成交复核不一致。")
        result = review(state["draft"], expected, known)
        result["cost_scenarios_verified"] = len(runner.costs)
        runner.event("review", "independent_numeric_review", {"attempt": len(state["reviews"]) + 1, "method": "stdlib CSV + raw fill recomputation"}, result, "passed" if result["passed"] else "rejected")
        return {"reviews": state["reviews"] + [result]}

    def repair(state: State):
        fixed = canonical_draft(runner.base["metrics"])
        runner.event("repair", "replace_unverified_draft", {"rejected_findings": state["reviews"][-1]["findings"]}, {"policy": "deterministic evidence-bound replacement", "claims": fixed["claims"]}, "repaired")
        return {"draft": fixed, "repaired": True}

    def route(state: State):
        if state["reviews"][-1]["passed"]:
            return "export"
        if state["repaired"]:
            raise ValueError("复核仍未通过，停止导出。")
        return "repair"

    def export(state: State):
        from .reporting import render_html, render_markdown
        result = {"run_id": run_id, "recorded_at_utc": datetime.now(timezone.utc).isoformat(), "mode": request.mode, "execution_label": "确定性研究" if request.mode == "offline" else "模型研究与工具调用", "request": request.model_dump(exclude={"external_text"}), "dataset": store.manifest, "base": runner.base, "market": runner.market, "costs": runner.costs, "draft": state["draft"], "original_draft": state["original_draft"], "reviews": state["reviews"], "repaired": state["repaired"], "external": state["external"], "evidence": store.evidence_rows(), "prompt": {"version": "researcher.v2"}, "model": model or __import__("os").environ.get("OPENAI_MODEL") if request.mode == "openai" else None, "artifacts": {"report_html": "report.html", "report_markdown": "report.md", "trace": "trace.jsonl"}}
        runner.event("export", "render_cited_report", {"format": ["HTML", "Markdown", "JSONL"]}, {"review_passed": True, "report": "report.html", "numeric_claims": len(state["draft"]["claims"])})
        result["trace"] = runner.events
        result["implementation"] = {"python": sys.version.split()[0], "packages": {name: importlib.metadata.version(name) for name in ["langgraph", "openai", "pandas", "numpy", "plotly", "pydantic"]}}
        save("result.json", result)
        (run_dir / "report.html").write_text(render_html(result), encoding="utf-8")
        (run_dir / "report.md").write_text(render_markdown(result), encoding="utf-8")
        result["local_run_dir"] = str(run_dir)
        return {"result": result}

    graph = StateGraph(State)
    for name, fn in [("plan", plan), ("context", context), ("analysis", analysis), ("review", audit), ("repair", repair), ("export", export)]:
        graph.add_node(name, fn)
    graph.add_edge(START, "plan")
    graph.add_edge("plan", "context")
    graph.add_edge("context", "analysis")
    graph.add_edge("analysis", "review")
    graph.add_conditional_edges("review", route, {"export": "export", "repair": "repair"})
    graph.add_edge("repair", "review")
    graph.add_edge("export", END)
    try:
        return graph.compile().invoke({"request": request.model_dump()})["result"]
    except Exception as error:
        save("failure.json", {"run_id": run_id, "error_class": type(error).__name__, "status": "failed", "events": len(runner.events)})
        raise
