"""7단계 판단 엔진.

흐름: 사안 입력 → 근거 묶음 만들기(코드) → AI 판단(근거 번호 인용 강제) → 인용 검사 → 의원 단위 표 예상(코드)
      → 캐스팅보트·처리 경로(코드, 규칙집) → 예측 기록

근거 표식: 기록(공식 데이터) / 보도(뉴스) / 규칙(제도) / 선례(과거 통계) / AI 추정
AI가 정당 입장을 판단하지 못하거나 API 키가 없으면, 발의자 구성으로 만든 기본값을 쓰고 '근거 약함'으로 표시한다.
"""
import json
import re
import sys
import uuid
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from config import DATA, METRICS_JSON, TOTAL_SEATS
from db import connect, seats_on

LABELS = ("기록", "보도", "규칙", "선례", "AI 추정")


class Bundle:
    def __init__(self):
        self.items: list[dict] = []

    def add(self, label: str, text: str, link: str | None = None, data=None) -> str:
        assert label in LABELS
        ref = f"E{len(self.items) + 1}"
        self.items.append({"ref": ref, "label": label, "text": text, "link": link, "data": data})
        return ref

    def refs(self) -> set[str]:
        return {i["ref"] for i in self.items}

    def as_prompt(self) -> str:
        return "\n".join(f"[{i['ref']}] ({i['label']}) {i['text']}" + (f" <{i['link']}>" if i["link"] else "")
                         for i in self.items)


def law_base(name: str) -> str:
    return re.sub(r"\s*(일부|전부)?개정법률안.*$|\s*법률안.*$|\(.*\)$", "", name or "").strip()


def committee_members(con, committee: str, on: str) -> list[dict]:
    rows = con.execute(
        """SELECT member_id, name, role FROM committee_roles WHERE committee=?
           AND (start_date IS NULL OR start_date<=?) AND (end_date IS NULL OR end_date>?)""",
        (committee, on, on)).fetchall()
    if rows:
        return [dict(r) for r in rows]
    # 위원회 명단 API가 없을 때: 의원 인적사항의 소속위원회 문자열로 대체(현재 시점만 정확)
    out = []
    for r in con.execute("SELECT member_id, name, committees FROM members WHERE committees LIKE ?", (f"%{committee}%",)):
        out.append({"member_id": r["member_id"], "name": r["name"], "role": "위원(인적사항 기준)"})
    return out


def current_party_map(con, on: str) -> dict[str, str]:
    return {r[0]: r[1] for r in con.execute(
        """SELECT p.member_id, p.party FROM party_affiliations p JOIN member_terms t ON t.member_id=p.member_id
           WHERE p.start_date<=? AND (p.end_date IS NULL OR p.end_date>?)
           AND t.start_date<=? AND (t.end_date IS NULL OR t.end_date>?)""", (on, on, on, on))}


def load_member_metrics() -> dict:
    p = METRICS_JSON / "members.json"
    return json.loads(p.read_text(encoding="utf-8"))["members"] if p.exists() else {}


def load_precedents() -> dict:
    p = METRICS_JSON / "precedents.json"
    return json.loads(p.read_text(encoding="utf-8")) if p.exists() else {"by_committee": {}}


def load_rules() -> list[dict]:
    return json.loads((DATA / "rules_institutional.json").read_text(encoding="utf-8"))["rules"]


