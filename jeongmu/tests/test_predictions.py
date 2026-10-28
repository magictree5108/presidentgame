from fixture_db import make

from heuristics import test_defection_pre_election as h1
from predictions import backtest, pconnect, predict_at, record, score_all


def test_predict_at_uses_only_past():
    con = make()
    b4 = con.execute("SELECT * FROM bills WHERE bill_id='B4'").fetchone()
    r = predict_at(con, b4, "가결")
    # B4 발의일(2024-08-05) 전에 결과 난 법안 없음 → 사전값만
    assert r["n_committee"] == 0 and 0 < r["p"] < 1


def test_backtest_and_scoring(tmp_path):
    con = make()
    res = backtest(con, n=10, end="2025-12-31")
    assert res["n"] == 3 and "brier" in res["model"]
    pc = pconnect(tmp_path / "p.sqlite")
    record("pass", {"pass_prob": 0.8}, bill_id="B1", con=pc)
    record("pass", {"pass_prob": 0.8}, bill_id="B2", con=pc)  # 미처리 → 채점 안 됨
    assert score_all(pc, con) == 1
    row = pc.execute("SELECT score FROM predictions WHERE bill_id='B1'").fetchone()
    assert abs(row[0] - 0.04) < 1e-9


def test_h1_runs():
    con = make()
    ev = h1(con, {"test": {"window_days": 90}}, [{"name": "가상선거", "date": "2024-10-01"}])
    assert ev["result"] == "판단 불가" and "표본 부족" in ev["reason"]  # 가상 표결 2건뿐
