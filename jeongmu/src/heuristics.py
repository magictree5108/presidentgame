"""정무 경험칙을 국회 DB로 검증한다. 결과는 rules_heuristic.json 의 evidence/status 에 그대로 쓴다.

사용: python src/heuristics.py
"""
import json
import sys
from collections import Counter, defaultdict
from datetime import date, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from config import DATA
from db import connect, party_lookup

PATH = DATA / "rules_heuristic.json"
VOTED = ("찬성", "반대", "기권")


def _vote_level_defections(con):
    """표결별 (vote_date, n_party_line, n_defect)."""
    party_at = party_lookup(con)
    rows = [{"bill_id": r[0], "party": party_at(r[1], r[3]), "vote": r[2], "vote_date": r[3]}
            for r in con.execute("SELECT bill_id, member_id, vote, vote_date FROM member_votes "
                                 "WHERE vote IN ('찬성','반대','기권')")]
    rows = [r for r in rows if r["party"] not in (None, "무소속")]
    by = defaultdict(Counter)
    dates = {}
    for r in rows:
        by[(r["bill_id"], r["party"])][r["vote"]] += 1
        dates[r["bill_id"]] = r["vote_date"]
    per_bill = defaultdict(lambda: [0, 0])
    for (bid, _), c in by.items():
        top = c.most_common(2)
        n = sum(c.values())
        if n < 2 or (len(top) > 1 and top[0][1] == top[1][1]):
            continue
        per_bill[bid][0] += n
        per_bill[bid][1] += n - top[0][1]
    return [(dates[b], v[0], v[1]) for b, v in per_bill.items() if dates.get(b)]


def test_defection_pre_election(con, rule, elections) -> dict:
    w = rule["test"]["window_days"]
    data = _vote_level_defections(con)
    if not data:
        return {"result": "판단 불가", "reason": "의원별 표결 데이터 없음"}
    windows = []
    for e in elections:
        ed = date.fromisoformat(e["date"])
        windows.append(((ed - timedelta(days=w)).isoformat(), e["date"]))
    import math
    # 같은 표결 안의 의원 표는 서로 독립이 아니므로, 표결(의안) 단위 이탈률을 표본으로 비교한다(Welch t).
    pre, rest = [], []
    for d, n, k in data:
        (pre if any(a <= d < b for a, b in windows) else rest).append(k / n)
    if len(pre) < 5 or len(rest) < 5:
        return {"result": "판단 불가", "reason": f"선거 전 {w}일 구간 표결 {len(pre)}건으로 표본 부족"}

    def mv(x):
        m = sum(x) / len(x)
        return m, sum((v - m) ** 2 for v in x) / (len(x) - 1)
    (mp, vp), (mr, vr) = mv(pre), mv(rest)
    se = math.sqrt(vp / len(pre) + vr / len(rest))
    z = (mp - mr) / se if se else None
    rp, rr = mp, mr
    if z is None:
        verdict = "판단 불가"
    elif z > 1.96:
        verdict = "데이터로 확인"
    elif z < -1.96:
        verdict = "반증"
    else:
        verdict = "판단 불가"
    return {"result": verdict, "pre_rate": round(rp, 4), "rest_rate": round(rr, 4) if rr is not None else None,
            "n_pre_votes": len(pre), "n_rest_votes": len(rest), "z": round(z, 2) if z is not None else None,
            "window_days": w, "elections": [e["name"] for e in elections],
            "method": "표결(의안)마다 '같은 당 다수와 다르게 던진 표'의 비율을 구하고, 선거일 전 window_days 구간 표결과 나머지 표결의 평균을 Welch t 로 비교. |t|>1.96 이면 판단. n 은 표결 건수.",
            "limits": "22대 안에서는 지방선거 1번뿐이라 '그 시기에 어떤 법안이 올라왔는지'의 영향을 떼어낼 수 없다. 21대 등 지난 국회 총선 전후 표결을 넣으면 더 정확해진다."}


TESTS = {"defection_pre_election": test_defection_pre_election}


def run(con=None) -> dict:
    data = json.loads(PATH.read_text(encoding="utf-8"))
    con = con or connect()
    for r in data["rules"]:
        t = r.get("test")
        if not t or t.get("kind") not in TESTS:
            continue
        ev = TESTS[t["kind"]](con, r, data.get("elections", []))
        ev["checked_at"] = date.today().isoformat()
        r["evidence"] = ev
        if ev["result"] in ("데이터로 확인", "반증"):
            r["status"] = ev["result"]
    PATH.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return data


if __name__ == "__main__":
    d = run()
    for r in d["rules"]:
        print(r["id"], r["status"], r.get("evidence"))
