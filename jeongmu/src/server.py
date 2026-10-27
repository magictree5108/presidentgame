"""정무상황실 웹 서버. 실행: python run.py  →  http://127.0.0.1:8000"""
import csv
import json
import sys
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse, PlainTextResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

import engine
import moves
import wargame
from config import ASSEMBLY_DB, DATA, DOCS, METRICS_JSON, ROOT, env
from db import connect, seats_on

app = FastAPI(title="정무상황실")
WEB = ROOT / "web"
GAMES = DATA / "wargames"


def con():
    return connect(ASSEMBLY_DB)


def jload(p: Path, default=None):
    return json.loads(p.read_text(encoding="utf-8")) if p.exists() else default


@app.get("/")
def index():
    return FileResponse(WEB / "index.html")


app.mount("/web", StaticFiles(directory=WEB), name="web")


@app.get("/api/status")
def status():
    c = con()
    meta = {r[0]: r[1] for r in c.execute("SELECT key, value FROM meta")}
    counts = {t: c.execute(f"SELECT COUNT(*) FROM {t}").fetchone()[0]
              for t in ("members", "bills", "bill_sponsors", "votes", "member_votes", "committee_roles")}
    rules = jload(DATA / "rules_institutional.json", {})
    from llm import usage_summary
    return {"today": date.today().isoformat(), "meta": meta, "counts": counts,
            "keys": {"assembly": bool(env("ASSEMBLY_API_KEY")), "naver": bool(env("NAVER_CLIENT_ID")),
                     "anthropic": bool(env("ANTHROPIC_API_KEY"))},
            "rules_verified": rules.get("_verified_summary"), "usage": usage_summary(),
            "metrics_as_of": (jload(METRICS_JSON / "members.json", {}) or {}).get("as_of")}


@app.get("/api/seats")
def seats(on: str | None = None):
    c = con()
    s = seats_on(c, on)
    on = s["date"]
    rows = c.execute(
        """SELECT m.member_id, m.name, m.district, m.elect_type, m.committees, p.party
           FROM member_terms t JOIN members m ON m.member_id=t.member_id
           LEFT JOIN party_affiliations p ON p.member_id=t.member_id AND p.start_date<=? AND (p.end_date IS NULL OR p.end_date>?)
           WHERE t.start_date<=? AND (t.end_date IS NULL OR t.end_date>?)""", (on, on, on, on)).fetchall()
    return {**s, "members": [dict(r) for r in rows], "label": "기록"}


@app.get("/api/members/{member_id}")
def member(member_id: str):
    c = con()
    m = c.execute("SELECT * FROM members WHERE member_id=?", (member_id,)).fetchone()
    if not m:
        raise HTTPException(404, "의원 없음")
    d = dict(m)
    d.pop("raw_json", None)
    d["terms"] = [dict(r) for r in c.execute("SELECT * FROM member_terms WHERE member_id=? ORDER BY start_date", (member_id,))]
    d["parties"] = [dict(r) for r in c.execute("SELECT * FROM party_affiliations WHERE member_id=? ORDER BY start_date", (member_id,))]
    d["lead_bills"] = [dict(r) for r in c.execute(
        """SELECT b.bill_id, b.bill_name, b.propose_dt, b.stage, b.proc_result, b.detail_link FROM bill_sponsors s
           JOIN bills b ON b.bill_id=s.bill_id WHERE s.member_id=? AND s.role='lead' ORDER BY b.propose_dt DESC LIMIT 15""",
        (member_id,))]
    d["metrics"] = (jload(METRICS_JSON / "members.json", {}) or {}).get("members", {}).get(member_id)
    try:
        from news import facts_for
        d["news"] = facts_for(member_id, 15)
    except Exception:
        d["news"] = []
    d["sources"] = ["열린국회정보 국회의원 인적사항(nwvrqwxyaytdsfvhu)", "국회의원 발의법률안(nzmimeepazxkubdpn)",
                    "국회의원 본회의 표결정보(nojepdqqaweusdfbi)", "네이버 뉴스 검색 API(보도 항목)"]
    return d


@app.get("/api/committees")
def committees():
    c = con()
    out: dict = {}
    for r in c.execute("SELECT committee, member_id, name, role FROM committee_roles"):
        out.setdefault(r["committee"], []).append(dict(r))
    if not out:  # 위원회 명단 API 확인 전: 인적사항의 소속위원회 문자열
        for r in c.execute("SELECT member_id, name, committees FROM members WHERE committees IS NOT NULL"):
            for cm in [x.strip() for x in r["committees"].split(",") if x.strip()]:
                out.setdefault(cm, []).append({"member_id": r["member_id"], "name": r["name"], "role": "위원"})
    return out


@app.get("/api/network")
def network(min_w: int = 3, cross_only: bool = False):
    d = jload(METRICS_JSON / "network.json", {"as_of": None, "edges": []})
    e = [x for x in d["edges"] if x["w"] >= min_w and (x["cross_party"] or not cross_only)]
    return {"as_of": d["as_of"], "edges": e[:3000], "n_total": len(d["edges"]), "label": "기록"}


@app.get("/api/bills")
def bills(q: str = "", limit: int = 30):
    c = con()
    rows = c.execute(
        """SELECT bill_id, bill_no, bill_name, proposer, propose_dt, committee, stage, proc_result, detail_link
           FROM bills WHERE bill_name LIKE ? ORDER BY propose_dt DESC LIMIT ?""", (f"%{q}%", min(limit, 200))).fetchall()
    return [dict(r) for r in rows]


