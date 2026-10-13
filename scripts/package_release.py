"""Build a portable portfolio ZIP from an explicit public-artifact allowlist."""
from __future__ import annotations

from datetime import datetime, timezone
import json
from pathlib import Path
import re
import zipfile

ROOT = Path(__file__).resolve().parents[1]
FILES = {"README.md", "LICENSE", "THIRD_PARTY_NOTICES.md", "CONTRIBUTING.md", "CHANGELOG.md", "pyproject.toml", "requirements.lock", "app.py", "Dockerfile", ".env.example", ".gitignore", ".gitattributes", ".dockerignore"}
DIRECTORIES = {"research_agent", "data", "references", "prompts", "scripts", "tests", "docs", "examples", ".github", "web", "strategy", "research"}
OUTPUTS = {"outputs/test-results.xml", "outputs/frontend-tests.xml", "outputs/browser-validation.json", "outputs/evaluation/evaluation.json", "outputs/prompt_contract_replay.json", "outputs/verification.json"}
TEXT = {".py", ".md", ".txt", ".json", ".jsonl", ".csv", ".toml", ".yml", ".yaml", ".ps1", ".example", ".ts", ".tsx", ".css", ".html", ".svg", ".xml", ".lock"}
SECRET_PATTERNS = [re.compile(r"sk-(?:proj-)?[A-Za-z0-9_-]{30,}"), re.compile(r"-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----")]


def main():
    candidates = [ROOT / name for name in FILES]
    for directory in DIRECTORIES:
        candidates.extend(p for p in (ROOT / directory).rglob("*") if p.is_file())
    candidates.extend(ROOT / p for p in OUTPUTS if (ROOT / p).exists())
    files = []
    for path in sorted(set(candidates)):
        if not path.is_file() or any(part in path.parts for part in {"__pycache__", "node_modules", "dist"}) or path.suffix in {".pyc", ".tsbuildinfo"}:
            continue
        if path.name in {"secrets.toml", ".env"} or path.suffix in {".db", ".sqlite", ".sqlite3", ".pem"}:
            raise ValueError(f"Unexpected private file in public tree: {path.name}")
        if path.suffix in TEXT:
            content = path.read_text(encoding="utf-8-sig")
            if any(pattern.search(content) for pattern in SECRET_PATTERNS):
                raise ValueError(f"Credential-like content: {path.relative_to(ROOT)}")
        files.append(path)
    manifest = {"created_at_utc": datetime.now(timezone.utc).isoformat(), "package": "regime-conditioned-momentum", "version": "3.0.0", "files": {p.relative_to(ROOT).as_posix(): {"bytes": p.stat().st_size} for p in files}, "checks": {"explicit_allowlist": True, "credential_pattern_scan": "passed", "no_runtime_or_account_configuration": True}}
    dist = ROOT / "dist"
    dist.mkdir(exist_ok=True)
    manifest_path = dist / "release-manifest.json"
    manifest_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
    target = dist / "regime-conditioned-momentum.zip"
    with zipfile.ZipFile(target, "w", zipfile.ZIP_DEFLATED, compresslevel=6) as bundle:
        for path in files:
            bundle.write(path, "regime-conditioned-momentum/" + path.relative_to(ROOT).as_posix())
        bundle.write(manifest_path, "regime-conditioned-momentum/release-manifest.json")
    print(json.dumps({"archive": str(target), "bytes": target.stat().st_size, "files": len(files)}, ensure_ascii=False))


if __name__ == "__main__":
    main()

