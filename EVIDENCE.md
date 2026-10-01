# Local acceptance evidence

Data provenance: SYNTHETIC controlled fixture, 200 invented records. No real-use evidence, baseline savings or adoption measurements.

Measured on 2026-10-01, Python 3.12.10, Windows AMD64. Installed rt console entry point used. These timings are measured on this machine, not predictions for other systems.

- Full end-to-end fixture generation, run and Markdown report: 0.711538 seconds (requirement: under 5 seconds).
- Standalone JSON report: 0.220936 seconds (requirement: under 5 seconds).
- Demo fixtures: 0.257875 seconds.
- Demo run: 0.227575 seconds.
- Demo report: 0.226079 seconds.

Exact reconciliations passed: 200 total, 160 active, 40 cancelled, 40 overdue, 80 upcoming; 50 per category. GBP costs: 400.00 monthly, 800.00 annual, 1200.00 quarterly, 1600.00 weekly. All 40 overdue IDs and 80 upcoming IDs match the independent planted lists exactly: zero false positives and zero misses. Amounts and counts reconcile with no tolerances.

Final test run: 70 passed. Adversarial evidence covers boundary dates, malformed JSON, schema drift, duplicate IDs and JSON fields, negative/extreme amounts, Unicode, unpaired surrogates, long strings, cancelled items, write failures, snapshot corruption and byte-identical repeated output. Changing a source date and price changes computed results; changing expectations has no effect on the workflow.

The hand-written five-record example is tested: 5 total, 4 active, 1 cancelled, 1 overdue, 2 upcoming. No real trial records shipped.

Reproduce: python -m pytest -q, then python scripts/verify_acceptance.py. The script updates timing evidence and the synthetic Markdown report. Timings may differ; domain reports remain deterministic. See fixtures/synthetic/expectations.json for the hand-computed oracle, and evidence/synthetic-report.md for the complete rendered output and source hash.

Implementation acceptance: PASS on the controlled fixture. Product verdict: PENDING the two-week real-use window, as recorded in VERDICT.md.