def build_bundle(con, issue: dict, on: str) -> tuple[Bundle, dict]:
    """issue: {"bill_id"} 또는 {"title","committee","summary"}"""
    B = Bundle()
    ctx: dict = {"on": on}
    bill = None
    if issue.get("bill_id"):
        bill = con.execute("SELECT * FROM bills WHERE bill_id=?", (issue["bill_id"],)).fetchone()
    title = bill["bill_name"] if bill else issue.get("title", "")
    committee = (bill["committee"] if bill else None) or issue.get("committee")
    ctx.update(title=title, committee=committee, bill=dict(bill) if bill else None)

    seats = seats_on(con, on)
    ctx["seats"] = seats
    B.add("기록", f"{on} 기준 재적 {seats['total']}명, 정당별 의석 {seats['by_party']}"
          + (f", 당적 미확인 {len(seats['unknown_party'])}명" if seats["unknown_party"] else ""),
          data=seats)
    if bill:
        sp = con.execute("SELECT name, member_id, role FROM bill_sponsors WHERE bill_id=?", (bill["bill_id"],)).fetchall()
        pm = current_party_map(con, on)
        lead = [s["name"] for s in sp if s["role"] == "lead"]
        parties = {}
        for s in sp:
            p = pm.get(s["member_id"], "미확인")
            parties[p] = parties.get(p, 0) + 1
        ctx["sponsor_parties"] = parties
        ctx["lead_party"] = next((pm.get(s["member_id"]) for s in sp if s["role"] == "lead"), None)
        B.add("기록", f"'{title}' 대표발의 {', '.join(lead) or '미상'}, 발의자 {len(sp)}명의 정당 분포 {parties}, "
              f"현재 단계 {bill['stage']}, 소관위 {committee}", bill["detail_link"])
    if committee:
        cm = committee_members(con, committee, on)
        pm = current_party_map(con, on)
        comp: dict = {}
        for m in cm:
            comp[pm.get(m["member_id"], "미확인")] = comp.get(pm.get(m["member_id"], "미확인"), 0) + 1
        ctx["committee_members"] = cm
        ctx["committee_comp"] = comp
        chair = [m["name"] for m in cm if m["role"] == "위원장"]
        B.add("기록", f"{committee} 위원 {len(cm)}명 정당 분포 {comp}" + (f", 위원장 {chair[0]}" if chair else ""))
        from metrics import precedent_stats
        prec = precedent_stats(con, on).get(committee)
        if prec:
            B.add("선례", f"{committee} 22대 발의 법안 {prec['n_bills']}건 중 가결 {prec['n_passed']}건"
                  f"(통과율 {prec['pass_rate']}), 계류율 {prec['pending_rate']}, 법사위 단계 정체율 "
                  f"{prec['stalled_at_judiciary_rate']}, 대안반영폐기율 {prec['alt_reflected_rate']}, "
                  f"가결까지 중앙값 {prec['median_days_to_plenary']}일(n={prec['n_with_duration']})", data=prec)
        from metrics import precedent_by_period
        for pname, pd in precedent_by_period(con, on).items():
            pc = pd["by_committee"].get(committee)
            if pc and pc["n_bills"]:
                B.add("선례", f"[{pname} 시기({pd['start']}~{pd['end'] or '현재'}) 발의분] {committee} {pc['n_bills']}건 중 "
                      f"가결 {pc['n_passed']}건(통과율 {pc['pass_rate']}), 계류율 {pc['pending_rate']}, "
                      f"가결까지 중앙값 {pc['median_days_to_plenary']}일 — 여야가 바뀌었으므로 현재 시기 통계를 우선 참고",
                      data={"period": pname, **pc})
    base = law_base(title)
    if base:
        like = (f"{base} %", f"{base}(%", base)
        where = "(bill_name LIKE ? OR bill_name LIKE ? OR bill_name = ?) AND bill_id != ?"
        args = (*like, issue.get("bill_id", ""))
        n_all = con.execute(f"SELECT COUNT(*) FROM bills WHERE {where}", args).fetchone()[0]
        res = dict(con.execute(f"SELECT proc_result, COUNT(*) FROM bills WHERE {where} AND proc_result IS NOT NULL "
                               "GROUP BY proc_result", args).fetchall())
        if n_all:
            B.add("선례", f"같은 법률('{base}')을 고치는 22대 법안 {n_all}건, 처리된 {sum(res.values())}건의 결과 {res}")
        # 같은 법률 개정안의 과거 본회의 표결: 정당별(표결일 기준 당적) 찬반
        from db import party_lookup
        party_at = party_lookup(con)
        past = con.execute(
            """SELECT bill_id, bill_name, vote_date, yes, no, abstain FROM votes
               WHERE (bill_name LIKE ? OR bill_name LIKE ?) AND vote_date < ? ORDER BY vote_date DESC LIMIT 5""",
            (f"{base} %", f"{base}(%", on)).fetchall()
        for v in past:
            tally: dict = {}
            for mv in con.execute("SELECT member_id, vote FROM member_votes WHERE bill_id=? AND vote IN ('찬성','반대','기권')",
                                  (v["bill_id"],)):
                p = party_at(mv["member_id"], v["vote_date"]) or "미확인"
                t = tally.setdefault(p, {"찬성": 0, "반대": 0, "기권": 0})
                t[mv["vote"]] += 1
            brief = ", ".join(f"{p} 찬{t['찬성']}/반{t['반대']}/기{t['기권']}" for p, t in
                              sorted(tally.items(), key=lambda x: -sum(x[1].values())))
            B.add("기록", f"[과거 표결] {v['vote_date']} '{v['bill_name']}' 찬성 {v['yes']} 반대 {v['no']} 기권 {v['abstain']} "
                  f"— 정당별: {brief}", data={"bill_id": v["bill_id"], "by_party": tally})
    # 위원장 대안이면: 대안에 반영된 원래 법안들과 그 발의자 정당
    if bill and (bill["proposer_kind"] == "위원장" or "(대안)" in (bill["bill_name"] or "")) and base:
        src = con.execute(
            """SELECT bill_id, bill_name, proposer FROM bills
               WHERE (bill_name LIKE ? OR bill_name = ?) AND proc_result LIKE '대안반영%' AND committee = ?
                 AND cmt_proc_dt BETWEEN date(?, '-14 days') AND date(?, '+1 days')""",
            (f"{base}%", base, committee, bill["propose_dt"], bill["propose_dt"])).fetchall()
        if src:
            pm = current_party_map(con, on)
            parties: dict = {}
            leads = []
            for sb in src:
                for sp in con.execute("SELECT member_id, name, role FROM bill_sponsors WHERE bill_id=?", (sb["bill_id"],)):
                    p = pm.get(sp["member_id"], "미확인")
                    parties[p] = parties.get(p, 0) + 1
                    if sp["role"] == "lead":
                        leads.append(f"{sp['name']}({p})")
            ctx["sponsor_parties"] = parties
            if not ctx.get("lead_party") and leads:
                ctx["lead_party"] = max(parties, key=parties.get)
            B.add("기록", f"이 대안에 반영된 원래 법안 {len(src)}건(같은 위원회, 위원회 처리일 기준 추정 연결). "
                  f"대표발의 {', '.join(leads[:8])}; 발의자 정당 분포(중복 포함) {parties}",
                  data=[dict(x) for x in src])
    rules = load_rules()
    for r in rules:
        if r["id"] in ("R1", "R3", "R4", "R5", "R6", "R8", "R9", "R19"):
            st = r.get("verification", {}).get("status", "미검증")
            B.add("규칙", f"{r['id']} {r['title']}: {r['rule']} [근거 {', '.join(b['law'] + ' ' + b['article'] for b in r['basis'])}, {st}]")
    try:
        from news import facts_for
        names = {m["member_id"]: m["name"] for m in ctx.get("committee_members", [])}
        for mid, nm in list(names.items())[:40]:
            for f in facts_for(mid, limit=3):
                B.add("보도", f"{nm}: [{f['category']}] {f['summary']} ({f['pub_date']}, {f['press_domain']})", f["url"])
    except Exception:
        pass
    return B, ctx


