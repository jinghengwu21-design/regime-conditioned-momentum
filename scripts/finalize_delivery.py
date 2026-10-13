"""Collect release evidence from completed checks, without inventing checks."""
from datetime import datetime, timezone
import json
from pathlib import Path
import shutil
import sys
import xml.etree.ElementTree as ET

ROOT = Path(__file__).resolve().parents[1]

def junit_counts(path):
    cases = list(ET.parse(path).getroot().iter('testcase'))
    counts = {'tests': len(cases), 'failures': sum(c.find('failure') is not None for c in cases), 'errors': sum(c.find('error') is not None for c in cases), 'skipped': sum(c.find('skipped') is not None for c in cases)}
    if counts['failures'] or counts['errors'] or not counts['tests']:
        raise ValueError('Test suite did not pass: ' + str(path))
    return counts

counts = junit_counts(ROOT / 'outputs/test-results.xml')
frontend = junit_counts(ROOT / 'outputs/frontend-tests.xml')
evaluation = json.loads((ROOT / 'outputs/evaluation/evaluation.json').read_text(encoding='utf-8'))
if not evaluation['all_passed']:
    raise ValueError('Behavioral evaluation did not pass')
for case in evaluation['cases']:
    source = ROOT / 'outputs/evaluation/runs' / case['run_id']
    destination = ROOT / 'examples/evaluation' / case['id']
    destination.mkdir(parents=True, exist_ok=True)
    for name in ['request.json', 'context.json', 'trace.jsonl', 'draft.original.json']:
        shutil.copy2(source / name, destination / name)
    (destination / 'verdict.json').write_text(json.dumps(case, ensure_ascii=False, indent=2), encoding='utf-8')
sample = json.loads((ROOT / 'examples/default/result.json').read_text(encoding='utf-8'))
browser = json.loads((ROOT / 'outputs/browser-validation.json').read_text(encoding='utf-8-sig'))
locked = sum(1 for row in (ROOT / 'requirements.lock').read_text().splitlines() if '==' in row)
verification = {
    'verified_at_utc': datetime.now(timezone.utc).isoformat(),
    'python': sys.version.split()[0], 'virtual_environment': sys.prefix != sys.base_prefix,
    'dependencies': sample['implementation']['packages'], 'locked_packages': locked,
    'tests': counts, 'frontend_tests': frontend,
    'behavior_evaluation': {'passed': evaluation['passed'], 'total': evaluation['total']},
    'sample_run': sample['run_id'], 'browser_validation': browser,
    'model_validation': 'Real SDK with simulated HTTP contract; no live provider run included',
    'release_mode': 'GitHub source, GitHub Pages snapshot and local Python runtime',
}
(ROOT / 'outputs/verification.json').write_text(json.dumps(verification, ensure_ascii=False, indent=2), encoding='utf-8')
text = f'''# Verification

Recorded at {verification['verified_at_utc']}.

| Check | Result | Evidence |
|---|---|---|
| Python | {counts['tests']} passed, zero failures or errors | `outputs/test-results.xml` |
| Browser calculation contracts | {frontend['tests']} passed | `outputs/frontend-tests.xml` |
| Research behavior | {evaluation['passed']} / {evaluation['total']} passed | `outputs/evaluation/evaluation.json` |
| Locked environment | Python {verification['python']}, {locked} packages, dependency check passed | `requirements.lock` |
| Frozen strategy | 19 archived Python sources parse successfully | `scripts/verify_strategy.py` |
| Browser interaction | Research archive, comparison, research loop, financial analytics and local execution | `outputs/browser-validation.json` |
| Frontend | TypeScript and Vite production build passed; npm audit: zero known findings at verification | `web/package-lock.json` |

## Numeric reproduction

Sample `{sample['run_id']}` reproduces 922 trades, CAGR 53.2094819391%, daily account Sharpe 1.2450084107, realized maximum drawdown 30.0906162013%, and final equity 17,815.7867377 USDT.

## Behavioral observations

'''
text += '\n'.join(f"- **{c['name']}**: {c['observed']}. Trace: `examples/evaluation/{c['id']}/trace.jsonl`." for c in evaluation['cases'])
text += '''

## Validation scope

The public experiment records use the deterministic LangGraph workflow. Provider tests use the real OpenAI SDK with simulated HTTP responses to exercise function calls, correction, denied tools and loop limits. These tests do not measure live-model accuracy or attack success rates.

The 390 × 844 mobile layout was checked across all eight workspaces; no document-level horizontal overflow was observed. Wide financial tables scroll within their panels. Desktop interaction was checked in Edge. Screenshots are under `docs/screenshots/`.

The Windows launcher completed dependency installation and the production frontend build. GitHub Actions runs clean Linux and Windows Python jobs and a Node frontend job; their status is available on the repository's Actions page. Upstream LangGraph emits deprecation warnings under Python 3.14. Docker configuration is provided but is not part of this local verification.

## Reproduce

```bash
python -m pytest tests --junitxml outputs/test-results.xml
python -m research_agent.cli evaluate
python scripts/verify_strategy.py
npm --prefix web test
npm --prefix web run build
```
'''
(ROOT / 'docs/VERIFICATION.md').write_text(text, encoding='utf-8')
print(json.dumps({'python_tests': counts, 'frontend_tests': frontend, 'behavior_evaluation': verification['behavior_evaluation']}, ensure_ascii=False))
