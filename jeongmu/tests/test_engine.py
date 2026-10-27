from fixture_db import make

from engine import Bundle, check_refs, judge, law_base
from metrics import compute


def test_law_base():
    assert law_base("가법 일부개정법률안(홍길동의원 등 10인)") == "가법"
    assert law_base("나법 전부개정법률안") == "나법"


def test_check_refs_marks_weak():
    items = check_refs([{"text": "a", "refs": ["E1", "E99"]}, {"text": "b", "refs": []}], {"E1"})
    assert items[0]["refs"] == ["E1"] and items[0]["invalid_refs"] == ["E99"] and not items[0]["weak"]
    assert items[1]["weak"]


def test_judge_without_ai():
    con = make()
    m = compute(con, "2025-12-31")["members"]
    r = judge({"bill_id": "B2"}, on="2025-12-31", use_ai=False, record_prediction=False, con=con, metrics=m)
    assert not r["ai_used"]
    assert {e["label"] for e in r["evidence"]} >= {"기록", "규칙"}
    assert len(r["member_forecast"]) == 6  # 현직 M1,M2,M3,M4,M6,M7 (M5 상실)
    lead = {f["member_id"]: f for f in r["member_forecast"]}
    assert lead["M2"]["forecast"] == "찬성"  # 대표발의자(M1) 정당 = 갑당 → 기본값 찬성
    assert lead["M3"]["forecast"] == "유동"  # 병당, 입장 근거 없음
    assert r["path"][0]["rule"] == "R4" and r["pass_prob"] is not None
