"""Capture the tested dependency closure without unrelated workspace packages."""
from importlib.metadata import distribution
from pathlib import Path
from packaging.markers import default_environment
from packaging.requirements import Requirement

pending = ["langgraph", "openai", "pandas", "numpy", "plotly", "pydantic", "httpx", "pytest", "pyarrow"]
versions = {}
constraints = []
environment = default_environment()
environment["extra"] = ""
while pending:
    dist = distribution(pending.pop())
    key = dist.metadata["Name"]
    if key in versions:
        continue
    versions[key] = dist.version
    for raw in dist.requires or []:
        req = Requirement(raw)
        if req.marker is None or req.marker.evaluate(environment):
            pending.append(req.name)
            constraints.append((key, req))
conflicts = []
for parent, req in constraints:
    version = distribution(req.name).version
    if not req.specifier.contains(version, prereleases=True):
        conflicts.append(f"{parent} requires {req}, installed {version}")
text = "# Exact dependency closure from the tested Windows CPython 3.14 environment.\n"
text += "# Optional platform-only dependencies are marked; no application secrets.\n"
text += "".join(f"{name}=={version}" + ("; sys_platform == 'win32'" if name.lower() in {"colorama", "pywin32"} else "") + "\n" for name, version in sorted(versions.items(), key=lambda x: x[0].lower()))
(Path(__file__).resolve().parents[1] / "requirements.lock").write_text(text, encoding="utf-8")
print({"dependencies": len(versions), "conflicts": conflicts})

