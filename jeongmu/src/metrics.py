"""3단계 분석 지표. assembly.sqlite → metrics.sqlite + data/metrics/*.json

모든 결과에 as_of(계산 기준일)와 표본 수(n_*)를 붙인다.
사용: python src/metrics.py [--as-of YYYY-MM-DD]
  --as-of 를 주면 그 날짜까지의 기록만 쓴다(역검증용).
"""
import argparse
import json
import sqlite3
import statistics
import sys
from collections import Counter, defaultdict
from datetime import date
from itertools import combinations
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from config import METRICS_DB, METRICS_JSON
from db import connect, party_lookup

VOTED = ("찬성", "반대", "기권")


def member_vote_metrics(con, as_of: str) -> dict[str, dict]:
    """당론 이탈률과 출석률.

    이탈: 같은 표결에서 같은 당(표결일 기준 당적 이력) 투표자 다수와 다르게 표결. 무소속·당적 미확인은 제외. 다수가 동률이면 그 표결은 제외.
    출석: 표결 기록이 있는 본회의 표결 중 '불참'이 아닌 비율.
    """
    party_at = party_lookup(con)
    rows = [{"bill_id": r[0], "member_id": r[1], "vote": r[3],
             "party": party_at(r[1], r[2]) or "미확인"}
            for r in con.execute(
                "SELECT bill_id, member_id, vote_date, vote FROM member_votes WHERE vote_date <= ? AND member_id IS NOT NULL",
                (as_of,))]
    by_bill_party: dict[tuple, Counter] = defaultdict(Counter)
    for r in rows:
        if r["vote"] in VOTED and r["party"] not in ("무소속", "미확인"):
            by_bill_party[(r["bill_id"], r["party"])][r["vote"]] += 1
    majority = {}
    for k, c in by_bill_party.items():
        top = c.most_common(2)
        if sum(c.values()) >= 2 and (len(top) == 1 or top[0][1] > top[1][1]):
            majority[k] = top[0][0]
    out: dict[str, dict] = defaultdict(lambda: {"n_votes": 0, "n_present": 0, "n_party_line": 0, "n_defect": 0})
    for r in rows:
        m = out[r["member_id"]]
        m["n_votes"] += 1
        if r["vote"] in VOTED:
            m["n_present"] += 1
            maj = majority.get((r["bill_id"], r["party"]))
            if maj:
                m["n_party_line"] += 1
                m["n_defect"] += r["vote"] != maj
    for m in out.values():
        m["attendance_rate"] = round(m["n_present"] / m["n_votes"], 4) if m["n_votes"] else None
        m["defection_rate"] = round(m["n_defect"] / m["n_party_line"], 4) if m["n_party_line"] else None
    return dict(out)


def sponsor_metrics(con, as_of: str):
    rows = con.execute(
        """SELECT s.bill_id, s.member_id, s.role, b.committee FROM bill_sponsors s
           JOIN bills b ON b.bill_id = s.bill_id
           WHERE b.propose_dt <= ? AND s.member_id IS NOT NULL""", (as_of,)).fetchall()
    fields: dict[str, Counter] = defaultdict(Counter)
    lead_n: Counter = Counter()
    bills: dict[str, set] = defaultdict(set)
    for r in rows:
        fields[r["member_id"]][r["committee"] or "미배정"] += 1
        if r["role"] == "lead":
            lead_n[r["member_id"]] += 1
        bills[r["bill_id"]].add(r["member_id"])
    pair: Counter = Counter()
    for members in bills.values():
        if len(members) > 60:  # 수십 명이 같이 낸 당론성 법안은 관계 신호가 약하다
            continue
        for a, b in combinations(sorted(members), 2):
            pair[(a, b)] += 1
    return fields, lead_n, pair


def party_on(con, member_id: str, on: str) -> str | None:
    r = con.execute(
        """SELECT party FROM party_affiliations WHERE member_id=? AND start_date<=?
           AND (end_date IS NULL OR end_date>?) ORDER BY start_date DESC""", (member_id, on, on)).fetchone()
    return r[0] if r else None


