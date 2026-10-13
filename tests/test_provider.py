"""Real OpenAI SDK exercised over mocked HTTP, not a live model evaluation."""
import json

import httpx
from openai import OpenAI
import pytest

from research_agent.data import DataStore
from research_agent.metrics import calculate
from research_agent.models import ResearchRequest
from research_agent.provider import ProviderError, run_model
from research_agent.tools import ToolRunner, schemas
from research_agent.workflow import canonical_draft, run_research


def response(index, output):
    return {"id": f"resp_contract_{index}", "object": "response", "created_at": 1791878400, "status": "completed", "model": "contract-test-model", "output": output, "usage": {"input_tokens": 100, "output_tokens": 100, "total_tokens": 200, "input_tokens_details": {"cached_tokens": 0}, "output_tokens_details": {"reasoning_tokens": 0}}}


def tool(index, name, args):
    return {"type": "function_call", "id": f"fc_{index}", "call_id": f"call_{index}", "name": name, "arguments": json.dumps(args), "status": "completed"}


def message(draft):
    return {"type": "message", "id": "msg_final", "status": "completed", "role": "assistant", "content": [{"type": "output_text", "text": json.dumps(draft), "annotations": []}]}


def test_sdk_function_call_roundtrip_and_review(tmp_path):
    req = ResearchRequest(mode="openai")
    store = DataStore()
    baseline = calculate(store, req.start, req.end_exclusive)
    bad_draft = canonical_draft(baseline["metrics"])
    bad_draft["claims"][0]["value"] = 999.0
    scope = {k: getattr(req, k) for k in ["asset", "start", "end_exclusive"]}
    calls = [("read_market", scope), ("read_backtest", scope), ("calculate_metrics", {"fee_bps": 5.0, "slippage_bps": 0.0}), ("compare_costs", {}), ("search_evidence", {"query": "成本 风险"}), ("read_evidence", {"evidence_id": "E-STRATEGY"})]
    requests = []

    def handle(request):
        payload = json.loads(request.content)
        requests.append(payload)
        i = len(requests) - 1
        assert payload["store"] is False
        assert payload["parallel_tool_calls"] is False
        if i:
            assert any(x["type"] == "function_call_output" for x in payload["input"] if "type" in x)
        output = [tool(i, *calls[i])] if i < len(calls) else [message(bad_draft)]
        return httpx.Response(200, json=response(i, output))

    client = OpenAI(api_key="contract-test-not-a-real-key", http_client=httpx.Client(transport=httpx.MockTransport(handle)))
    result = run_research(req, output_root=tmp_path, client=client, model="contract-test-model")
    assert len(requests) == 7
    assert result["repaired"]
    assert result["reviews"][-1]["passed"]
    assert result["reviews"][0]["findings"][0]["code"] == "NUMERIC_MISMATCH"
    assert result["base"]["metrics"]["trade_count"] == 922


def test_missing_model_settings_does_not_silently_fake_a_run(monkeypatch, tmp_path):
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    monkeypatch.delenv("OPENAI_MODEL", raising=False)
    runner = ToolRunner(DataStore(), ResearchRequest(mode="openai"), tmp_path)
    with pytest.raises(ProviderError, match="OPENAI_API_KEY"):
        run_model(runner, {})
    assert not any(e["action"] == "model_request" for e in runner.events)


def test_unbounded_model_tool_loop_is_stopped(tmp_path):
    counter = []

    def handle(request):
        counter.append(1)
        return httpx.Response(200, json=response(len(counter), [tool(len(counter), "execute_shell", {"cmd": "read .env"})]))

    client = OpenAI(api_key="contract-test", http_client=httpx.Client(transport=httpx.MockTransport(handle)))
    runner = ToolRunner(DataStore(), ResearchRequest(mode="openai"), tmp_path)
    with pytest.raises(ProviderError, match="限定轮次"):
        run_model(runner, {}, client=client)
    assert len(counter) == 8
    assert sum(e["status"] == "denied" for e in runner.events) == 8


def test_all_tool_schemas_forbid_unexpected_fields():
    for schema in schemas():
        assert schema["strict"]
        assert schema["parameters"]["additionalProperties"] is False
        assert set(schema["parameters"].get("required", [])) == set(schema["parameters"]["properties"])
