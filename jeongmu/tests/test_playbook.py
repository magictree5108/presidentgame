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


def test_export_clean_strips_codes():
    import export_report
    t = export_report.clean("결론을 냅니다[E12][E13]. L22·W26에 따라 흡수합니다. 조항을 내주는 C3로 흡수합니다. 시한을 겁니다(S4).")
    assert "E12" not in t and "L22" not in t and "C3" not in t and "S4" not in t
    assert "결론을 냅니다." in t and "시한을 겁니다" in t
