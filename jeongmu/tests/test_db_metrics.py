from fixture_db import make

from db import compute_stage, seats_on
from metrics import compute


def test_seats_on_dates():
    con = make()
    s = seats_on(con, "2024-06-01")
    assert s["total"] == 6 and s["by_party"] == {"갑당": 3, "을당": 2, "병당": 1}
    s = seats_on(con, "2025-03-01")  # M3 당적 변경 당일부터 병당
    assert s["by_party"] == {"갑당": 2, "을당": 2, "병당": 2}
    s = seats_on(con, "2025-07-01")  # M5 상실 후, 보궐 전
    assert s["total"] == 5 and s["vacant"] == 295
    s = seats_on(con, "2025-10-01")
    assert s["by_party"]["갑당"] == 3 and s["total"] == 6


def test_stage():
    assert compute_stage({"proc_result": "대안반영폐기"}) == "폐기·철회"
    assert compute_stage({"proc_result": "수정가결"}) == "본회의 통과"
    assert compute_stage({"law_submit_dt": "2024-01-01"}) == "법사위 심사"
    assert compute_stage({"cmt_present_dt": "2024-01-01"}) == "소관위 심사"


def test_member_metrics():
    r = compute(make(), "2025-12-31")
    m3 = r["members"]["M3"]
    assert m3["n_party_line"] == 2 and m3["n_defect"] == 1 and m3["defection_rate"] == 0.5
    m2 = r["members"]["M2"]
    assert m2["attendance_rate"] == 0.5
    # M6 은 병당 단독 투표자라 당 다수 판단 불가 → 이탈률 없음
    assert r["members"]["M6"]["defection_rate"] is None
    m1 = r["members"]["M1"]
    assert m1["n_lead_bills"] == 2
    assert m1["top_cosponsors"][0]["member_id"] in ("M2", "M4")


def test_precedents_and_as_of():
    r = compute(make(), "2025-12-31")
    g = r["precedents"]["가위원회"]
    assert g["n_bills"] == 3 and g["n_passed"] == 2 and g["stalled_at_judiciary_rate"] == round(1 / 3, 4)
    assert g["median_days_to_plenary"] == (62 + 122) / 2
    assert r["precedents"]["나위원회"]["alt_reflected_rate"] == 1.0
    early = compute(make(), "2024-07-05")
    assert early["precedents"]["전체"]["n_bills"] == 1


def test_no_future_leak():
    r = compute(make(), "2024-10-01")
    g = r["precedents"]["가위원회"]
    assert g["n_bills"] == 3 and g["n_passed"] == 1  # B4 는 2024-12-05 에 가결 → 아직 모름
    assert g["pending_rate"] == round(2 / 3, 4)
