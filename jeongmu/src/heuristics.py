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
from db import connect

PATH = DATA / "rules_heuristic.json"
VOTED = ("찬성", "반대", "기권")


def _vote_level_defections(con):
    """표결별 (vote_date, n_party_line, n_defect)."""
    rows = con.execute(
        "SELECT bill_id, party, vote, vote_date FROM member_votes WHERE vote IN ('찬성','반대','기권')").fetchall()
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
    pre = [0, 0]
    rest = [0, 0]
    for d, n, k in data:
        tgt = pre if any(a <= d < b for a, b in windows) else rest
        tgt[0] += n
        tgt[1] += k
    if pre[0] == 0:
        return {"result": "판단 불가", "reason": f"선거 전 {w}일 구간에 표결 기록 없음", "n_rest": rest[0]}
    rp, rr = pre[1] / pre[0], rest[1] / rest[0] if rest[0] else None
    # 두 비율 차이의 대략적 유의성(정규근사)
    import math
    p = (pre[1] + rest[1]) / (pre[0] + rest[0])
    se = math.sqrt(p * (1 - p) * (1 / pre[0] + 1 / rest[0])) if rest[0] and 0 < p < 1 else None
    z = (rp - rr) / se if se else None
    if z is None:
        verdict = "판단 불가"
    elif z > 1.96:
        verdict = "데이터로 확인"
    elif z < -1.96:
        verdict = "반증"
    else:
        verdict = "판단 불가"
    return {"result": verdict, "pre_rate": round(rp, 4), "rest_rate": round(rr, 4) if rr is not None else None,
            "n_pre_votes": pre[0], "n_rest_votes": rest[0], "z": round(z, 2) if z is not None else None,
            "window_days": w, "elections": [e["name"] for e in elections],
            "method": "표결별 같은 당 다수와 다른 표(찬성·반대·기권)의 비율. 선거일 전 window_days 구간 대 나머지. |z|>1.96 이면 판단.",
            "limits": "22대 국회 안에서는 선거가 적어 표본이 작다. 지난 국회 표결 데이터를 넣으면 더 정확해진다."}


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
