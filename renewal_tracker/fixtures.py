"""Labelled fixtures, no randomness (seed: none). Independent arithmetic oracle."""
from datetime import date, timedelta
from pathlib import Path
from .core import CATEGORIES
from .report import json_text

AS_OF = "2026-09-30"


def fixture_records():
    records = []
    for group, category in enumerate(CATEGORIES, 1):
        for n in range(1, 51):
            offset = -1 if n <= 10 or n > 40 else 0 if n <= 20 else 30 if n <= 30 else 31
            records.append({"id": f"{category}-{n:03d}", "name": f"Synthetic {category} {n:03d}", "category": category, "amount": f"{group * 10}.00", "currency": "GBP", "cadence": ("monthly", "annual", "quarterly", "weekly")[group - 1], "renewal_date": (date(2026, 9, 30) + timedelta(days=offset)).isoformat(), "status": "cancelled" if n > 40 else "active", "synthetic": True})
    return records


def expectations():
    # Hand-computed: four groups of 50; each has 40 active, 10 cancelled,
    # 10 overdue, 20 upcoming inclusive of today and day 30, 10 beyond window.
    # Costs: 40 * 10 = 400; 40 * 20 = 800; 40 * 30 = 1200; 40 * 40 = 1600.
    # Lists below encode planted IDs independently of classification logic.
    return {"_comment": "SYNTHETIC: hand-computed ground truth; not real trial evidence", "synthetic": True, "as_of": AS_OF, "window_days": 30,
            "counts": {"total": 200, "active": 160, "cancelled": 40, "overdue": 40, "upcoming": 80},
            "category_counts": {"subscription": 50, "domain": 50, "membership": 50, "service": 50},
            "costs_per_cadence": [{"currency": "GBP", "cadence": "annual", "amount": "800.00"}, {"currency": "GBP", "cadence": "monthly", "amount": "400.00"}, {"currency": "GBP", "cadence": "quarterly", "amount": "1200.00"}, {"currency": "GBP", "cadence": "weekly", "amount": "1600.00"}],
            "overdue_ids": sorted(f"{c}-{n:03d}" for c in ("subscription", "domain", "membership", "service") for n in range(1, 11)),
            "upcoming_ids": sorted(f"{c}-{n:03d}" for c in ("subscription", "domain", "membership", "service") for n in range(11, 31))}


def generate(out):
    from .cli import atomic_write
    out = Path(out)
    data = {"_comment": "SYNTHETIC FIXTURE: all records invented for testing", "synthetic": True, "as_of": AS_OF, "records": fixture_records()}
    atomic_write(out / "records.json", json_text(data))
    atomic_write(out / "expectations.json", json_text(expectations()))
    # A hand-written five-record example is also shipped in examples/tiny.
    return 200
