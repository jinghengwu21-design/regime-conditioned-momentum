"""Check that the archived strategy sources are present and parse as Python."""
import ast
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
manifest = json.loads((ROOT / "strategy/manifest.json").read_text(encoding="utf-8"))
for name in manifest["files"]:
    path = ROOT / "strategy/frozen" / name
    ast.parse(path.read_text(encoding="utf-8-sig"), filename=name)
print(f"Parsed {len(manifest['files'])} strategy source files ({manifest['source_class']}).")
