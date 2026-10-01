import json
from renewal_tracker.report import render
from renewal_tracker.fixtures import expectations, AS_OF
from renewal_tracker.core import analyse


def test_report_matches_ground_truth_exact(result):
    report = json.loads(render(result, "json"))
    for key in ("counts", "category_counts", "costs_per_cadence"):
        assert report[key] == expectations()[key]


def test_report_zero_false_positives(result):
    for key in ("overdue", "upcoming"):
        actual = {r["id"] for r in json.loads(render(result, "json"))[key]}
        planted = set(expectations()[key + "_ids"])
        assert actual - planted == set()
        assert planted - actual == set()


def test_report_carries_provenance_banner(result):
    for fmt in ("md", "json"):
        output = render(result, fmt)
        assert "Data provenance:" in output
        assert "200 synthetic fixture records" in output
        assert "0 real records" in output


def test_real_and_mixed_provenance(record):
    records = [record, {**record, "id": "real-1", "synthetic": False}]
    output = render(analyse(records, AS_OF))
    assert "1 real records" in output and "1 synthetic fixture records" in output
    assert "not independently verified" in output


def test_hypothetical_figures_labelled(result):
    for fmt in ("md", "json"):
        assert "Time saved and money saved are unmeasured and are not reported" in render(result, fmt)
    assert not any("saved" in key for key in result if key != "honesty")


def test_handles_unicode_and_long_inputs(record):
    record["name"] = "C:\\Users\\Henry\\" + "日本語 café 🔑" * 700
    record["id"] = "日本語"
    result = analyse([record], AS_OF)
    assert json.loads(render(result, "json"))["records"][0]["name"] == record["name"]
    assert "日本語" in render(result)


def test_no_em_dashes_in_outputs(record):
    record["name"] = "a" + chr(0x2014) + "b"
    record["id"] = "z" + chr(0x2014) + "x"
    result = analyse([record], AS_OF)
    for fmt in ("md", "json"):
        assert chr(0x2014) not in render(result, fmt)
    assert json.loads(render(result, "json"))["records"][0]["name"] == record["name"]


def test_markdown_escapes_user_markup(record):
    record["name"] = "<script>|hello`"
    output = render(analyse([record], AS_OF))
    assert "<script>" not in output
    assert "&lt;script&gt;" in output
