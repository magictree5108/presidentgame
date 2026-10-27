"""9단계: 예측 기록·자동 채점·역검증.

predictions.sqlite 에 판단 엔진의 모든 예측을 날짜와 함께 남기고, 국회 DB에 결과가 들어오면 채점한다.

사용:
  python src/predictions.py score              # 결과가 나온 예측 채점
  python src/predictions.py backtest [--n 100] # 역검증 리포트 → docs/backtest.md
"""
import argparse
import json
import random
import sqlite3
import sys
from datetime import date, datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from config import DOCS, PREDICTIONS_DB, TERM_START
from db import connect

SCHEMA = """
CREATE TABLE IF NOT EXISTS predictions (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  created_at TEXT NOT NULL,
  kind TEXT NOT NULL,          -- pass / vote_count / duration_days / next_action
  bill_id TEXT,
  subject TEXT,
  predicted TEXT NOT NULL,     -- JSON: {"pass_prob":0.7} / {"yes":180,"no":100} / {"days":120} / {"actor":..,"action":..}
  basis TEXT,                  -- JSON: 근거 참조 목록
  source TEXT,                 -- engine / backtest / manual
  resolve_by TEXT,
  outcome TEXT,
  score REAL,                  -- pass: 브라이어 점수(낮을수록 좋음) / vote_count: 찬성수 오차 / duration: 일수 오차
  scored_at TEXT
);
"""


def pconnect(path=PREDICTIONS_DB):
    con = sqlite3.connect(str(path))
    con.row_factory = sqlite3.Row
    con.executescript(SCHEMA)
    return con


def record(kind: str, predicted: dict, *, bill_id=None, subject=None, basis=None,
           source="engine", resolve_by=None, con=None) -> int:
    con = con or pconnect()
    cur = con.execute(
        "INSERT INTO predictions(created_at,kind,bill_id,subject,predicted,basis,source,resolve_by) VALUES(?,?,?,?,?,?,?,?)",
        (datetime.now().isoformat(timespec="seconds"), kind, bill_id, subject,
         json.dumps(predicted, ensure_ascii=False), json.dumps(basis or [], ensure_ascii=False), source, resolve_by))
    con.commit()
    return cur.lastrowid


def passed(result: str | None, target: str = "가결") -> bool | None:
    if not result:
        return None
    if target == "반영":
        return "가결" in result or "대안반영" in result
    return "가결" in result


def score_all(pcon=None, acon=None) -> int:
    pcon = pcon or pconnect()
    acon = acon or connect()
    n = 0
    for p in pcon.execute("SELECT * FROM predictions WHERE scored_at IS NULL AND bill_id IS NOT NULL"):
        b = acon.execute("SELECT * FROM bills WHERE bill_id=?", (p["bill_id"],)).fetchone()
        pred = json.loads(p["predicted"])
        outcome, score = None, None
        if p["kind"] == "pass" and b and b["proc_result"]:
            y = passed(b["proc_result"], pred.get("target", "가결"))
            outcome = {"proc_result": b["proc_result"], "passed": y}
            score = (pred["pass_prob"] - float(y)) ** 2
        elif p["kind"] == "vote_count":
            v = acon.execute("SELECT * FROM votes WHERE bill_id=?", (p["bill_id"],)).fetchone()
            if v and v["yes"] is not None:
                outcome = {"yes": v["yes"], "no": v["no"], "abstain": v["abstain"]}
                score = abs(pred["yes"] - v["yes"])
        elif p["kind"] == "duration_days" and b and b["plenary_dt"] and b["propose_dt"]:
            d = (date.fromisoformat(b["plenary_dt"]) - date.fromisoformat(b["propose_dt"])).days
            outcome = {"days": d}
            score = abs(pred["days"] - d)
        if outcome is not None:
            pcon.execute("UPDATE predictions SET outcome=?, score=?, scored_at=? WHERE id=?",
                         (json.dumps(outcome, ensure_ascii=False), score, date.today().isoformat(), p["id"]))
            n += 1
    pcon.commit()
    return n


# ------------------------------------------------------------------ 역검증
def _rate(k, n, prior, strength):
    return (k + prior * strength) / (n + strength)


def predict_at(acon, bill, target: str) -> dict:
    """발의 시점(propose_dt 전날까지)의 데이터만으로 통과 확률을 낸다.

    모델(투명한 규칙 기반):
      p_cmt   = 같은 위원회에서 그 시점까지 결과가 난 법안의 통과율(전체율로 평활)
      p_spon  = 대표발의자의 그 시점까지 결과가 난 대표발의 법안 통과율(위원회율로 평활)
      p       = 0.5*p_cmt + 0.5*p_spon, 공동발의자 중 다른 당 의원이 있으면 로짓 +0.3
    """
    as_of = bill["propose_dt"]

    def done_rows(where, args):
        return acon.execute(
            f"""SELECT proc_result FROM bills WHERE proc_result IS NOT NULL
                AND COALESCE(plenary_dt, law_proc_dt, cmt_proc_dt) < ? AND {where}""",
            (as_of, *args)).fetchall()

    allr = done_rows("1=1", ())
    k_all = sum(passed(r[0], target) for r in allr)
    p_all = _rate(k_all, len(allr), 0.3, 10)
    cm = done_rows("committee = ?", (bill["committee"],))
    k_cm = sum(passed(r[0], target) for r in cm)
    p_cmt = _rate(k_cm, len(cm), p_all, 20)
    lead = acon.execute("SELECT member_id FROM bill_sponsors WHERE bill_id=? AND role='lead'", (bill["bill_id"],)).fetchone()
    p_spon, n_sp = p_cmt, 0
    if lead and lead[0]:
        sp = done_rows("bill_id IN (SELECT bill_id FROM bill_sponsors WHERE member_id=? AND role='lead')", (lead[0],))
        n_sp = len(sp)
        p_spon = _rate(sum(passed(r[0], target) for r in sp), n_sp, p_cmt, 10)
    p = 0.5 * p_cmt + 0.5 * p_spon
    cross = 0
    if lead and lead[0]:
        parties = acon.execute(
            """SELECT DISTINCT p.party FROM bill_sponsors s JOIN party_affiliations p ON p.member_id=s.member_id
               AND p.start_date<=? AND (p.end_date IS NULL OR p.end_date>?) WHERE s.bill_id=?""",
            (as_of, as_of, bill["bill_id"])).fetchall()
        cross = len(parties) > 1
    if cross:
        import math
        lo = math.log(p / (1 - p)) + 0.3
        p = 1 / (1 + math.exp(-lo))
    return {"p": p, "p_baseline": p_cmt, "n_committee": len(cm), "n_sponsor": n_sp, "cross_party": bool(cross)}


