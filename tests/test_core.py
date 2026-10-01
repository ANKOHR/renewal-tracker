import pytest
from renewal_tracker.core import TrackerError, analyse
from renewal_tracker.fixtures import AS_OF, fixture_records


def test_empty_input_renders_without_traceback():
    result = analyse([], AS_OF)
    assert result["counts"] == {"total": 0, "active": 0, "cancelled": 0, "overdue": 0, "upcoming": 0}
    assert result["costs_per_cadence"] == []


@pytest.mark.parametrize("field,value", [("amount", "-1.00"), ("amount", "NaN"), ("amount", "Infinity"), ("amount", 1.25), ("amount", "10000000000.00"), ("amount", "1.001"), ("amount", "1e3"), ("renewal_date", "2026-02-30"), ("renewal_date", "10000-01-01"), ("renewal_date", "2026-9-1"), ("category", "unknown"), ("status", "paid"), ("cadence", "sometimes"), ("currency", "gbp"), ("synthetic", "true"), ("id", ""), ("name", "x" * 10001), ("name", "a\nb")])
def test_rejects_adversarial_values(record, field, value):
    record[field] = value
    with pytest.raises(TrackerError, match=field):
        analyse([record], AS_OF)


def test_duplicates_rejected(record):
    with pytest.raises(TrackerError, match="duplicate id"):
        analyse([record, record], AS_OF)


def test_schema_drift(record):
    record["surprise"] = True
    with pytest.raises(TrackerError, match="surprise"):
        analyse([record], AS_OF)


def test_missing_field(record):
    del record["currency"]
    with pytest.raises(TrackerError, match="currency"):
        analyse([record], AS_OF)


def test_future_date_is_valid_and_not_due(record):
    record["renewal_date"] = "2099-01-01"
    assert analyse([record], AS_OF)["counts"]["upcoming"] == 0


def test_cancelled_excluded_even_when_overdue(record):
    record["status"] = "cancelled"
    r = analyse([record], AS_OF)
    assert r["counts"]["overdue"] == 0
    assert r["costs_per_cadence"] == []


def test_money_exact_and_currencies_separate(record):
    rows = []
    for n, (amount, currency, cadence) in enumerate((("0.10", "GBP", "monthly"), ("0.20", "GBP", "monthly"), ("0.10", "USD", "annual"))):
        rows.append({**record, "id": str(n), "amount": amount, "currency": currency, "cadence": cadence})
    assert analyse(rows, AS_OF)["costs_per_cadence"] == [{"currency": "GBP", "cadence": "monthly", "amount": "0.30"}, {"currency": "USD", "cadence": "annual", "amount": "0.10"}]


def test_boundary_dates(record):
    rows = [{**record, "id": str(n), "renewal_date": d} for n, d in enumerate(("2026-09-29", "2026-09-30", "2026-10-30", "2026-10-31"))]
    r = analyse(rows, AS_OF)
    assert [x["id"] for x in r["overdue"]] == ["0"]
    assert [x["id"] for x in r["upcoming"]] == ["1", "2"]


def test_ground_truth_corruption_changes_computed_figures():
    records = fixture_records()
    before = analyse(records, AS_OF)
    records[0]["renewal_date"] = "2026-10-01"
    records[0]["amount"] = "15.00"
    after = analyse(records, AS_OF)
    assert after["counts"]["overdue"] == before["counts"]["overdue"] - 1
    assert after["counts"]["upcoming"] == before["counts"]["upcoming"] + 1
    assert next(c["amount"] for c in after["costs_per_cadence"] if c["cadence"] == "monthly") == "405.00"


def test_core_no_mutation(record):
    copy = dict(record)
    analyse([record], AS_OF)
    assert record == copy


@pytest.mark.parametrize("window", [-1, 366, True])
def test_invalid_window(window):
    with pytest.raises(TrackerError, match="window_days"):
        analyse([], AS_OF, window)
