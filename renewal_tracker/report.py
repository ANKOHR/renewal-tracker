"""Deterministic report rendering and explicit provenance."""
import json


def safe_text(value):
    # Preserve Unicode while ensuring user text cannot inject an em dash.
    return str(value).replace(chr(0x2014), "-" )


def json_text(value):
    return json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True).replace(chr(0x2014), "\\u2014") + "\n"


def banner(result):
    p = result["provenance"]
    return (f"Data provenance: {len(p['real_record_ids'])} real records (user-entered; ownership and accuracy not independently verified); "
            f"{len(p['synthetic_record_ids'])} synthetic fixture records. All figures computed from these inputs.")


def cell(value):
    return safe_text(value).replace(chr(92), chr(92) * 2).replace("|", chr(92) + "|").replace("<", "&lt;").replace(">", "&gt;").replace("`", chr(92) + "`")


def render(result, format_name="md"):
    if format_name == "json":
        return json_text({**result, "provenance_banner": banner(result)})
    lines = ["# Renewal Tracker", "", banner(result), "", f"As of: {result['as_of']}. Upcoming window: through {result['window_end']} inclusive.", "", result["honesty"], "", "## Counts", ""]
    lines += [f"- {key}: {value}" for key, value in result["counts"].items()]
    lines += ["", "## Declared active costs per billing cadence", "", "Currencies and cadences are separate. These prices are not confirmed payments or savings.", "", "| Currency | Cadence | Amount |", "| --- | --- | ---: |"]
    lines += [f"| {c['currency']} | {c['cadence']} | {c['amount']} |" for c in result["costs_per_cadence"]]
    if not result["costs_per_cadence"]:
        lines += ["No active costs: 0 records."]
    for key in ("overdue", "upcoming"):
        lines += ["", f"## {key.title()}", "", "| ID | Name | Category | Renewal date | Declared price |", "| --- | --- | --- | --- | ---: |"]
        lines += [f"| {cell(r['id'])} | {cell(r['name'])} | {r['category']} | {r['renewal_date']} | {r['currency']} {r['amount']} / {r['cadence']} |" for r in result[key]]
        if not result[key]:
            lines += ["No records: 0."]
    lines += ["", "## Input trace", ""]
    for source in result["provenance"]["sources"]:
        lines.append(f"- {cell(source['file'])}: SHA-256 {source['sha256']}; synthetic file label: {str(source['synthetic']).lower()}")
    if not result["provenance"]["sources"]:
        lines.append("- Empty input: no source files.")
    lines += ["", "The JSON report includes every input record and real/synthetic record IDs for reconciliation."]
    return safe_text("\n".join(lines)) + "\n"
