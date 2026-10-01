import json
import os
from pathlib import Path
import subprocess
import sys
import time
import pytest
from renewal_tracker.cli import main, atomic_write, load_input
from renewal_tracker.core import TrackerError
from renewal_tracker.fixtures import generate


def invoke(tmp_path, *args):
    env = {**os.environ, "PYTHONPATH": str(Path(__file__).resolve().parents[1]), "PYTHONIOENCODING": "utf-8"}
    return subprocess.run([sys.executable, "-m", "renewal_tracker.cli", *args], cwd=tmp_path, env=env, capture_output=True, text=True, encoding="utf-8")


def test_run_completes_on_fixture(tmp_path):
    start = time.perf_counter()
    for args in (("fixtures", "--out", "demo"), ("run", "--input", "demo"), ("report", "--format", "md")):
        r = invoke(tmp_path, *args)
        assert r.returncode == 0, r.stderr
        assert "Traceback" not in r.stderr
    assert time.perf_counter() - start < 5
    assert "200 synthetic fixture records" in r.stdout


def test_determinism_byte_identical(tmp_path):
    invoke(tmp_path, "fixtures", "--out", "demo")
    invoke(tmp_path, "run", "--input", "demo")
    state = (tmp_path / ".rt/result.json").read_bytes()
    report = invoke(tmp_path, "report", "--format", "json").stdout
    invoke(tmp_path, "run", "--input", "demo")
    assert state == (tmp_path / ".rt/result.json").read_bytes()
    assert report == invoke(tmp_path, "report", "--format", "json").stdout


@pytest.mark.parametrize("command", ["fixtures", "run", "report", "due", "costs"])
def test_cli_smoke_all_subcommands(tmp_path, command):
    help_result = invoke(tmp_path, command, "--help")
    assert help_result.returncode == 0 and "Example:" in help_result.stdout
    invoke(tmp_path, "fixtures", "--out", "demo")
    invoke(tmp_path, "run", "--input", "demo")
    args = ("--out", "second") if command == "fixtures" else ("--format", "json") if command == "report" else ("--input", "demo")
    assert invoke(tmp_path, command, *args).returncode == 0


def test_malformed_input_named_error(tmp_path):
    (tmp_path / "records.json").write_text('{\n "synthetic": true,\n "records": [}', encoding="utf-8")
    r = invoke(tmp_path, "run", "--input", str(tmp_path))
    assert r.returncode == 2
    assert "ParseError:" in r.stderr and "records.json: line 3" in r.stderr
    assert "Traceback" not in r.stderr


def test_missing_input_named_error(tmp_path):
    r = invoke(tmp_path, "run", "--input", "missing")
    assert r.returncode == 2 and "MissingInput:" in r.stderr and "rt fixtures" in r.stderr


def test_empty_directory_report(tmp_path):
    (tmp_path / "empty").mkdir()
    assert invoke(tmp_path, "run", "--input", "empty").returncode == 0
    r = invoke(tmp_path, "report")
    assert r.returncode == 0 and "total: 0" in r.stdout and "Data provenance:" in r.stdout


def test_report_write_failure_no_partial_files(tmp_path):
    invoke(tmp_path, "fixtures", "--out", "demo")
    invoke(tmp_path, "run", "--input", "demo")
    (tmp_path / "blocked").mkdir()
    r = invoke(tmp_path, "report", "--out", "blocked")
    assert r.returncode == 2 and "WriteError:" in r.stderr
    assert not list(tmp_path.glob(".rt-tmp-*"))
    assert (tmp_path / "blocked").is_dir()


def test_existing_report_unchanged_on_failed_replace(tmp_path, monkeypatch):
    path = tmp_path / "report.md"
    path.write_text("old", encoding="utf-8")
    def fail(*args):
        raise PermissionError("planted write failure")
    monkeypatch.setattr(os, "replace", fail)
    with pytest.raises(TrackerError, match="WriteError"):
        atomic_write(path, "new")
    assert path.read_text() == "old"
    assert not list(tmp_path.glob(".rt-tmp-*"))


def test_corrupted_snapshot_rejected(tmp_path):
    invoke(tmp_path, "fixtures", "--out", "demo")
    invoke(tmp_path, "run", "--input", "demo")
    path = tmp_path / ".rt/result.json"
    data = json.loads(path.read_text())
    data["counts"]["total"] = 999
    path.write_text(json.dumps(data))
    r = invoke(tmp_path, "report")
    assert r.returncode == 2 and "does not reconcile" in r.stderr


