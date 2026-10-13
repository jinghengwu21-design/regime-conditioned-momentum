from __future__ import annotations

import argparse
import json
from pathlib import Path
import shutil

from .data import ROOT
from .models import ResearchRequest
from .workflow import run_research


def main():
    parser = argparse.ArgumentParser(description="金融研究 Agent 工作台")
    parser.add_argument("command", choices=["demo", "run", "evaluate"], nargs="?", default="demo")
    parser.add_argument("--mode", choices=["offline", "openai"], default="offline")
    parser.add_argument("--scenario", choices=["normal", "prompt_injection", "numeric_mismatch", "missing_data", "tool_abuse"], default="normal")
    parser.add_argument("--fee-bps", type=float, default=5)
    parser.add_argument("--slippage-bps", type=float, default=0)
    parser.add_argument("--start", default=ResearchRequest.model_fields["start"].default)
    parser.add_argument("--end-exclusive", default=ResearchRequest.model_fields["end_exclusive"].default)
    parser.add_argument("--question", default=ResearchRequest.model_fields["question"].default)
    parser.add_argument("--output", type=Path)
    parser.add_argument("--save-example", action="store_true")
    args = parser.parse_args()
    if args.command == "evaluate":
        from .evaluation import evaluate
        report = evaluate(args.output or ROOT / "outputs/evaluation")
        print(json.dumps(report, ensure_ascii=False, indent=2))
        if not report["all_passed"]:
            raise SystemExit(1)
        return
    request = ResearchRequest(mode=args.mode, scenario=args.scenario, fee_bps=args.fee_bps, slippage_bps=args.slippage_bps, start=args.start, end_exclusive=args.end_exclusive, question=args.question)
    result = run_research(request, output_root=args.output)
    if args.save_example:
        dest = ROOT / "examples" / ("default" if args.scenario == "normal" else args.scenario)
        dest.mkdir(parents=True, exist_ok=True)
        for name in ["request.json", "context.json", "result.json", "trace.jsonl", "draft.original.json", "report.html", "report.md"]:
            shutil.copy2(Path(result["local_run_dir"]) / name, dest / name)
    print(json.dumps({"run_id": result["run_id"], "mode": result["mode"], "metrics": result["base"]["metrics"], "review_passed": result["reviews"][-1]["passed"], "report": str(Path(result["local_run_dir"]) / "report.html")}, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
