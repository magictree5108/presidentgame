"""워게임 수(move)의 제도상 가능 여부 검사.

규칙과 정족수는 data/rules_institutional.json 의 threshold/params 에서 읽는다(숫자를 코드에 박지 않는다).
수를 둔 세력이 '확보했다고 선언한 지지 정당(supporters)'의 의석만으로 서명·발의·의결 정족수를
채울 수 있는지 본다. 못 채우면 그 수는 막고 이유와 부족한 의석수를 돌려준다.

상태(state) 예:
{
  "total": 300,                         # 재적(현재 의원 수)
  "seats": {"A당": 170, "B당": 108, ...},
  "committees": {"법제사법위원회": {"A당": 10, "B당": 7, "total": 18}},
  "bills": {"B1": {"stage": "소관위 심사", "committee": "법제사법위원회", "fast_track": false,
                   "mediated": false, "days_in_judiciary": 0, "vetoed": false}},
  "filibuster": {"B1": {"active": true, "cloture_filed_hours_ago": 30}},
  "speaker_conditions": [],            # "천재지변"/"국가비상사태"/"교섭단체 대표 합의"
}
수 예: {"actor": "A당", "type": "fast_track", "bill": "B1", "supporters": ["A당", "C당"], "route": "plenary"}
"""
import json
import math
from dataclasses import dataclass, field

from config import DATA

_RULES = None


def rules() -> dict:
    global _RULES
    if _RULES is None:
        data = json.loads((DATA / "rules_institutional.json").read_text(encoding="utf-8"))
        _RULES = {r["move"]: r for r in data["rules"] if r.get("move")}
        _RULES["_by_id"] = {r["id"]: r for r in data["rules"]}
    return _RULES


def need(t: dict, base_count: int) -> int:
    """정족수 정의(t)와 기준 인원으로 필요한 최소 인원."""
    x = base_count * t["num"] / t["den"]
    if t.get("strict"):  # '과반수' = 초과
        return math.floor(x) + 1
    return math.ceil(x)  # '이상'


@dataclass
class Verdict:
    allowed: bool
    rule_id: str | None
    reason: str
    checks: list = field(default_factory=list)  # [{"what","need","have","ok"}]

    def to_dict(self):
        return {"allowed": self.allowed, "rule_id": self.rule_id, "reason": self.reason, "checks": self.checks}


def _sum(seats: dict, parties) -> int:
    return sum(seats.get(p, 0) for p in parties)


def _check(checks, what, t, base, have):
    n = need(t, base)
    ok = have >= n
    checks.append({"what": what, "need": n, "have": have, "ok": ok,
                   "rule": f"{base}명의 {t['num']}/{t['den']} {'초과' if t.get('strict') else '이상'}"})
    return ok


