"""Bounded Responses API loop; the model chooses and calls real local tools."""
from __future__ import annotations

import json
import os
from time import perf_counter

from .data import ROOT
from .models import Draft
from .tools import ToolRunner, schemas


class ProviderError(RuntimeError):
    pass


def run_model(runner: ToolRunner, external: dict, client=None, model: str | None = None) -> dict:
    if client is None:
        from openai import OpenAI
        if not os.environ.get("OPENAI_API_KEY") or not (model or os.environ.get("OPENAI_MODEL")):
            raise ProviderError("模型模式需要在启动终端设置 OPENAI_API_KEY 和 OPENAI_MODEL；离线示例可立即运行。")
        # Endpoint is fixed; untrusted model/tool text cannot redirect credentials.
        client = OpenAI(api_key=os.environ["OPENAI_API_KEY"], base_url="https://api.openai.com/v1", timeout=45, max_retries=1)
    model = model or os.environ.get("OPENAI_MODEL", "contract-test-model")
    prompt = (ROOT / "prompts/researcher.v2.txt").read_text(encoding="utf-8")
    context = {"request": {k: v for k, v in runner.request.model_dump().items() if k not in ("external_text", "scenario")}, "external_document": external, "plan": ["行情及样本完整性", "历史回测及数值核验", "成本压力", "证据检索", "结构化研究结论"]}
    messages = [{"role": "user", "content": json.dumps(context, ensure_ascii=False)}]
    call_count = 0
    called = set()
    for iteration in range(8):
        before = perf_counter()
        try:
            response = client.responses.create(model=model, instructions=prompt, input=messages, tools=schemas(), parallel_tool_calls=False, store=False, max_output_tokens=2600, text={"format": {"type": "json_schema", "name": "research_draft", "schema": Draft.model_json_schema(), "strict": True}})
        except Exception as error:
            runner.event("analysis", "model_request", {"model": model, "iteration": iteration + 1}, {"error_class": type(error).__name__}, "error", (perf_counter() - before) * 1000)
            raise ProviderError("模型请求失败；检查账号、模型权限或网络。诊断轨迹只记录错误类型。") from None
        usage = response.usage.model_dump() if getattr(response, "usage", None) else {}
        runner.event("analysis", "model_request", {"model": model, "iteration": iteration + 1}, {"response_id": response.id, "usage": usage, "execution": "provider_response"}, elapsed_ms=(perf_counter() - before) * 1000)
        calls = []
        for item in response.output:
            messages.append(item.model_dump(exclude_none=True))
            if item.type == "function_call":
                calls.append(item)
        if not calls:
            required = {"read_market", "read_backtest", "calculate_metrics", "compare_costs", "search_evidence"}
            if required - called:
                messages.append({"role": "user", "content": "请先完成实际工具调用：" + ", ".join(sorted(required - called))})
                continue
            try:
                return Draft.model_validate_json(response.output_text).model_dump()
            except Exception:
                raise ProviderError("模型未返回符合契约的结构化研究报告。") from None
        for call in calls:
            call_count += 1
            if call_count > 12:
                raise ProviderError("已达到单次研究的工具调用上限。")
            try:
                args = json.loads(call.arguments)
            except (TypeError, json.JSONDecodeError):
                args = {"_invalid_json": True}
            if not isinstance(args, dict):
                args = {"_invalid_arguments": True}
            result = runner.call(call.name, args)
            if "error" not in result:
                called.add(call.name)
            messages.append({"type": "function_call_output", "call_id": call.call_id, "output": json.dumps(result, ensure_ascii=False, allow_nan=False)})
    raise ProviderError("模型未在限定轮次内完成研究。")

