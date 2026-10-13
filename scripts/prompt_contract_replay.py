"""Replay a numeric-error fixture through old prose and current claim contracts.

This is a local contract replay, not a model-quality A/B experiment.
"""
from datetime import datetime, timezone
import difflib
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from research_agent.audit import review
from research_agent.data import DataStore
from research_agent.metrics import calculate
from research_agent.models import ResearchRequest
from research_agent.workflow import canonical_draft

request = ResearchRequest()
metrics = calculate(DataStore(), request.start, request.end_exclusive)["metrics"]
draft = canonical_draft(metrics)
draft["claims"][0]["value"] = 999.0
result = review(draft, metrics, {"CALC-BASE", "CALC-COST", "E-BACKTEST", "E-STRATEGY"})
before = (ROOT / "prompts/researcher.v1.txt").read_text(encoding="utf-8")
after = (ROOT / "prompts/researcher.v2.txt").read_text(encoding="utf-8")
output = ROOT / "outputs/prompt_contract_replay.json"
output.parent.mkdir(exist_ok=True)
output.write_text(json.dumps({"recorded_at_utc": datetime.now(timezone.utc).isoformat(), "kind": "local_contract_replay_not_model_ab", "fixture": {"metric": "trade_count", "value": 999}, "v1_free_prose": {"text": "该策略完成 999 笔交易。", "numeric_validation": "absent"}, "v2_claim_review": result, "diff": "".join(difflib.unified_diff(before.splitlines(True), after.splitlines(True), fromfile="researcher.v1", tofile="researcher.v2"))}, ensure_ascii=False, indent=2), encoding="utf-8")
print(output)