def test_record_schema_error_names_file_and_field(input_dir, record):
    record["amount"] = "-10.00"
    root = input_dir([record])
    with pytest.raises(TrackerError, match="amount.*records.json.*line 1"):
        load_input(root)


def test_real_label_in_synthetic_file_rejected(input_dir, record):
    record["synthetic"] = False
    root = input_dir([record])
    with pytest.raises(TrackerError, match="synthetic file"):
        load_input(root)


def test_two_input_files_duplicate_ids(tmp_path):
    generate(tmp_path)
    (tmp_path / "other.records.json").write_bytes((tmp_path / "records.json").read_bytes())
    r = invoke(tmp_path, "run", "--input", str(tmp_path))
    assert r.returncode == 2 and "duplicate id" in r.stderr


def test_category_filter(tmp_path):
    generate(tmp_path / "demo")
    r = invoke(tmp_path, "due", "--input", "demo", "--category", "domain")
    data = json.loads(r.stdout)
    assert len(data["overdue"]) == 10 and len(data["upcoming"]) == 20
    assert all(x["category"] == "domain" for x in data["upcoming"])


def test_unicode_windows_path_and_dash_roundtrip(tmp_path, record):
    root = tmp_path / "日本語 input"
    root.mkdir()
    record["name"] = "C:\\Users\\Henry café " + chr(0x2014) + " renewal"
    (root / "records.json").write_text(json.dumps({"synthetic": True, "as_of": "2026-09-30", "records": [record]}), encoding="utf-8")
    assert invoke(tmp_path, "run", "--input", str(root)).returncode == 0
    r = invoke(tmp_path, "report", "--format", "json")
    assert r.returncode == 0, r.stderr
    assert json.loads(r.stdout)["records"][0]["name"] == record["name"]
    assert chr(0x2014) not in r.stdout


@pytest.mark.parametrize("extension", ["csv", "yaml", "jsonl"])
def test_unsupported_format_named_error(tmp_path, extension):
    (tmp_path / ("bad." + extension)).write_text("broken input")
    r = invoke(tmp_path, "run", "--input", str(tmp_path))
    assert r.returncode == 2 and "SchemaError:" in r.stderr and "line 1" in r.stderr


@pytest.mark.parametrize("payload", ['{"synthetic":true,"synthetic":false}', '{"value":NaN}', '{"value":Infinity}'])
def test_ambiguous_json_rejected(tmp_path, payload):
    (tmp_path / "records.json").write_text(payload)
    r = invoke(tmp_path, "run", "--input", str(tmp_path))
    assert r.returncode == 2 and "ParseError:" in r.stderr and "line 1" in r.stderr


def test_unpaired_unicode_surrogate_rejected(tmp_path):
    from renewal_tracker.fixtures import fixture_records
    record = fixture_records()[0]
    record["name"] = chr(0xD800)
    (tmp_path / "records.json").write_text(json.dumps({"synthetic": True, "as_of": "2026-09-30", "records": [record]}))
    r = invoke(tmp_path, "run", "--input", str(tmp_path))
    assert r.returncode == 2 and "SchemaError:" in r.stderr and "name" in r.stderr
    assert "Traceback" not in r.stderr


def test_tiny_handwritten_fixture(tmp_path):
    root = Path(__file__).resolve().parents[1] / "examples/tiny"
    r = invoke(tmp_path, "run", "--input", str(root))
    assert r.returncode == 0
    r = invoke(tmp_path, "report", "--format", "json")
    assert json.loads(r.stdout)["counts"] == {"total": 5, "active": 4, "cancelled": 1, "overdue": 1, "upcoming": 2}


def test_conflicting_reference_dates_named_error(tmp_path):
    generate(tmp_path / "demo")
    path = tmp_path / "demo/records.json"
    data = json.loads(path.read_text())
    data["as_of"] = "2026-10-01"
    data["records"] = []
    (tmp_path / "demo/other.records.json").write_text(json.dumps(data))
    r = invoke(tmp_path, "run", "--input", "demo")
    assert r.returncode == 2 and "as_of differs" in r.stderr
    assert invoke(tmp_path, "run", "--input", "demo", "--as-of", "2026-09-30").returncode == 0
