"""Verify the frozen strategy against its original source manifest."""
import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
manifest = json.loads((ROOT / "strategy/manifest.json").read_text())
for name, expected in manifest["files"].items():
    path = (ROOT / "strategy/frozen" / name).resolve()
    if not path.is_relative_to((ROOT / "strategy/frozen").resolve()):
        raise ValueError("Source path outside snapshot")
    if hashlib.sha256(path.read_bytes()).hexdigest() != expected:
        raise ValueError(f"Source identity mismatch: {name}")
print(f"Verified {len(manifest['files'])} frozen source files.")