def network(con, pair: Counter, as_of: str, min_weight: int = 2):
    party = {m: party_on(con, m, as_of) for m in {x for p in pair for x in p}}
    edges = []
    cross = Counter()
    deg = Counter()
    for (a, b), w in pair.items():
        if w < min_weight:
            continue
        x = party.get(a) != party.get(b) and party.get(a) and party.get(b)
        edges.append({"a": a, "b": b, "w": w, "cross_party": bool(x)})
        deg[a] += w
        deg[b] += w
        if x:
            cross[a] += w
            cross[b] += w
    bip = {m: round(cross[m] / deg[m], 4) for m in deg}
    return edges, bip


def top_partners(pair: Counter, k: int = 10) -> dict[str, list]:
    by: dict[str, list] = defaultdict(list)
    for (a, b), w in pair.items():
        by[a].append((b, w))
        by[b].append((a, w))
    return {m: sorted(v, key=lambda x: -x[1])[:k] for m, v in by.items()}


def _days(a, b):
    try:
        return (date.fromisoformat(b) - date.fromisoformat(a)).days
    except (TypeError, ValueError):
        return None


def precedent_stats(con, as_of: str, key: str = "committee", start: str | None = None, end: str | None = None) -> dict:
    """위원회별 선례 통계. key 는 committee 만 지원(분야=소관위원회로 본다).
    start/end 를 주면 그 기간에 발의된 법안만 본다(정부 시기별 비교용)."""
    bills = con.execute(
        "SELECT * FROM bills WHERE propose_dt <= ? AND propose_dt >= ? AND propose_dt <= ?",
        (as_of, start or "0000", end or "9999")).fetchall()
    vetoed = {r[0] for r in con.execute("SELECT bill_id FROM vetoes WHERE bill_id IS NOT NULL")}
    groups: dict[str, list] = defaultdict(list)
    for b in bills:
        groups[b[key] or "미배정"].append(b)
        groups["전체"].append(b)
    today = date.today().isoformat()

    def known(b):
        """as_of 시점에 결과가 알려져 있었는가. 결과일이 없으면 오늘 기준일 때만 인정."""
        if not b["proc_result"]:
            return False
        d = b["plenary_dt"] or b["law_proc_dt"] or b["cmt_proc_dt"]
        return d <= as_of if d else as_of >= today

    out = {}
    for g, bs in groups.items():
        n = len(bs)
        done = [b for b in bs if known(b)]
        passed = [b for b in done if "가결" in b["proc_result"]]
        pending = [b for b in bs if not known(b)]
        alt = [b for b in done if "대안반영" in b["proc_result"]]
        at_jud = [b for b in pending if ((b["law_submit_dt"] or "9") <= as_of or (b["cmt_proc_dt"] or "9") <= as_of)
                  and not (b["law_proc_dt"] and b["law_proc_dt"] <= as_of)]
        durations = [d for d in (_days(b["propose_dt"], b["plenary_dt"]) for b in passed) if d is not None]
        out[g] = {
            "n_bills": n,
            "n_passed": len(passed),
            "pass_rate": round(len(passed) / n, 4) if n else None,
            "pending_rate": round(len(pending) / n, 4) if n else None,
            "alt_reflected_rate": round(len(alt) / n, 4) if n else None,
            "stalled_at_judiciary_rate": round(len(at_jud) / n, 4) if n else None,
            "n_with_duration": len(durations),
            "median_days_to_plenary": statistics.median(durations) if durations else None,
            "p25_days": statistics.quantiles(durations, n=4)[0] if len(durations) >= 4 else None,
            "p75_days": statistics.quantiles(durations, n=4)[2] if len(durations) >= 4 else None,
            "n_vetoed": sum(1 for b in bs if b["bill_id"] in vetoed),
            "n_decided": len(done),
        }
    return out


