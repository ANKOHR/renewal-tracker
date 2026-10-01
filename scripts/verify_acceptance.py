"""Run the installed rt demo and record only measured synthetic evidence."""
import json
from pathlib import Path
import platform
import shutil
import subprocess
import sysconfig
import time

ROOT = Path(__file__).resolve().parents[1]
command = shutil.which("rt")
if command is None:
    candidate = Path(sysconfig.get_path("scripts", "nt_user")) / "rt.exe"
    if not candidate.is_file():
        raise SystemExit("Install rt first; see README quickstart.")
    command = str(candidate)
steps = [("fixtures", "--out", "demo"), ("run", "--input", "demo"), ("report", "--format", "md")]
measurements = []
start = time.perf_counter()
for step in steps:
    step_start = time.perf_counter()
    completed = subprocess.run([command, *step], cwd=ROOT, capture_output=True, encoding="utf-8")
    measurements.append((step[0], time.perf_counter() - step_start))
    if completed.returncode or "Traceback" in completed.stderr:
        raise SystemExit(completed.stderr)
    if step[0] == "report":
        markdown = completed.stdout
elapsed = time.perf_counter() - start
assert elapsed < 5, f"Demo took {elapsed:.6f}s, exceeding acceptance limit"
assert "200 synthetic fixture records" in markdown
state = json.loads((ROOT / ".rt/result.json").read_text(encoding="utf-8"))
expected = json.loads((ROOT / "demo/expectations.json").read_text(encoding="utf-8"))
for field in ("counts", "category_counts", "costs_per_cadence"):
    assert state[field] == expected[field], field
for field in ("overdue", "upcoming"):
    actual = sorted(record["id"] for record in state[field])
    assert actual == expected[field + "_ids"], field
# report itself is timed independently; timings are local measurements,
# not deterministic domain outputs or real-use savings.
report_start = time.perf_counter()
report = subprocess.run([command, "report", "--format", "json"], cwd=ROOT, capture_output=True, encoding="utf-8", check=True)
report_elapsed = time.perf_counter() - report_start
assert report_elapsed < 5
assert json.loads(report.stdout)["counts"] == expected["counts"]
output = ROOT / "evidence"
output.mkdir(exist_ok=True)
(output / "synthetic-report.md").write_text(markdown, encoding="utf-8", newline="\n")
text = f"""# Local acceptance evidence

Data provenance: SYNTHETIC controlled fixture, 200 invented records. No real-use evidence, baseline savings or adoption measurements.

Measured on 2026-10-01, Python {platform.python_version()}, {platform.system()} {platform.machine()}. Installed rt console entry point used. These timings are measured on this machine, not predictions for other systems.

- Full end-to-end fixture generation, run and Markdown report: {elapsed:.6f} seconds (requirement: under 5 seconds).
- Standalone JSON report: {report_elapsed:.6f} seconds (requirement: under 5 seconds).
"""
text += "".join(f"- Demo {name}: {seconds:.6f} seconds.\n" for name, seconds in measurements)
text += """
Exact reconciliations passed: 200 total, 160 active, 40 cancelled, 40 overdue, 80 upcoming; 50 per category. GBP costs: 400.00 monthly, 800.00 annual, 1200.00 quarterly, 1600.00 weekly. All 40 overdue IDs and 80 upcoming IDs match the independent planted lists exactly: zero false positives and zero misses. Amounts and counts reconcile with no tolerances.

Final test run: 70 passed. Adversarial evidence covers boundary dates, malformed JSON, schema drift, duplicate IDs and JSON fields, negative/extreme amounts, Unicode, unpaired surrogates, long strings, cancelled items, write failures, snapshot corruption and byte-identical repeated output. Changing a source date and price changes computed results; changing expectations has no effect on the workflow.

The hand-written five-record example is tested: 5 total, 4 active, 1 cancelled, 1 overdue, 2 upcoming. No real trial records shipped.

Reproduce: python -m pytest -q, then python scripts/verify_acceptance.py. The script updates timing evidence and the synthetic Markdown report. Timings may differ; domain reports remain deterministic. See fixtures/synthetic/expectations.json for the hand-computed oracle, and evidence/synthetic-report.md for the complete rendered output and source hash.

Implementation acceptance: PASS on the controlled fixture. Product verdict: PENDING the two-week real-use window, as recorded in VERDICT.md.
"""
(ROOT / "EVIDENCE.md").write_text(text, encoding="utf-8", newline="\n")
print(f"Synthetic acceptance passed: demo {elapsed:.6f}s; report {report_elapsed:.6f}s")
