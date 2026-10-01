# Renewal Tracker

A CPU-only Python CLI for subscriptions, domains, memberships and recurring services. It classifies declared renewal dates and reconciles exact decimal prices from local JSON files. It does not discover services, contact providers, predict renewals, advance dates, or claim savings.

## Hypothesis and acceptance

A deterministic, tested tool with explicit dates, prices and provenance can make Henry's renewal list trustworthy. Acceptance: the labelled 200-record fixture must produce exactly the planted counts, due IDs and per-cadence costs, with zero false positives, and the full demo must finish in under 5 seconds. This validates implementation accuracy on synthetic data, not completeness of Henry's real list or actual time saved. See EVIDENCE.md for the measured local results.

## Quickstart

Python 3.10 or newer. Runtime dependencies: none. From the repository root:

```powershell
python -m pip install --no-index --no-deps --no-build-isolation -e .
rt fixtures --out demo
rt run --input demo
rt report --format md
rt report --format json --out demo-report.json
python -m pytest -q
```

Installation uses the locally installed setuptools build backend. No network is required; if pip is configured to check versions, disable that check. `python -m renewal_tracker.cli` is the equivalent entry point without installation. Tests require locally installed pytest.

On Windows, if a user installation warns that its Scripts folder is outside PATH, enable it for the current PowerShell session:

```powershell
$rtScripts = python -c "import sysconfig; print(sysconfig.get_path('scripts', 'nt_user'))"
$env:Path = "$rtScripts;$env:Path"
```

The smallest hand-written five-record version:

```powershell
rt run --input examples/tiny
rt report --format md
```

The default local snapshot is `.rt/result.json` in the working directory. `run` replaces it atomically only after successful validation. Reports describe that snapshot, which can become stale: rerun after changing inputs. `report` validates and recomputes the snapshot before rendering. The input directory and working directory may differ. No personal trial records are shipped. Do not commit real input, snapshots or private reports to a public repository.

## Input format reference

The supported format is UTF-8 JSON. Read files named `records.json` or `*.records.json` directly inside the supplied directory. Other JSON filenames are rejected except `expectations.json`, the independent test oracle which is never read by the workflow. CSV, YAML and JSONL input files receive a named unsupported-format error. Subdirectories are not searched. An empty directory is a valid zero-record input.

Every input file is an object:

```json
{
  "_comment": "SYNTHETIC EXAMPLE: invented, not Henry's data",
  "synthetic": true,
  "as_of": "2026-09-30",
  "records": [
    {
      "id": "example-1",
      "name": "Example domain",
      "category": "domain",
      "amount": "12.00",
      "currency": "GBP",
      "cadence": "annual",
      "renewal_date": "2026-10-01",
      "status": "active",
      "synthetic": true
    }
  ]
}
```

For Henry's real data, enter verified provider information by hand and set file and record `synthetic` to `false`. This label is a user assertion; the tool cannot verify ownership or accuracy. A mixed input file uses `synthetic: false`, and labels each invented record `true`. A file labelled synthetic cannot contain a real-labelled record. Reports list real and synthetic record IDs separately and include file names and SHA-256 digests of source bytes.

| Field | Rule |
| --- | --- |
| `_comment` | Optional file-level label; mandatory in shipped synthetic files by policy |
| `as_of` | Required explicit ISO date YYYY-MM-DD; overridden by `--as-of` |
| `synthetic` | Required boolean at file and record level |
| `records` | Required list, may be empty |
| `id` | Unique across all input files, 1..128 characters, no control characters or unpaired Unicode surrogates |
| `name` | 1..10000 characters, no control characters; Unicode and Windows paths supported |
| `category` | subscription, domain, membership, service |
| `amount` | Nonnegative decimal string with exactly two decimal places, maximum 9999999999.99 |
| `currency` | Three uppercase letters; a grouping label, no exchange rate or currency validation service |
| `cadence` | daily, weekly, monthly, quarterly, annual |
| `renewal_date` | Declared next renewal, ISO date in years 1900..9998 |
| `status` | active or cancelled |

Unknown and missing fields are schema errors. Dates must be actual calendar dates. Duplicate JSON fields are rejected instead of overwritten. Negative, nonfinite, scientific-notation and overprecision amounts are rejected. Duplicate IDs are rejected, including across files. Zero prices are valid. Future dates are valid and listed only when in the selected window. Very long strings beyond the stated limit are rejected, not truncated. All records are validated before filtering.

Overdue means an active record's declared date is before `as_of`. Upcoming means that date is between `as_of` and `as_of + window_days`, inclusive. Default window: 30 days; permitted: 0..365. Cancelled records remain in total and category counts but are excluded from costs and due lists. A past date does not prove a bill is unpaid. Cadence is an input price label, not a rule to infer unseen renewals. Update dates manually after confirming renewal.

Prices are summed exactly using decimal arithmetic within each currency and cadence. There is no grand money total across different currencies or cadences, annualisation, currency conversion, or projected spend. Category counts include cancelled records. All figure inputs are included in JSON reports. Markdown due tables include record IDs, dates and declared prices; JSON also includes all active and cancelled records for reconciliation.

When combining input files, their `as_of` values must agree unless overridden explicitly. Empty input uses the documented fixed reference date 2026-09-30, never the wall clock. No randomness is used (seed: none). The same input bytes, date and window produce byte-identical snapshots and reports on repeated runs. Record ordering is stable by ID; due lists by date then ID. Source file hashes deliberately change when input bytes change, even if their meaning is the same.

