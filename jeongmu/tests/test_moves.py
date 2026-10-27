"""워게임 합법성 검사 테스트. 의석수는 테스트용 가상값이며 실제 정당 의석이 아니다."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from moves import check, need

STATE = {
    "total": 300,
    "seats": {"갑당": 170, "을당": 108, "병당": 12, "정당": 10},
    "committees": {"가위원회": {"갑당": 10, "을당": 7, "병당": 1, "total": 18}},
    "bills": {
        "B1": {"stage": "소관위 심사", "committee": "가위원회"},
        "B2": {"stage": "정부이송", "days_since_transfer": 5},
        "B3": {"stage": "법사위 심사", "committee": "가위원회", "days_in_judiciary": 61},
        "B4": {"stage": "본회의 통과", "vetoed": True},
    },
    "filibuster": {"B1": {"cloture_filed_hours_ago": 10}},
}


def test_need():
    assert need({"num": 3, "den": 5}, 300) == 180
    assert need({"num": 1, "den": 2, "strict": True}, 300) == 151
    assert need({"num": 1, "den": 2, "strict": True}, 299) == 150
    assert need({"num": 2, "den": 3}, 299) == 200
    assert need({"num": 1, "den": 3}, 300) == 100


def test_fast_track_blocked_without_three_fifths():
    v = check(STATE, {"type": "fast_track", "bill": "B1", "supporters": ["갑당"]})
    assert not v["allowed"] and v["rule_id"] == "R4"
    v = check(STATE, {"type": "fast_track", "bill": "B1", "supporters": ["갑당", "병당"]})
    assert v["allowed"]  # 182 >= 180


def test_fast_track_committee_route():
    v = check(STATE, {"type": "fast_track", "bill": "B1", "route": "committee", "supporters": ["갑당"]})
    assert not v["allowed"]  # 10 < 11
    v = check(STATE, {"type": "fast_track", "bill": "B1", "route": "committee", "supporters": ["갑당", "병당"]})
    assert v["allowed"]


def test_filibuster_and_cloture():
    assert check(STATE, {"type": "filibuster", "bill": "B1", "supporters": ["을당"]})["allowed"]
    assert not check(STATE, {"type": "filibuster", "bill": "B1", "supporters": ["병당"]})["allowed"]
    v = check(STATE, {"type": "filibuster", "action": "cloture_vote", "bill": "B1", "supporters": ["갑당", "병당"]})
    assert not v["allowed"] and "24시간" in v["reason"]


def test_veto_rules():
    assert check(STATE, {"type": "veto", "bill": "B2", "actor_role": "대통령"})["allowed"]
    assert not check(STATE, {"type": "veto", "bill": "B2", "actor_role": "대통령", "partial": True})["allowed"]
    assert not check(STATE, {"type": "veto", "bill": "B1", "actor_role": "대통령"})["allowed"]
    assert not check(STATE, {"type": "veto", "bill": "B2", "actor_role": "국무총리"})["allowed"]


def test_override_and_impeach():
    assert not check(STATE, {"type": "override_veto", "bill": "B4", "supporters": ["갑당", "병당"]})["allowed"]
    assert not check(STATE, {"type": "override_veto", "bill": "B4", "supporters": ["갑당", "병당", "정당"]})["allowed"]  # 192 < 200
    assert check(STATE, {"type": "override_veto", "bill": "B4", "supporters": ["갑당", "을당"]})["allowed"]
    v = check(STATE, {"type": "impeach", "target_role": "대통령", "supporters": ["을당", "병당"]})
    assert not v["allowed"]  # 120 < 151 발의
    v = check(STATE, {"type": "impeach", "target_role": "대통령", "supporters": ["갑당"]})
    assert v["allowed"] and "부족" in v["reason"]  # 발의 가능, 의결(200) 부족


def test_judiciary_bypass_and_speaker():
    assert check(STATE, {"type": "judiciary_bypass", "bill": "B3", "supporters": ["갑당", "병당"]})["allowed"]
    assert not check(STATE, {"type": "speaker_deadline", "bill": "B1", "actor_role": "의장"})["allowed"]
    st = {**STATE, "speaker_conditions": ["교섭단체 대표 합의"]}
    assert check(st, {"type": "speaker_deadline", "bill": "B1", "actor_role": "의장"})["allowed"]


def test_negotiating_group_and_mediation():
    assert not check(STATE, {"type": "form_negotiating_group", "supporters": ["병당"]})["allowed"]
    assert check(STATE, {"type": "form_negotiating_group", "supporters": ["병당", "정당"]})["allowed"]
    assert check(STATE, {"type": "mediation_committee", "bill": "B1", "supporters": ["을당"]})["allowed"]
    assert not check(STATE, {"type": "mediation_committee", "bill": "B3", "supporters": ["을당"]})["allowed"]
