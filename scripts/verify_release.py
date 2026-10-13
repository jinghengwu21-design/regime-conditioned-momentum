"""Verify archive integrity and execute a demo from a fresh extracted checkout."""
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import subprocess
import sys
import uuid
import zipfile

ROOT = Path(__file__).resolve().parents[1]
archive = ROOT / "dist/regime-conditioned-momentum.zip"
target = ROOT / "outputs" / ("package-smoke-" + uuid.uuid4().hex[:8])
target.mkdir(parents=True, exist_ok=False)
with zipfile.ZipFile(archive) as bundle:
    for name in bundle.namelist():
        resolved = (target / name).resolve()
        if not resolved.is_relative_to(target.resolve()):
            raise ValueError("Archive path leaves extraction directory")
    bundle.extractall(target)
checkout = target / "regime-conditioned-momentum"
manifest = json.loads((checkout / "release-manifest.json").read_text(encoding="utf-8"))
for name, expected in manifest["files"].items():
    if not (checkout / name).is_file():
        raise ValueError("Archive file missing: " + name)
env = dict(os.environ)
env.pop("PYTHONPATH", None)
env["PYTHONUTF8"] = "1"
result = subprocess.run([sys.executable, "-m", "research_agent.cli", "demo", "--output", str(target / "runs")], cwd=checkout, env=env, capture_output=True, text=True, encoding="utf-8", timeout=60, check=True)
run = json.loads(result.stdout)
record = {"verified_at_utc": datetime.now(timezone.utc).isoformat(), "files_verified": len(manifest["files"]), "fresh_extracted_checkout": True, "run_id": run["run_id"], "trade_count": run["metrics"]["trade_count"], "review_passed": run["review_passed"]}
(ROOT / "dist/smoke-test.json").write_text(json.dumps(record, ensure_ascii=False, indent=2), encoding="utf-8")
print(json.dumps(record, ensure_ascii=False, indent=2))