@app.get("/api/precedents")
def precedents():
    return jload(METRICS_JSON / "precedents.json", {"as_of": None, "by_committee": {}})


@app.get("/api/rules")
def rules():
    return {"institutional": jload(DATA / "rules_institutional.json"), "heuristic": jload(DATA / "rules_heuristic.json")}


class Heuristic(BaseModel):
    rule: str
    source: str
    note: str = ""


@app.post("/api/rules/heuristic")
def add_heuristic(h: Heuristic):
    if not h.rule.strip() or not h.source.strip():
        raise HTTPException(400, "규칙과 출처(직급·경력)는 필수")
    p = DATA / "rules_heuristic.json"
    d = jload(p)
    nums = [int(r["id"][1:]) for r in d["rules"] if r["id"][1:].isdigit()]
    new = {"id": f"H{max(nums, default=0) + 1}", "rule": h.rule.strip(), "source": h.source.strip(),
           "note": h.note.strip(), "status": "가설", "test": None, "evidence": None, "added_at": date.today().isoformat()}
    d["rules"].append(new)
    p.write_text(json.dumps(d, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return new


@app.get("/api/government")
def government():
    return jload(DATA / "government.json", {})


@app.get("/api/groups")
def groups():
    return list(csv.DictReader((DATA / "groups.csv").open(encoding="utf-8")))


@app.get("/api/alerts")
def alerts(on: str | None = None):
    try:
        from news import alerts as a
        return a(on)
    except Exception as e:
        return {"error": str(e)}


class JudgeReq(BaseModel):
    bill_id: str | None = None
    title: str | None = None
    committee: str | None = None
    summary: str | None = None
    use_ai: bool = True


@app.post("/api/judge")
def judge(r: JudgeReq):
    if not (r.bill_id or r.title):
        raise HTTPException(400, "법안 ID나 사안 제목이 필요")
    return engine.judge(r.model_dump(), use_ai=r.use_ai)


class NewGame(BaseModel):
    bill_id: str | None = None
    title: str = "사안"
    committee: str | None = None
    player: str
    actors: list[dict]
    coalitions: dict | None = None
    turn_days: int = 7


@app.post("/api/wargame")
def wargame_new(r: NewGame):
    c = con()
    on = date.today().isoformat()
    s = seats_on(c, on)
    title, cmt, stage = r.title, r.committee, "소관위 심사"
    if r.bill_id:
        b = c.execute("SELECT * FROM bills WHERE bill_id=?", (r.bill_id,)).fetchone()
        if b:
            title, cmt, stage = b["bill_name"], b["committee"], b["stage"]
    comp: dict = {}
    if cmt:
        pm = engine.current_party_map(c, on)
        for m in engine.committee_members(c, cmt, on):
            p = pm.get(m["member_id"], "미확인")
            comp[p] = comp.get(p, 0) + 1
    g = wargame.new_game(s["by_party"], s["total"], {"name": title, "committee": cmt, "stage": stage},
                         r.actors, r.player, comp, r.coalitions, r.turn_days, on)
    GAMES.mkdir(parents=True, exist_ok=True)
    (GAMES / f"{g['run_id']}.json").write_text(json.dumps(g, ensure_ascii=False), encoding="utf-8")
    return g


class Turn(BaseModel):
    move: dict
    use_ai: bool = True


@app.post("/api/wargame/{run_id}/turn")
def wargame_turn(run_id: str, t: Turn):
    p = GAMES / f"{run_id}.json"
    if not p.exists() or not run_id.isalnum():
        raise HTTPException(404, "게임 없음")
    g = json.loads(p.read_text(encoding="utf-8"))
    r = wargame.play_turn(g, t.move, use_ai=t.use_ai)
    p.write_text(json.dumps(r["game"], ensure_ascii=False), encoding="utf-8")
    return r


@app.post("/api/check")
def check_move(body: dict):
    return moves.check(body["state"], body["move"])


@app.get("/api/predictions")
def predictions():
    from predictions import pconnect
    pc = pconnect()
    rows = [dict(r) for r in pc.execute("SELECT * FROM predictions ORDER BY id DESC LIMIT 500")]
    scored = [r for r in rows if r["kind"] == "pass" and r["score"] is not None]
    by_src: dict = {}
    for r in scored:
        b = by_src.setdefault(r["source"], {"n": 0, "brier_sum": 0.0, "hits": 0})
        b["n"] += 1
        b["brier_sum"] += r["score"]
        b["hits"] += r["score"] < 0.25  # 0.5 기준으로 맞힘
    summary = {k: {"n": v["n"], "brier": round(v["brier_sum"] / v["n"], 4), "hit_rate": round(v["hits"] / v["n"], 4)}
               for k, v in by_src.items()}
    return {"summary": summary, "rows": rows}


@app.get("/api/backtest", response_class=PlainTextResponse)
def backtest_report():
    p = DOCS / "backtest.md"
    return p.read_text(encoding="utf-8") if p.exists() else "역검증 리포트가 아직 없습니다. python src/predictions.py backtest"


@app.get("/api/usage")
def usage():
    from llm import usage_summary
    return usage_summary()