JUDGE_SYSTEM = """너는 한국 국회 정무 분석관이다. 아래 근거 목록 [E번호] 안의 정보만으로 판단한다.
규칙:
- 모든 판단 문장에 사용한 근거 번호를 refs 에 단다. 근거 목록에 없는 사실·수치·발언을 만들지 않는다.
- 근거가 부족하면 그렇다고 쓰고 refs 를 비운다(화면에 '근거 약함'으로 표시된다).
- 특정 정당에 유리하게 쓰지 않는다. 어느 관점에서 보든 같은 기준으로 판단한다.
- party_stances 의 stance 는 찬성/반대/유동 중 하나.
  · 이 법안에 대한 직접 근거(당론 보도, 발의자 구성)가 있으면 그것으로 정한다.
  · 직접 근거가 없어도 같은 법률 개정안의 과거 본회의 표결에서 그 정당이 일관되게(예: 90% 이상) 한쪽으로 표결했다면
    그 방향으로 추정할 수 있다. 이때 reason 을 '간접 근거:'로 시작하고 근거 번호를 단다.
  · 과거 표결이 엇갈리거나 근거가 전혀 없으면 유동으로 두고, 근거가 없을 때는 refs 를 비운다."""

JUDGE_SCHEMA = {
    "type": "object", "additionalProperties": False,
    "required": ["party_stances", "judgments", "path_risks", "pass_prob", "pass_prob_refs"],
    "properties": {
        "party_stances": {"type": "array", "items": {"type": "object", "additionalProperties": False,
            "required": ["party", "stance", "reason", "refs"],
            "properties": {"party": {"type": "string"}, "stance": {"type": "string", "enum": ["찬성", "반대", "유동"]},
                           "reason": {"type": "string"}, "refs": {"type": "array", "items": {"type": "string"}}}}},
        "judgments": {"type": "array", "items": {"type": "object", "additionalProperties": False,
            "required": ["text", "refs"],
            "properties": {"text": {"type": "string"}, "refs": {"type": "array", "items": {"type": "string"}}}}},
        "path_risks": {"type": "array", "items": {"type": "object", "additionalProperties": False,
            "required": ["stage", "risk", "refs"],
            "properties": {"stage": {"type": "string"}, "risk": {"type": "string"},
                           "refs": {"type": "array", "items": {"type": "string"}}}}},
        "pass_prob": {"type": "number"},
        "pass_prob_refs": {"type": "array", "items": {"type": "string"}},
    },
}