def check_move(state: dict, move: dict) -> Verdict:
    R = rules()
    mtype = move.get("type")
    seats = state["seats"]
    total = state["total"]
    sup = move.get("supporters") or [move.get("actor")]
    have = _sum(seats, sup)
    bill = state.get("bills", {}).get(move.get("bill"), {}) if move.get("bill") else {}
    checks: list = []

    def verdict(ok, rule, why_ok, why_no):
        rid = rule["id"] if rule else None
        return Verdict(ok, rid, why_ok if ok else why_no, checks)

    if mtype in ("speech", "negotiate", "press", "pass", "public_campaign"):
        return Verdict(True, None, "제도 제한이 없는 정치 행위", [])

    if mtype not in R:
        return Verdict(False, None, f"규칙집에 없는 수 유형: {mtype}", [])
    rule = R[mtype]
    th = rule.get("threshold", {})

    if mtype == "plenary_pass":
        ok = _check(checks, "출석(지지 세력만으로)", th["attendance"], total, have)
        # 의결은 출석 기준이므로 전원 출석을 가정한 최소 확보 의석으로 본다
        ok_vote = _check(checks, "찬성(전원 출석 가정)", th["approve"], total, have)
        return Verdict(True, rule["id"],
                       "가능. 지지 세력만으로 가결 가능" if ok and ok_vote
                       else "제안은 가능하나 지지 세력만으로는 가결 의석 부족(설득 필요)", checks)

    if mtype == "committee_pass":
        c = state.get("committees", {}).get(move.get("committee") or bill.get("committee"))
        if not c:
            return Verdict(False, rule["id"], "위원회 구성 정보가 없어 판단 불가", [])
        ok = _check(checks, "위원회 찬성(전원 출석 가정)", th["approve"], c["total"], _sum(c, sup))
        return Verdict(True, rule["id"], "가능" if ok else "상정은 가능하나 지지 위원만으로는 부족", checks)

    if mtype == "fast_track":
        if bill.get("fast_track"):
            return Verdict(False, rule["id"], "이미 신속처리대상안건으로 지정됨", [])
        if bill and bill.get("stage") not in ("소관위 심사", "법사위 심사"):
            return Verdict(False, rule["id"], "위원회에 회부된 안건만 지정 가능(국회법 제85조의2 ①)", [])
        if move.get("route", "plenary") == "committee":
            c = state.get("committees", {}).get(bill.get("committee") or move.get("committee"))
            if not c:
                return Verdict(False, rule["id"], "위원회 구성 정보가 없어 판단 불가", [])
            h = _sum(c, sup)
            ok = _check(checks, "소관위 서명", th["committee_sign"], c["total"], h)
            ok = _check(checks, "소관위 찬성", th["committee_approve"], c["total"], h) and ok
        else:
            ok = _check(checks, "지정동의 서명", th["sign"], total, have)
            ok = _check(checks, "본회의 찬성(무기명)", th["approve"], total, have) and ok
        return verdict(ok, rule, "가능", "불가: 지지 세력 의석이 신속처리 지정 정족수(5분의 3)에 못 미침")

    if mtype == "judiciary_bypass":
        p = rule["params"]
        days = bill.get("days_in_judiciary", 0)
        checks.append({"what": "법사위 회부 후 경과일", "need": p["wait_days"], "have": days, "ok": days >= p["wait_days"]})
        if days < p["wait_days"]:
            return Verdict(False, rule["id"], f"불가: 법사위 회부 후 {p['wait_days']}일이 지나지 않음", checks)
        c = state.get("committees", {}).get(bill.get("committee"))
        if c and move.get("objection", True):
            ok = _check(checks, "소관위 찬성(이의 있을 때)", th["committee_approve"], c["total"], _sum(c, sup))
            return verdict(ok, rule, "가능", "불가: 소관위 5분의 3 찬성 부족")
        return Verdict(True, rule["id"], "가능(이의 없음 가정)", checks)

    if mtype == "speaker_deadline":
        conds = set(state.get("speaker_conditions", []))
        ok = bool(conds & set(rule["conditions"]))
        checks.append({"what": "직권상정 요건", "need": " / ".join(rule["conditions"]), "have": ", ".join(conds) or "없음", "ok": ok})
        if move.get("actor_role") not in (None, "의장"):
            return Verdict(False, rule["id"], "불가: 심사기간 지정은 의장만 할 수 있음", checks)
        return verdict(ok, rule, "가능", "불가: 천재지변·국가비상사태·교섭단체 대표 합의 중 어느 것도 없음")

    if mtype == "filibuster":
        if move.get("action", "start") == "start":
            fb = state.get("filibuster", {}).get(move.get("bill"), {})
            if fb.get("ended"):
                return Verdict(False, rule["id"], "불가: 종결 선포된 안건은 다시 무제한토론 요구 불가(제106조의2 ⑨)", [])
            ok = _check(checks, "요구서 서명", th["sign"], total, have)
            return verdict(ok, rule, "가능", "불가: 재적 3분의 1 서명 부족")
        if not state.get("filibuster", {}).get(move.get("bill"), {}).get("active"):
            return Verdict(False, rule["id"], "불가: 진행 중인 무제한토론이 없음", [])
        if move["action"] == "cloture_file":
            ok = _check(checks, "종결동의 서명", th["cloture_sign"], total, have)
            return verdict(ok, rule, "가능(24시간 후 표결)", "불가: 재적 3분의 1 서명 부족")
        if move["action"] == "cloture_vote":
            hrs = state.get("filibuster", {}).get(move.get("bill"), {}).get("cloture_filed_hours_ago")
            if hrs is None or hrs < 24:
                checks.append({"what": "종결동의 제출 후 경과 시간", "need": 24, "have": hrs or 0, "ok": False})
                return Verdict(False, rule["id"], "불가: 종결동의 제출 후 24시간이 지나야 표결", checks)
            ok = _check(checks, "종결 찬성(무기명)", th["cloture"], total, have)
            return verdict(ok, rule, "가능", "불가: 재적 5분의 3 찬성 부족")

    if mtype == "override_veto":
        if not bill.get("vetoed"):
            return Verdict(False, rule["id"], "불가: 재의요구된 법률안이 아님", [])
        ok = _check(checks, "재의결 찬성(전원 출석 가정)", th["approve"], total, have)
        return verdict(ok, rule, "가능", "불가: 지지 세력만으로 출석 3분의 2 찬성 확보 불가")

    if mtype == "veto":  # 규칙집 move 키가 없으므로 위에서 걸리지 않음 — 아래 별도 처리
        pass

    if mtype == "impeach":
        pres = move.get("target_role") == "대통령"
        pk, ak = ("president_propose", "president_approve") if pres else ("propose", "approve")
        ok = _check(checks, "발의", th[pk], total, have)
        okv = _check(checks, "의결 찬성", th[ak], total, have)
        if not ok:
            return Verdict(False, rule["id"], "불가: 탄핵소추 발의 정족수 부족", checks)
        return Verdict(True, rule["id"], "가능" if okv else "발의는 가능하나 지지 세력만으로는 의결 정족수 부족", checks)

    if mtype in ("dismissal_motion", "constitutional_amendment"):
        ok = _check(checks, "발의", th["propose"], total, have)
        okv = _check(checks, "의결 찬성", th["approve"], total, have)
        if not ok:
            return Verdict(False, rule["id"], "불가: 발의 정족수 부족", checks)
        return Verdict(True, rule["id"], "가능" if okv else "발의는 가능하나 지지 세력만으로는 의결 정족수 부족", checks)

    if mtype == "lift_martial_law":
        ok = _check(checks, "해제요구 찬성", th["approve"], total, have)
        return Verdict(True, rule["id"], "가능" if ok else "상정 가능하나 지지 세력만으로는 재적 과반 부족", checks)

    if mtype == "form_negotiating_group":
        n = rule["params"]["min_members"]
        checks.append({"what": "소속 의원", "need": n, "have": have, "ok": have >= n})
        return verdict(have >= n, rule, "가능", f"불가: {n}명 미만")

    if mtype == "mediation_committee":
        if bill.get("mediated"):
            return Verdict(False, rule["id"], "불가: 이미 안건조정위원회를 거친 안건", [])
        if bill.get("stage") == "법사위 심사":
            return Verdict(False, rule["id"], "불가: 체계·자구 심사로 법사위에 회부된 법률안은 제외", [])
        c = state.get("committees", {}).get(bill.get("committee") or move.get("committee"))
        if not c:
            return Verdict(False, rule["id"], "위원회 구성 정보가 없어 판단 불가", [])
        ok = _check(checks, "구성 요구", th["request"], c["total"], _sum(c, sup))
        return verdict(ok, rule, "가능", "불가: 소관위 재적 3분의 1 요구 부족")

    if mtype in ("investigation", "secret_ballot_request"):
        ok = _check(checks, "요구", th["request"], total, have)
        return verdict(ok, rule, "가능", "불가: 요구 정족수 부족")

    return Verdict(False, rule["id"], "검사 로직이 없는 수 유형", [])


