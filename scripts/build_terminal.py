"""Build reproducible browser artifacts. No network or model access is required."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
import shutil
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from research_agent.analytics import portfolio_analytics
from research_agent.data import DataStore
from research_agent.models import ResearchRequest
from research_agent.workflow import run_research

PERIODS = {
    "all": ("2020-01-01T00:00:00+00:00", "2026-10-03T12:05:00+00:00"),
    "2020-2023": ("2020-01-01T00:00:00+00:00", "2024-01-01T00:00:00+00:00"),
    "2024-2025": ("2024-01-01T00:00:00+00:00", "2026-01-01T00:00:00+00:00"),
    "2026": ("2026-01-01T00:00:00+00:00", "2026-10-03T12:05:00+00:00"),
}


def main():
    target = ROOT / "web/public/data"
    target.mkdir(parents=True, exist_ok=True)
    store = DataStore()
    payload = {"version": "2.0.0", "asof": "2026-10-03T12:05:00Z", "manifest": store.manifest,
               "periods": {key: portfolio_analytics(store, *dates) for key, dates in PERIODS.items()},
               "evidence": store.evidence_rows()}
    (target / "terminal.json").write_text(json.dumps(payload, ensure_ascii=False, allow_nan=False, separators=(",", ":")), encoding="utf-8")
    experiments = {}
    for scenario in ["normal", "numeric_mismatch", "prompt_injection", "missing_data", "tool_abuse"]:
        result = run_research(ResearchRequest(scenario=scenario))
        run_dir = Path(result.pop("local_run_dir"))
        experiments[scenario] = result
        if scenario == "normal":
            shutil.copy2(run_dir / "report.html", target / "report.html")
            shutil.copy2(run_dir / "report.md", target / "report.md")
    (target / "experiments.json").write_text(json.dumps(experiments, ensure_ascii=False, allow_nan=False, separators=(",", ":")), encoding="utf-8")
    for name in ["trades.csv", "fills.csv", "manifest.json"]:
        shutil.copy2(ROOT / "data" / name, target / name)
    fingerprint = {p.name: {"sha256": hashlib.sha256(p.read_bytes()).hexdigest(), "bytes": p.stat().st_size}
                   for p in sorted(target.glob("*")) if p.name != "build-manifest.json"}
    (target / "build-manifest.json").write_text(json.dumps(fingerprint, indent=2), encoding="utf-8")
    print(json.dumps({"periods": len(PERIODS), "experiments": len(experiments), "files": fingerprint}))


if __name__ == "__main__":
    main()
