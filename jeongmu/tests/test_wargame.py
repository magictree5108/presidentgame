"""가상 세력으로 3턴 이상 진행되는지, 불가능한 수가 걸러지는지 확인."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from wargame import new_game, play_turn


def game():
    return new_game(
        seats={"갑당": 170, "을당": 108, "병당": 12, "정당": 10}, total=300,
        bill={"name": "가상법안", "committee": "가위원회"},
        actors=[{"name": "갑당", "kind": "party", "stance": "찬성"},
                {"name": "을당", "kind": "party", "stance": "반대"},
                {"name": "대통령", "kind": "president", "stance": "반대"}],
        player="갑당", committee_comp={"갑당": 10, "을당": 7, "병당": 1},
        coalitions={"갑당": ["갑당"], "을당": ["을당"]})


def test_illegal_fast_track_rejected():
    r = play_turn(game(), {"type": "fast_track"})
    assert r["rejected"] and r["game"]["turn"] == 0
    assert "5분의 3" in r["entry"]["check"]["reason"]


def test_three_plus_turns():
    g = game()
    g["coalitions"]["갑당"] = ["갑당", "병당"]
    moves = [{"type": "fast_track"}, {"type": "committee_pass"}, {"type": "negotiate"},
             {"type": "negotiate"}, {"type": "negotiate"}, {"type": "negotiate"}]
    for m in moves:
        r = play_turn(g, m)
        assert not r["rejected"], r["entry"]
        g = r["game"]
    assert g["turn"] == 6 and g["day"] == 42
    stage = g["bills"]["X"]["stage"]
    # 신속처리 지정 후 소관위 의결 → 법사위 30일 경과로 본회의 부의 간주 → 이후 진행
    assert stage != "소관위 심사"
    effects = [e["effect"] for e in g["log"]]
    assert any("본회의 부의 간주" in (x or "") for x in effects)
    assert all(e.get("label") in ("시뮬레이션", "규칙") for e in g["log"])