def check_veto(state: dict, move: dict) -> Verdict:
    """대통령 재의요구: 정부 이송 후 15일 이내, 전부 거부만 가능."""
    r = rules()["_by_id"]["R9"]
    bill = state.get("bills", {}).get(move.get("bill"), {})
    days = bill.get("days_since_transfer")
    checks = [{"what": "정부 이송 후 경과일", "need": f"≤{r['params']['days']}", "have": days,
               "ok": days is not None and days <= r["params"]["days"]}]
    if move.get("actor_role") != "대통령":
        return Verdict(False, "R9", "불가: 재의요구는 대통령만 가능", checks)
    if bill.get("stage") != "정부이송":
        return Verdict(False, "R9", "불가: 정부로 이송된 법률안이 아님", checks)
    if move.get("partial"):
        return Verdict(False, "R9", "불가: 일부 거부·수정 거부는 헌법상 불가(제53조 ③)", checks)
    if not checks[0]["ok"]:
        return Verdict(False, "R9", "불가: 15일이 지나 법률로 확정됨(제53조 ⑤)", checks)
    return Verdict(True, "R9", "가능", checks)


def check(state: dict, move: dict) -> dict:
    if move.get("type") == "veto":
        return check_veto(state, move).to_dict()
    return check_move(state, move).to_dict()
