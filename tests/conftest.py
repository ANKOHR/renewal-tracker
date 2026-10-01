import json
import pytest
from renewal_tracker.fixtures import fixture_records, AS_OF
from renewal_tracker.core import analyse

@pytest.fixture
def record():
    return dict(fixture_records()[0])

@pytest.fixture
def result():
    return analyse(fixture_records(), AS_OF)

@pytest.fixture
def input_dir(tmp_path):
    def write(records, synthetic=True):
        root = tmp_path / "input"
        root.mkdir(exist_ok=True)
        (root / "records.json").write_text(json.dumps({"synthetic": synthetic, "as_of": AS_OF, "records": records}, ensure_ascii=False), encoding="utf-8")
        return root
    return write