def check_refs(items: list[dict], valid: set[str]) -> list[dict]:
    for it in items:
        refs = [r for r in it.get("refs", []) if r in valid]
        bad = [r for r in it.get("refs", []) if r not in valid]
        it["refs"] = refs
        it["label"] = "AI 추정"
        it["weak"] = not refs
        if bad:
            it["invalid_refs"] = bad
    return items


def default_stances(ctx: dict) -> list[dict]:
    """AI 없이: 대표발의자 정당=찬성, 나머지=유동. 근거 약함."""
    out = []
    for p in ctx["seats"]["by_party"]:
        st = "찬성" if p == ctx.get("lead_party") else "유동"
        out.append({"party": p, "stance": st, "reason": "대표발의자 소속 정당" if st == "찬성" else "입장 근거 없음",
                    "refs": [], "label": "기본값", "weak": True})
    return out


def member_forecast(con, ctx: dict, stances: list[dict], metrics: dict) -> list[dict]:
    on = ctx["on"]
    pm = current_party_map(con, on)
    st = {s["party"]: s for s in stances}
    cm_ids = {m["member_id"] for m in ctx.get("committee_members", [])}
    names = {r[0]: (r[1], r[2]) for r in con.execute("SELECT member_id, name, district FROM members")}
    out = []
    for mid, party in pm.items():
        m = metrics.get(mid, {})
        s = st.get(party, {"stance": "유동", "weak": True})
        dr = m.get("defection_rate")
        reasons = [f"당론 추정: {party} {s['stance']}" + (" (근거 약함)" if s.get("weak") else "")]
        call = s["stance"]
        if dr is not None:
            reasons.append(f"이탈률 {dr:.1%} (표결 {m.get('n_party_line')}건 기준, 기록)")
            if call != "유동" and dr >= 0.10:
                call = "유동"
                reasons.append("이탈률 10% 이상이라 유동으로 분류")
        else:
            reasons.append("이탈률 데이터 없음")
        if mid in cm_ids:
            reasons.append("소관위 위원(기록)")
        out.append({"member_id": mid, "name": names.get(mid, (None,))[0], "party": party,
                    "district": names.get(mid, (None, None))[1], "forecast": call,
                    "defection_rate": dr, "reasons": reasons, "label": "AI 추정" if not s.get("weak") else "근거 약함"})
    return out


def casting_votes(fc: list[dict], total: int) -> dict:
    need = total // 2 + 1  # 전원 출석 가정 시 가결선(과반)
    yes = sum(1 for f in fc if f["forecast"] == "찬성")
    no = sum(1 for f in fc if f["forecast"] == "반대")
    swing = [f for f in fc if f["forecast"] == "유동"]
    gap = need - yes
    swing.sort(key=lambda f: -(f["defection_rate"] or 0))
    return {"need_for_majority": need, "yes": yes, "no": no, "swing": len(swing), "gap": gap,
            "casting": swing[: max(10, min(30, abs(gap) + 10))] if swing else [],
            "note": "전원 출석 가정. 실제 의결은 출석 과반이므로 불참에 따라 달라진다."}


