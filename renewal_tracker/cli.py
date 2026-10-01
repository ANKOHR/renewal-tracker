"""Local file CLI. No network calls and no clock-dependent outputs."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import sys
import tempfile
from .core import TrackerError, analyse, parse_date, validate_record
from .fixtures import generate
from .report import json_text, render, safe_text


def atomic_write(path, text):
    path = Path(path)
    temporary = None
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        with tempfile.NamedTemporaryFile(mode="w", encoding="utf-8", newline="\n", dir=path.parent, prefix=".rt-tmp-", delete=False) as handle:
            temporary = Path(handle.name)
            handle.write(text)
        os.replace(temporary, path)
    except (OSError, ValueError) as exc:
        raise TrackerError(f"WriteError: {path}: {exc}. Choose a writable file path.") from None
    finally:
        if temporary is not None and temporary.exists():
            temporary.unlink()


def unique_object(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError(f"duplicate JSON field {key!r}")
        result[key] = value
    return result


def read_json(path):
    try:
        raw = path.read_bytes()
        value = json.loads(raw.decode("utf-8-sig"), object_pairs_hook=unique_object, parse_constant=lambda value: (_ for _ in ()).throw(ValueError(f"nonfinite number {value}")))
        return value, raw
    except json.JSONDecodeError as exc:
        raise TrackerError(f"ParseError: {path}: line {exc.lineno}, column {exc.colno}: {exc.msg}") from None
    except (UnicodeError, ValueError) as exc:
        raise TrackerError(f"ParseError: {path}: line 1: {exc}") from None
    except OSError as exc:
        raise TrackerError(f"ReadError: {path}: {exc}") from None


def load_input(directory, as_of=None):
    root = Path(directory)
    if not root.is_dir():
        raise TrackerError(f"MissingInput: {root}. Use rt fixtures --out demo or provide an input directory.")
    # Expectations are the independent test oracle, never workflow inputs.
    unsupported = sorted(p.name for p in root.iterdir() if p.is_file() and p.suffix.lower() in (".csv", ".yaml", ".yml", ".jsonl"))
    if unsupported:
        raise TrackerError(f"SchemaError: {root / unsupported[0]}: line 1: unsupported format; use records.json or *.records.json")
    paths = sorted(p for p in root.iterdir() if p.is_file() and (p.name == "records.json" or p.name.endswith(".records.json")))
    unexpected = sorted(p for p in root.iterdir() if p.is_file() and p.suffix.lower() == ".json" and p not in paths and p.name != "expectations.json")
    if unexpected:
        raise TrackerError(f"SchemaError: {unexpected[0]}: line 1: unrecognised input filename; use *.records.json")
    records, sources, dates = [], [], set()
    for path in paths:
        data, raw = read_json(path)
        try:
            if not isinstance(data, dict):
                raise TrackerError("SchemaError: input must be an object")
            required = {"synthetic", "as_of", "records"}
            if not required <= data.keys() or data.keys() - required - {"_comment"}:
                raise TrackerError("SchemaError: input fields must be synthetic, as_of, records, and optional _comment")
            if type(data["synthetic"]) is not bool or not isinstance(data["records"], list):
                raise TrackerError("SchemaError: synthetic must be boolean and records must be a list")
            parse_date(data["as_of"])
            dates.add(data["as_of"])
            for index, record in enumerate(data["records"], 1):
                try:
                    clean = validate_record(record)
                    if data["synthetic"] and not clean["synthetic"]:
                        raise TrackerError("SchemaError: synthetic file cannot contain a real record")
                    records.append(clean)
                except TrackerError as exc:
                    raise TrackerError(f"{exc}; record {index}") from None
            sources.append({"file": path.name, "sha256": hashlib.sha256(raw).hexdigest(), "synthetic": data["synthetic"]})
        except TrackerError as exc:
            raise TrackerError(f"{exc}; file {path}, line 1 (schema location; record index given where applicable)") from None
    if as_of is None and len(dates) > 1:
        raise TrackerError("SchemaError: as_of differs between files; supply --as-of YYYY-MM-DD")
    return records, as_of or (next(iter(dates)) if dates else "2026-09-30"), sources


class SafeParser(argparse.ArgumentParser):
    def error(self, message):
        super().error(safe_text(message))


def parser():
    p = SafeParser(prog="rt", description="Track declared renewals in local JSON files. No predictions or measured savings.")
    sub = p.add_subparsers(dest="command", required=True)
    f = sub.add_parser("fixtures", help="Generate 200 labelled synthetic records", epilog="Example: rt fixtures --out demo")
    f.add_argument("--out", required=True)
    r = sub.add_parser("run", help="Compute renewal classifications and store a report snapshot", epilog="Example: rt run --input demo --as-of 2026-09-30")
    r.add_argument("--input", required=True)
    r.add_argument("--as-of", help="Explicit date; otherwise use input as_of")
    r.add_argument("--window-days", type=int, default=30)
    r.add_argument("--state", default=".rt/result.json", help="Local result snapshot (default: .rt/result.json)")
    report = sub.add_parser("report", help="Render a stored snapshot with provenance", epilog="Example: rt report --format md --out report.md")
    report.add_argument("--format", choices=("md", "json"), default="md")
    report.add_argument("--state", default=".rt/result.json")
    report.add_argument("--out", help="Write atomically to this file; otherwise print")
    for name, help_text in (("due", "List declared overdue and upcoming renewals"), ("costs", "Show active input prices grouped by currency and cadence")):
        domain = sub.add_parser(name, help=help_text, epilog=f"Example: rt {name} --input demo --as-of 2026-09-30")
        domain.add_argument("--input", required=True)
        domain.add_argument("--as-of")
        domain.add_argument("--window-days", type=int, default=30)
        domain.add_argument("--category", choices=("subscription", "domain", "membership", "service"))
    return p


def main(argv=None):
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, "reconfigure"):
            stream.reconfigure(encoding="utf-8")
    args = parser().parse_args(argv)
    try:
        if args.command == "fixtures":
            count = generate(args.out)
            print(f"Generated {count} SYNTHETIC records at {safe_text(args.out)}. Expectations are hand-computed synthetic ground truth.")
        elif args.command in ("run", "due", "costs"):
            records, as_of, sources = load_input(args.input, args.as_of)
            # Validate the whole input before filtering to expose duplicates and invalid records.
            result = analyse(records, as_of, args.window_days, sources)
            if getattr(args, "category", None):
                result = analyse([r for r in records if r["category"] == args.category], as_of, args.window_days, sources)
            if args.command == "run":
                atomic_write(args.state, json_text(result))
                print(f"Computed {result['counts']['total']} records; real: {len(result['provenance']['real_record_ids'])}; synthetic: {len(result['provenance']['synthetic_record_ids'])}. Snapshot: {safe_text(args.state)}. Savings unmeasured, not reported.")
            else:
                from .report import banner
                keys = ("overdue", "upcoming") if args.command == "due" else ("costs_per_cadence",)
                print(json_text({"provenance_banner": banner(result), "provenance": result["provenance"], "as_of": result["as_of"], "window_end": result["window_end"], "honesty": result["honesty"], **{k: result[k] for k in keys}}), end="")
        elif args.command == "report":
            path = Path(args.state)
            if not path.is_file():
                raise TrackerError(f"MissingInput: {path}. Run rt run --input <dir> first.")
            result, _ = read_json(path)
            try:
                # Recompute to validate the persisted data, never trust edited summary figures.
                validated = analyse(result["records"], result["as_of"], result["window_days"], result["provenance"]["sources"])
                if validated != result:
                    raise TrackerError("SchemaError: snapshot does not reconcile; rerun rt run")
                output = render(validated, args.format)
            except (KeyError, TypeError, AttributeError) as exc:
                raise TrackerError(f"SchemaError: {path}: invalid snapshot field {exc}; rerun rt run") from None
            if args.out:
                atomic_write(args.out, output)
            else:
                print(output, end="")
        return 0
    except TrackerError as exc:
        print(safe_text(str(exc)), file=sys.stderr)
        return 2
    except OSError as exc:
        print(safe_text(f"IOError: {exc}. Check local file permissions and paths."), file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
