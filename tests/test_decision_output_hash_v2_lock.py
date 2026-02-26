import json
from pathlib import Path

from psi.services.di.integrity import compute_decision_output_hash_v2


FIXTURE_PATH = Path(__file__).parent / "fixtures" / "decision_output_minimal_v1.json"
EXPECTED_HASH_V2 = "d86879071f93c3151c730254975f794b427aa49f7b18c40839ae7604b15a10a0"


def test_decision_output_hash_v2_lock():
    outputs_obj = json.loads(FIXTURE_PATH.read_text(encoding="utf-8"))
    got = compute_decision_output_hash_v2(inputs_obj={}, outputs_obj=outputs_obj)
    assert got == EXPECTED_HASH_V2
