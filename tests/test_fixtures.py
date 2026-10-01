import json
from renewal_tracker.fixtures import AS_OF, generate, expectations, fixture_records
from renewal_tracker.core import analyse
from renewal_tracker.cli import load_input


def test_fixtures_labelled_synthetic(tmp_path):
    generate(tmp_path)
    for path in tmp_path.glob("*.json"):
        data = json.loads(path.read_text(encoding="utf-8"))
        assert data["synthetic"] is True
        assert "SYNTHETIC" in data["_comment"]
    assert all(r["synthetic"] for r in fixture_records())
    assert len(fixture_records()) == 200


def test_fixture_ground_truth_matches_hand_computed():
    expected = expectations()
    result = analyse(fixture_records(), AS_OF)
    for key in ("counts", "category_counts", "costs_per_cadence"):
        assert result[key] == expected[key]
    for key in ("overdue", "upcoming"):
        assert sorted(r["id"] for r in result[key]) == expected[key + "_ids"]


def test_expectations_are_not_inputs(tmp_path):
    generate(tmp_path)
    (tmp_path / "expectations.json").write_text("broken oracle", encoding="utf-8")
    rows, as_of, _ = load_input(tmp_path)
    assert analyse(rows, as_of)["counts"]["total"] == 200


def test_fixture_generation_identical(tmp_path):
    generate(tmp_path)
    before = {p.name: p.read_bytes() for p in tmp_path.glob("*.json")}
    generate(tmp_path)
    assert before == {p.name: p.read_bytes() for p in tmp_path.glob("*.json")}
