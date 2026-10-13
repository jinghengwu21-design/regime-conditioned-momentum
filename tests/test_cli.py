"""CLI output stays portable across Windows console encodings."""
import json
import os
from pathlib import Path
import subprocess
import sys


def test_cli_emits_utf8_json_under_legacy_console(tmp_path):
    env = dict(os.environ, PYTHONIOENCODING="cp1252", PYTHONUTF8="0")
    result = subprocess.run(
        [sys.executable, "-m", "research_agent.cli", "demo", "--output", str(tmp_path)],
        cwd=Path(__file__).resolve().parents[1], env=env, capture_output=True,
        timeout=60, check=True,
    )
    payload = json.loads(result.stdout.decode("utf-8"))
    assert payload["metrics"]["trade_count"] == 922
    assert payload["review_passed"] is True