## Subcommand catalogue

Every subcommand has `--help` and examples.

```powershell
rt fixtures --out demo
rt run --input demo --as-of 2026-09-30 --window-days 30 --state .rt/result.json
rt report --format md --state .rt/result.json --out report.md
rt report --format json
rt due --input demo --category domain --window-days 60
rt costs --input demo --category subscription
```

`fixtures` writes 200 synthetic records plus hand-computed expectations. `run` validates and saves a computed snapshot. `report` renders Markdown or JSON, printing when `--out` is absent. `due` directly computes overdue and upcoming lists with provenance. `costs` directly computes active declared prices per currency and cadence with provenance. `due` and `costs` do not change the saved snapshot. Use `--category` to restrict those two commands to a domain category. Output includes provenance for the filtered records and the source files they came from.

## Architecture

```text
local records.json / *.records.json
             |
             v
cli.py: parse, validate file labels, source hashes
             |
             v
core.py: pure validation, classification, exact grouping
             |
             +--> due / costs JSON with provenance
             |
             v
atomic .rt/result.json
             |
             v
report.py: Markdown / JSON, provenance banner, input trace

fixtures.py --> labelled fixtures + independent expectations
pytest      --> boundaries, adversarial input, oracle, determinism
```

No database, network calls, language-model calls or GPU workloads. Core functions perform no I/O. The CLI owns file access and atomic replacement. Fixtures are generated deterministically with no random seed needed.

## Honesty boundary

Every figure comes from explicit records. Synthetic data is labelled in files and report banners. Real-labelled input is user-entered and not independently verified. Nothing here demonstrates real usage, time saved or money saved. Those metrics are unmeasured and not reported. Any future illustrative or hypothetical figure must be labelled as such in code, CLI, documentation and reports. Measured savings would require a recorded baseline and trial; no such baseline exists in this build. The synthetic accuracy and runtime results validate only this controlled acceptance trial.

Markdown replaces user-supplied U+2014 with a plain hyphen to obey the no-em-dash output rule. JSON escapes that character as a Unicode escape, preserving the exact parsed value without emitting a literal em dash. Other Unicode is preserved. Markdown escapes table delimiters and HTML angle brackets. Input strings are never executed.

## Fixture labelling and planted ground truth

JSON has no header comments, so every shipped or generated fixture has a first `_comment` header field containing SYNTHETIC and a `synthetic: true` field. Every record is labelled too. Examples and expectations follow the same policy. No fixture represents a real provider account.

Four groups of 50 records correspond to the four categories. Each group has 40 active and 10 cancelled. Active records 001..010 renew yesterday, 011..020 today, 021..030 on day 30, 031..040 on day 31. Cancelled 041..050 have yesterday's date. Thus 200 total, 160 active, 40 cancelled, 40 overdue and 80 upcoming. Each category contains 50 records. Prices are GBP 10.00 monthly for subscriptions, 20.00 annual for domains, 30.00 quarterly for memberships, 40.00 weekly for services. Active totals: GBP 400.00 monthly, 800.00 annual, 1200.00 quarterly, 1600.00 weekly. Expectations are written independently of the engine. Changing the oracle does not change the report; changing a record does.

## Failure modes and limitations

- Malformed JSON: ParseError with file, exact line and column, exit 2.
- Missing input or snapshot: MissingInput with a usage hint, exit 2.
- Schema drift or invalid values: SchemaError with offending fields, file and record index where applicable. Schema errors use line 1 as a file-level location, not a claim of exact field location.
- Duplicate IDs: SchemaError naming the ID; no records silently discarded.
- Unsupported input formats: SchemaError naming the file and line 1, with JSON usage hint.
- Report write failure: WriteError naming the target; the temporary file is cleaned up and an existing report remains intact. Writes are atomic per file, not a transaction across both fixture files.
- Incomplete or stale user input: cannot be detected reliably; no provider sync or hidden inference. Past dates need hand review.
- Different minor currency units: this version uses exactly two decimal places for all currencies; do not enter values requiring other precision.
- Local snapshots have reconciliation checks, not signatures. An attacker able to edit the whole snapshot can forge its provenance. Input hashes are traceability, not authentication.

## Evidence-based improvement hook and verdict

After two weeks of actual use, measure classification accuracy against a hand-checked sample. Start the window on the first real run, not on the build date. Keep the private trial log locally, outside version control. Record date, explicit as_of/window, sampled IDs, expected classification, actual classification, number checked, errors and whether Henry used the tool. Error rate = errors / records checked; an empty sample is unmeasured, not zero error. Optionally measure elapsed task time against a recorded manual baseline, with identical scope. Do not label a subjective impression as savings.

If error rate exceeds 10 percent, fix the top measured failure cause and retest or kill with a recorded reason. If unused during the two-week window, kill and record why. Build status: acceptance evidence available on synthetic data. Final verdict: PENDING real-use evidence; the window has not occurred. Never invent a completed verdict. Record the eventual decision and evidence in VERDICT.md: expand if it earns daily use or revenue; integrate if substantial overlap is found; commercialise if an evidenced buyer would pay as-is; maintain as portfolio evidence otherwise; kill if unused or unable to meet acceptance. The current build contains no buyer, revenue or daily-use evidence.
