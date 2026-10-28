import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

import playbook


def test_principles_valid():
    d = playbook.load()
    ps = d["principles"]
    assert len({p["id"] for p in ps}) == len(ps)
    for p in ps:
        assert p["book"] in d["books"] and p["mode"] in ("공격", "방어")
        assert set(p["tags"]) <= set(d["tags"]) and p["loc"] and p["apply"]


def test_check_principles_drops_unknown():
    out = playbook.check_principles([{"principles": ["D3", "Z99"]}])
    assert out[0]["principles"] == ["D3"] and out[0]["principles_dropped"] == ["Z99"]