def process_path(ctx: dict, stances: list[dict]) -> list[dict]:
    from moves import check
    seats = ctx["seats"]["by_party"]
    yes_parties = [s["party"] for s in stances if s["stance"] == "찬성"]
    state = {"total": ctx["seats"]["total"], "seats": seats,
             "committees": {ctx["committee"]: {**ctx.get("committee_comp", {}), "total": sum(ctx.get("committee_comp", {}).values())}}
             if ctx.get("committee") else {},
             "bills": {"X": {"stage": (ctx.get("bill") or {}).get("stage") or "소관위 심사", "committee": ctx.get("committee")}}}
    steps = [{"step": "소관위 심사·의결", "rule": "R3", "label": "규칙"},
             {"step": "법사위 체계·자구 심사(60일 넘기면 R6 부의 요구 가능)", "rule": "R6", "label": "규칙"},
             {"step": "본회의 의결", "rule": "R1", "label": "규칙"},
             {"step": "정부 이송 15일 내 공포 또는 재의요구", "rule": "R9", "label": "규칙"}]
    ft = check(state, {"type": "fast_track", "bill": "X", "supporters": yes_parties})
    steps.insert(0, {"step": "신속처리안건 지정 가능성", "rule": "R4", "label": "규칙",
                     "check": ft, "supporters": yes_parties})
    return steps


def judge(issue: dict, on: str | None = None, use_ai: bool = True, record_prediction: bool = True,
          con=None, metrics: dict | None = None) -> dict:
    on = on or date.today().isoformat()
    con = con or connect()
    B, ctx = build_bundle(con, issue, on)
    run_id = uuid.uuid4().hex[:12]
    ai = None
    ai_error = None
    if use_ai:
        try:
            from llm import call_json
            prompt = (f"사안: {ctx['title']}\n소관위원회: {ctx['committee']}\n추가 설명: {issue.get('summary', '')}\n\n"
                      f"근거 목록:\n{B.as_prompt()}\n\n정당 목록: {list(ctx['seats']['by_party'])}")
            ai = call_json(JUDGE_SYSTEM, prompt, JUDGE_SCHEMA, purpose="judge", run_id=run_id)
        except Exception as e:
            ai_error = str(e)
    valid = B.refs()
    if ai:
        stances = check_refs(ai["party_stances"], valid)
        judgments = check_refs(ai["judgments"], valid)
        risks = check_refs(ai["path_risks"], valid)
        pass_prob = max(0.0, min(1.0, float(ai["pass_prob"])))
        pp_refs = [r for r in ai["pass_prob_refs"] if r in valid]
    else:
        stances, judgments, risks = default_stances(ctx), [], []
        # 현재 정부 시기 통계가 있으면 그것을, 없으면 22대 전체 통계를 쓴다
        precs = [i for i in B.items if i["label"] == "선례" and isinstance(i["data"], dict)
                 and i["data"].get("pass_rate") is not None]
        cur = [i for i in precs if "period" in i["data"] and i["data"].get("n_decided", 0) >= 10]
        pick = (cur or precs)[-1] if (cur or precs) else None
        pass_prob = pick["data"]["pass_rate"] if pick else None
        pp_refs = [pick["ref"]] if pick else []
    fc = member_forecast(con, ctx, stances, metrics if metrics is not None else load_member_metrics())
    cv = casting_votes(fc, ctx["seats"]["total"] or TOTAL_SEATS)
    path = process_path(ctx, stances)
    out = {"run_id": run_id, "on": on, "issue": issue, "title": ctx["title"], "committee": ctx["committee"],
           "evidence": B.items, "party_stances": stances, "judgments": judgments, "path_risks": risks,
           "pass_prob": pass_prob, "pass_prob_refs": pp_refs, "pass_prob_weak": not pp_refs,
           "member_forecast": fc, "casting": cv, "path": path,
           "ai_used": bool(ai), "ai_error": ai_error, "simulation_label": "AI 추정"}
    if record_prediction and issue.get("bill_id") and pass_prob is not None:
        from predictions import record
        record("pass", {"pass_prob": pass_prob}, bill_id=issue["bill_id"], subject=ctx["title"],
               basis=pp_refs, source="engine")
        record("vote_count", {"yes": cv["yes"]}, bill_id=issue["bill_id"], subject=ctx["title"], source="engine")
    return out


if __name__ == "__main__":
    import argparse
    ap = argparse.ArgumentParser()
    ap.add_argument("--bill-id")
    ap.add_argument("--title")
    ap.add_argument("--committee")
    ap.add_argument("--no-ai", action="store_true")
    a = ap.parse_args()
    r = judge({"bill_id": a.bill_id, "title": a.title, "committee": a.committee}, use_ai=not a.no_ai)
    print(json.dumps({k: r[k] for k in ("title", "pass_prob", "casting", "ai_used", "ai_error")}, ensure_ascii=False, indent=1, default=str))
