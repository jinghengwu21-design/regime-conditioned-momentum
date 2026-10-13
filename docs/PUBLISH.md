# Build and deployment

## Static research terminal

```bash
npm --prefix web ci
npm --prefix web test
npm --prefix web run build
```

The static bundle is `web/dist/`. Relative asset URLs support a GitHub project Pages path. The Pages workflow builds the client from its lockfile and uploads that directory. Configure Pages with GitHub Actions as its source.

The public site includes frozen research data and timestamped Agent traces. Its interactive cost scenarios execute in the browser. New LangGraph runs use the local Python service.

## Local service

```bash
python -m research_agent.server --port 8507
```

The server binds to 127.0.0.1 by default. It serves the static bundle and the research API from the same origin. Configure model credentials in the shell environment before starting it.

## Container

```bash
docker build -t sarkaz-research .
docker run --rm -p 127.0.0.1:8507:8507 sarkaz-research
```

The Docker image builds the frontend in a Node stage and serves it from Python. Container execution is separate from the local Windows verification record.

## Portable release

```bash
python scripts/package_release.py
python scripts/verify_release.py
```

The packager uses explicit source roots, ignores dependency trees and runtime outputs, scans text for credential patterns and writes a file-hash manifest. The verification script extracts into a new directory, checks every listed hash and runs a fresh deterministic research case.
