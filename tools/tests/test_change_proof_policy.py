import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]


def test_change_proof_policy_matches_the_entrance_use_rules():
    policy = json.loads((ROOT / ".github" / "change-proof.json").read_bytes())
    entrance = json.loads((ROOT / "lib" / "use-rules.json").read_bytes())

    assert policy == entrance