def precedent_by_period(con, as_of: str) -> dict:
    """data/government_periods.json 의 정부 시기별 위원회 선례 통계."""
    p = Path(__file__).resolve().parent.parent / "data" / "government_periods.json"
    if not p.exists():
        return {}
    out = {}
    for per in json.loads(p.read_text(encoding="utf-8"))["periods"]:
        if per["start"] > as_of:
            continue
        out[per["name"]] = {"start": per["start"], "end": per["end"],
                            "by_committee": precedent_stats(con, as_of, start=per["start"], end=per["end"])}
    return out


METRICS_SCHEMA = """
CREATE TABLE IF NOT EXISTS member_metrics (member_id TEXT, as_of TEXT, data TEXT, PRIMARY KEY(member_id, as_of));
CREATE TABLE IF NOT EXISTS edges (a TEXT, b TEXT, w INTEGER, cross_party INTEGER, as_of TEXT);
CREATE TABLE IF NOT EXISTS precedents (grp TEXT, as_of TEXT, data TEXT, PRIMARY KEY(grp, as_of));
"""


def compute(con, as_of: str) -> dict:
    votes = member_vote_metrics(con, as_of)
    fields, lead_n, pair = sponsor_metrics(con, as_of)
    edges, bip = network(con, pair, as_of)
    partners = top_partners(pair)
    names = {r[0]: r[1] for r in con.execute("SELECT member_id, name FROM members")}
    members = {}
    for mid in set(names) | set(votes) | set(fields):
        v = votes.get(mid, {})
        members[mid] = {
            "member_id": mid, "name": names.get(mid), "as_of": as_of,
            **{k: v.get(k) for k in ("n_votes", "n_present", "n_party_line", "n_defect", "attendance_rate", "defection_rate")},
            "n_lead_bills": lead_n.get(mid, 0),
            "n_sponsored_bills": sum(fields.get(mid, {}).values()),
            "fields": dict(fields.get(mid, Counter()).most_common(8)),
            "top_cosponsors": [{"member_id": p, "name": names.get(p), "shared_bills": w} for p, w in partners.get(mid, [])],
            "bipartisan_share": bip.get(mid),
        }
    return {"as_of": as_of, "members": members, "edges": edges, "precedents": precedent_stats(con, as_of),
            "precedents_by_period": precedent_by_period(con, as_of)}


def save(result: dict, path=METRICS_DB, json_dir: Path = METRICS_JSON):
    m = sqlite3.connect(str(path))
    m.executescript(METRICS_SCHEMA)
    a = result["as_of"]
    m.execute("DELETE FROM edges WHERE as_of=?", (a,))
    for mid, d in result["members"].items():
        m.execute("INSERT OR REPLACE INTO member_metrics VALUES(?,?,?)", (mid, a, json.dumps(d, ensure_ascii=False)))
    m.executemany("INSERT INTO edges VALUES(?,?,?,?,?)",
                  [(e["a"], e["b"], e["w"], int(e["cross_party"]), a) for e in result["edges"]])
    for g, d in result["precedents"].items():
        m.execute("INSERT OR REPLACE INTO precedents VALUES(?,?,?)", (g, a, json.dumps(d, ensure_ascii=False)))
    m.commit()
    m.close()
    json_dir.mkdir(parents=True, exist_ok=True)
    (json_dir / "members.json").write_text(json.dumps({"as_of": a, "members": result["members"]}, ensure_ascii=False), encoding="utf-8")
    (json_dir / "network.json").write_text(json.dumps({"as_of": a, "edges": result["edges"]}, ensure_ascii=False), encoding="utf-8")
    (json_dir / "precedents.json").write_text(json.dumps({"as_of": a, "by_committee": result["precedents"], "by_period": result.get("precedents_by_period", {})}, ensure_ascii=False, indent=1), encoding="utf-8")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--as-of", default=date.today().isoformat())
    a = ap.parse_args()
    con = connect()
    r = compute(con, a.as_of)
    save(r)
    print(f"의원 {len(r['members'])}명, 관계 {len(r['edges'])}개, 위원회 {len(r['precedents'])}개 저장 (기준일 {a.as_of})")
