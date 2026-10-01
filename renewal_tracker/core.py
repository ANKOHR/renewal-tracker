"""Pure renewal classification. No payment, savings or usage estimates."""
from datetime import date, timedelta
from decimal import Decimal, InvalidOperation
import re

CATEGORIES = ("subscription", "domain", "membership", "service")
CADENCES = ("monthly", "quarterly", "annual", "weekly", "daily")
FIELDS = {"id", "name", "category", "amount", "currency", "cadence", "renewal_date", "status", "synthetic"}

class TrackerError(ValueError):
    """A named, actionable input or output error."""


def parse_date(value, field="as_of"):
    if not isinstance(value, str) or not re.fullmatch(r"[0-9]{4}-[0-9]{2}-[0-9]{2}", value):
        raise TrackerError(f"SchemaError: {field} must be an ISO date YYYY-MM-DD")
    try:
        result = date.fromisoformat(value)
        if not 1900 <= result.year <= 9998:
            raise ValueError()
        return result
    except ValueError:
        raise TrackerError(f"SchemaError: {field} must be a valid date in 1900..9998") from None


def validate_record(record):
    if not isinstance(record, dict):
        raise TrackerError("SchemaError: record must be an object")
    missing, extra = FIELDS - record.keys(), record.keys() - FIELDS
    if missing or extra:
        raise TrackerError(f"SchemaError: missing fields {sorted(missing)}; unknown fields {sorted(extra)}")
    for field, limit in (("id", 128), ("name", 10000)):
        value = record[field]
        if not isinstance(value, str) or not value.strip() or len(value) > limit or any(ord(c) < 32 or 127 <= ord(c) <= 159 or 0xD800 <= ord(c) <= 0xDFFF for c in value):
            raise TrackerError(f"SchemaError: {field} must contain 1..{limit} characters with no control characters or unpaired Unicode surrogates")
    for field, values in (("category", CATEGORIES), ("cadence", CADENCES), ("status", ("active", "cancelled"))):
        if record[field] not in values:
            raise TrackerError(f"SchemaError: {field} must be one of {', '.join(values)}")
    if not isinstance(record["synthetic"], bool):
        raise TrackerError("SchemaError: synthetic must be a boolean")
    if not isinstance(record["currency"], str) or not re.fullmatch(r"[A-Z]{3}", record["currency"]):
        raise TrackerError("SchemaError: currency must be a three-letter uppercase code")
    amount = record["amount"]
    if not isinstance(amount, str) or not re.fullmatch(r"[0-9]{1,10}\.[0-9]{2}", amount):
        raise TrackerError("SchemaError: amount must be a nonnegative decimal string with two places, at most 9999999999.99")
    try:
        Decimal(amount)
    except InvalidOperation:
        raise TrackerError("SchemaError: amount is invalid") from None
    parse_date(record["renewal_date"], "renewal_date")
    return dict(record)


def analyse(records, as_of, window_days=30, sources=None):
    """Classify declared dates only. Overdue does not mean an unpaid debt.

    A future renewal is valid; cancelled items are excluded from due and cost
    lists. Costs are input prices per stated cadence, never estimated savings.
    """
    today = parse_date(as_of)
    if type(window_days) is not int or not 0 <= window_days <= 365:
        raise TrackerError("SchemaError: window_days must be an integer in 0..365")
    try:
        end = today + timedelta(days=window_days)
    except OverflowError:
        raise TrackerError("SchemaError: as_of and window_days exceed the date range") from None
    clean, seen = [], set()
    for value in records:
        record = validate_record(value)
        if record["id"] in seen:
            raise TrackerError(f"SchemaError: duplicate id {record['id']!r}")
        seen.add(record["id"])
        clean.append(record)
    clean.sort(key=lambda r: r["id"])
    active = [r for r in clean if r["status"] == "active"]
    overdue = sorted((r for r in active if parse_date(r["renewal_date"]) < today), key=lambda r: (r["renewal_date"], r["id"]))
    upcoming = sorted((r for r in active if today <= parse_date(r["renewal_date"]) <= end), key=lambda r: (r["renewal_date"], r["id"]))
    grouped = {}
    for r in active:
        key = (r["currency"], r["cadence"])
        grouped[key] = grouped.get(key, Decimal("0.00")) + Decimal(r["amount"])
    costs = [{"currency": c, "cadence": f, "amount": format(a, ".2f")} for (c, f), a in sorted(grouped.items())]
    real_ids = [r["id"] for r in clean if not r["synthetic"]]
    synthetic_ids = [r["id"] for r in clean if r["synthetic"]]
    return {
        "schema_version": 1, "as_of": as_of, "window_days": window_days, "window_end": end.isoformat(),
        "counts": {"total": len(clean), "active": len(active), "cancelled": len(clean) - len(active), "overdue": len(overdue), "upcoming": len(upcoming)},
        "category_counts": {c: sum(r["category"] == c for r in clean) for c in CATEGORIES},
        "costs_per_cadence": costs, "overdue": overdue, "upcoming": upcoming, "records": clean,
        "provenance": {"sources": sorted(sources or [], key=lambda s: s["file"]), "real_record_ids": real_ids, "synthetic_record_ids": synthetic_ids},
        "honesty": "Computed from declared inputs. Overdue means the declared date has passed, not a confirmed unpaid bill. Costs are stated prices per cadence. Time saved and money saved are unmeasured and are not reported. No renewal discovery or prediction.",
    }