def backtest(acon=None, n: int = 100, seed: int = 22, end: str = "2026-05-29", target: str = "가결") -> dict:
    """22대 전반기(임기 시작~end) 처리 완료 법안 중 n건 무작위 표본으로 역검증."""
    acon = acon or connect()
    pool = acon.execute(
        """SELECT * FROM bills WHERE proc_result IS NOT NULL AND propose_dt >= ? AND propose_dt <= ?
           AND COALESCE(plenary_dt, law_proc_dt, cmt_proc_dt) <= ?""", (TERM_START, end, end)).fetchall()
    if not pool:
        return {"error": "처리 완료 법안이 DB에 없음(국회 데이터 수집 전)"}
    rng = random.Random(seed)
    sample = rng.sample(pool, min(n, len(pool)))
    rows = []
    for b in sample:
        pr = predict_at(acon, b, target)
        y = float(passed(b["proc_result"], target))
        rows.append({"bill_id": b["bill_id"], "bill_name": b["bill_name"], "committee": b["committee"],
                     "propose_dt": b["propose_dt"], "result": b["proc_result"], "y": y, **pr})

    def metrics(key):
        brier = sum((r[key] - r["y"]) ** 2 for r in rows) / len(rows)
        acc = sum((r[key] >= 0.5) == bool(r["y"]) for r in rows) / len(rows)
        return {"brier": round(brier, 4), "accuracy": round(acc, 4)}

    model, base = metrics("p"), metrics("p_baseline")
    return {"n": len(rows), "pool": len(pool), "seed": seed, "target": target, "end": end,
            "model": model, "baseline": base, "rows": rows,
            "model_worse": model["brier"] > base["brier"]}


def write_report(res: dict, path: Path = DOCS / "backtest.md"):
    if "error" in res:
        path.write_text(f"# 역검증 리포트\n\n실행 불가: {res['error']}\n", encoding="utf-8")
        return
    first = ("**모델이 기준 예측(위원회 평균 통과율로 찍기)보다 못했다.**" if res["model_worse"]
             else "모델이 기준 예측(위원회 평균 통과율로 찍기)보다 브라이어 점수가 낮았다(좋았다).")
    lines = [first, "", f"# 역검증 리포트 ({date.today()})", "",
             f"- 표본: 22대 전반기(~{res['end']}) 처리 완료 법안 {res['pool']}건 중 무작위 {res['n']}건 (seed {res['seed']})",
             f"- 맞힐 대상: '{res['target']}' 여부",
             "- 규칙: 각 법안의 발의일 전날까지 결과가 난 법안만 사용(미래 정보 차단)", "",
             "| 방법 | 브라이어 점수(낮을수록 좋음) | 정확도(0.5 기준) |", "|---|---|---|",
             f"| 위원회 평균 통과율로 찍기(기준) | {res['baseline']['brier']} | {res['baseline']['accuracy']} |",
             f"| 정무상황실 규칙 모델 | {res['model']['brier']} | {res['model']['accuracy']} |", "",
             "## 법안별", "", "| 법안 | 위원회 | 발의일 | 결과 | 모델 p | 기준 p |", "|---|---|---|---|---|---|"]
    for r in res["rows"]:
        lines.append(f"| {r['bill_name']} | {r['committee']} | {r['propose_dt']} | {r['result']} | {r['p']:.2f} | {r['p_baseline']:.2f} |")
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("cmd", choices=["score", "backtest"])
    ap.add_argument("--n", type=int, default=100)
    ap.add_argument("--target", default="가결", choices=["가결", "반영"])
    a = ap.parse_args()
    if a.cmd == "score":
        print(f"채점 {score_all()}건")
    else:
        r = backtest(n=a.n, target=a.target)
        write_report(r)
        for p in ("model", "baseline"):
            print(p, r.get(p))
        record_n = 0
        if "rows" in r:
            pc = pconnect()
            for row in r["rows"]:
                record("pass", {"pass_prob": row["p"], "target": a.target}, bill_id=row["bill_id"],
                       subject=row["bill_name"], source="backtest", con=pc)
                record_n += 1
            score_all(pc)
        print(f"docs/backtest.md 작성, 역검증 예측 {record_n}건 기록")
