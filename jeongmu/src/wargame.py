"""워게임 턴 진행. 모든 결과는 '시뮬레이션'으로 표시된다.

한 턴: 플레이어 수 → 제도 검사(moves.check) → 불가능하면 거부(턴 소모 없음) →
       효과 적용 → 다른 세력의 응수(가능한 수 목록 안에서만; AI 또는 규칙 기반) → 시간 경과

상태는 JSON 하나로 들고 다닌다(서버가 data/wargames/<run_id>.json 에 저장).
"""
import copy
import json
import uuid
from datetime import date

from moves import check, need

TURN_DAYS_DEFAULT = 7

# 행위자별로 고려할 수 있는 수(템플릿). supporters 는 행위자의 연합으로 채운다.
CANDIDATES = {
    "party": [
        {"type": "committee_pass"}, {"type": "fast_track", "route": "plenary"},
        {"type": "fast_track", "route": "committee"}, {"type": "judiciary_bypass"},
        {"type": "mediation_committee"}, {"type": "filibuster", "action": "start"},
        {"type": "filibuster", "action": "cloture_file"}, {"type": "filibuster", "action": "cloture_vote"},
        {"type": "plenary_pass"}, {"type": "override_veto"},
        {"type": "negotiate"}, {"type": "public_campaign"}, {"type": "pass"},
    ],
    "president": [{"type": "veto", "actor_role": "대통령"}, {"type": "press"}, {"type": "pass"}],
    "speaker": [{"type": "speaker_deadline", "actor_role": "의장"}, {"type": "negotiate"}, {"type": "pass"}],
}


def new_game(seats: dict, total: int, bill: dict, actors: list[dict], player: str,
             committee_comp: dict | None = None, coalitions: dict | None = None,
             turn_days: int = TURN_DAYS_DEFAULT, on: str | None = None) -> dict:
    """actors: [{"name":"갑당","kind":"party","stance":"찬성"}, {"name":"대통령","kind":"president","stance":"반대"}, ...]"""
    cmt = bill.get("committee") or "소관위원회"
    return {
        "run_id": uuid.uuid4().hex[:12], "label": "시뮬레이션", "turn": 0, "day": 0, "start": on or date.today().isoformat(),
        "turn_days": turn_days, "player": player, "actors": actors,
        "coalitions": coalitions or {a["name"]: [a["name"]] for a in actors if a["kind"] == "party"},
        "total": total, "seats": seats,
        "committees": {cmt: {**(committee_comp or {}), "total": sum((committee_comp or {}).values())}},
        "bills": {"X": {"name": bill.get("name", "사안"), "stage": bill.get("stage", "소관위 심사"), "committee": cmt,
                        "fast_track": False, "mediated": False, "days_in_judiciary": 0, "vetoed": False,
                        "days_since_transfer": None, "fast_track_day": None, "outcome": None}},
        "filibuster": {}, "speaker_conditions": [], "log": [],
    }


def _support(g, actor):
    return g["coalitions"].get(actor, [actor])


def _seats(g, parties):
    return sum(g["seats"].get(p, 0) for p in parties)


def apply(g: dict, actor: str, move: dict) -> dict:
    """합법성 검사 후 효과 적용. 반환: 로그 항목."""
    move = {**move, "bill": move.get("bill", "X")}
    move.setdefault("supporters", _support(g, actor))
    v = check(g, move)
    entry = {"turn": g["turn"], "day": g["day"], "actor": actor, "move": move, "check": v,
             "label": "시뮬레이션", "effect": None}
    if not v["allowed"]:
        entry["effect"] = "거부됨(제도상 불가)"
        g["log"].append(entry)
        return entry
    b = g["bills"]["X"]
    t = move["type"]
    sup = _seats(g, move["supporters"])
    total = g["total"]
    if t == "committee_pass":
        c = g["committees"][b["committee"]]
        ok = sum(c.get(p, 0) for p in move["supporters"]) >= need({"num": 1, "den": 2, "strict": True}, c["total"])
        if ok and b["stage"] == "소관위 심사":
            b["stage"], b["days_in_judiciary"] = "법사위 심사", 0
            entry["effect"] = "소관위 의결 → 법사위 회부"
        else:
            entry["effect"] = "소관위 의결 실패(지지 위원 부족)" if not ok else "이미 소관위를 지남"
    elif t == "fast_track":
        b["fast_track"], b["fast_track_day"] = True, g["day"]
        entry["effect"] = "신속처리대상안건 지정"
    elif t == "judiciary_bypass":
        b["stage"] = "본회의 대기"
        entry["effect"] = "법사위 지연 → 본회의 부의 요구"
    elif t == "mediation_committee":
        b["mediated"] = True
        entry["effect"] = "안건조정위원회 구성(최장 90일)"
    elif t == "filibuster":
        fb = g["filibuster"].setdefault("X", {})
        a = move.get("action", "start")
        if a == "start":
            fb.update(active=True, cloture_filed_hours_ago=None)
            entry["effect"] = "무제한토론 시작"
        elif a == "cloture_file":
            fb["cloture_filed_hours_ago"] = 0
            entry["effect"] = "종결동의 제출(24시간 뒤 표결 가능)"
        else:
            fb.update(active=False, ended=True)
            entry["effect"] = "무제한토론 종결 → 표결"
    elif t == "plenary_pass":
        if g["filibuster"].get("X", {}).get("active"):
            entry["effect"] = "무제한토론 중이라 표결 불가"
            entry["check"] = {**v, "allowed": False, "reason": "무제한토론 진행 중(종결 전 표결 불가, 국회법 제106조의2)"}
        elif b["stage"] not in ("본회의 대기",) and not (b["fast_track"] and b["stage"] != "정부이송"):
            entry["effect"] = "본회의 부의 전 단계라 표결 불가"
            entry["check"] = {**v, "allowed": False, "reason": f"현재 단계 '{b['stage']}'에서는 본회의 표결 불가"}
        elif sup >= need({"num": 1, "den": 2, "strict": True}, total):
            b["stage"], b["days_since_transfer"] = "정부이송", 0
            entry["effect"] = "본회의 가결 → 정부 이송"
        else:
            b["stage"], b["outcome"] = "부결", "부결"
            entry["effect"] = "본회의 부결"
    elif t == "veto":
        b["vetoed"], b["stage"] = True, "본회의 대기"
        entry["effect"] = "재의요구(국회 환부)"
    elif t == "override_veto":
        if sup >= need({"num": 2, "den": 3}, total):
            b["stage"], b["outcome"] = "법률 확정", "재의결 가결"
            entry["effect"] = "재의결 가결 → 법률 확정"
        else:
            b["stage"], b["outcome"] = "폐기", "재의결 부결"
            entry["effect"] = "재의결 부결 → 폐기"
    elif t == "speaker_deadline":
        b["stage"] = "본회의 대기"
        entry["effect"] = "의장 심사기간 지정 → 본회의 부의"
    else:
        entry["effect"] = "정치 행위(제도상 상태 변화 없음)"
    g["log"].append(entry)
    return entry


def legal_options(g: dict, actor: dict) -> list[dict]:
    out = []
    for c in CANDIDATES.get(actor["kind"], []):
        m = {**c, "bill": "X", "supporters": _support(g, actor["name"])}
        if check(g, m)["allowed"]:
            out.append(c)
    return out


def rule_based_response(g: dict, actor: dict, options: list[dict]) -> dict:
    """AI 없이 쓰는 단순 응수: 반대 세력은 막는 수, 찬성 세력은 진척시키는 수를 우선."""
    b = g["bills"]["X"]
    types = [(o["type"], o.get("action")) for o in options]
    if actor["stance"] == "반대":
        for want in [("veto", None), ("filibuster", "start"), ("mediation_committee", None)]:
            if want in types and not (want[0] == "filibuster" and b["stage"] != "본회의 대기"):
                if want == ("filibuster", "start") and g["filibuster"].get("X", {}).get("active"):
                    continue
                return options[types.index(want)]
        return {"type": "public_campaign"}
    if actor["stance"] == "찬성":
        order = [("override_veto", None), ("filibuster", "cloture_vote"), ("filibuster", "cloture_file"),
                 ("plenary_pass", None), ("judiciary_bypass", None), ("fast_track", None), ("committee_pass", None)]
        fb = g["filibuster"].get("X", {})
        for want in order:
            if want == ("filibuster", "cloture_file") and (not fb.get("active") or fb.get("cloture_filed_hours_ago") is not None):
                continue
            if want == ("filibuster", "cloture_vote") and not fb.get("active"):
                continue
            if want == ("plenary_pass", None) and fb.get("active"):
                continue
            if want == ("override_veto", None) and not b["vetoed"]:
                continue
            for o in options:
                if (o["type"], o.get("action")) == want or (want[1] is None and o["type"] == want[0]):
                    return o
        return {"type": "negotiate"}
    return {"type": "pass"}


def ai_response(g: dict, actor: dict, options: list[dict]) -> dict | None:
    from llm import call_json
    schema = {"type": "object", "additionalProperties": False, "required": ["choice", "reason"],
              "properties": {"choice": {"type": "integer"}, "reason": {"type": "string"}}}
    sys_p = ("너는 한국 국회 워게임의 한 세력을 맡는다. 주어진 '가능한 수' 목록 번호 중 하나만 고른다. "
             "목록 밖의 수는 고를 수 없다. 이유는 현재 상태와 그 세력의 입장만으로 한두 문장.")
    state = {k: g[k] for k in ("turn", "day", "seats", "total", "bills", "filibuster")}
    recent = [{"actor": e["actor"], "move": e["move"]["type"], "effect": e["effect"]} for e in g["log"][-8:]]
    user = (f"세력: {actor['name']} (입장: {actor['stance']}, 연합: {_support(g, actor['name'])})\n"
            f"상태: {json.dumps(state, ensure_ascii=False)}\n최근 일지: {json.dumps(recent, ensure_ascii=False)}\n"
            f"가능한 수: {json.dumps(list(enumerate(options)), ensure_ascii=False)}")
    r = call_json(sys_p, user, schema, purpose="wargame_turn", run_id=g["run_id"], effort="medium", max_tokens=4000)
    i = r["choice"]
    if not (0 <= i < len(options)):
        return None
    return {**options[i], "reason": r["reason"], "by": "AI"}


def advance(g: dict):
    d = g["turn_days"]
    g["day"] += d
    b = g["bills"]["X"]
    if b["stage"] == "법사위 심사":
        b["days_in_judiciary"] += d
    if b["days_since_transfer"] is not None and b["stage"] == "정부이송":
        b["days_since_transfer"] += d
        if b["days_since_transfer"] > 15:
            b["stage"], b["outcome"] = "법률 확정", "공포 또는 15일 경과 확정"
    fb = g["filibuster"].get("X")
    if fb and fb.get("cloture_filed_hours_ago") is not None:
        fb["cloture_filed_hours_ago"] += 24 * d
    # 신속처리: 소관위 60일, 법사위 30일 경과 시 자동 진행(R5, 2026.10.2 시행 국회법)
    if b["fast_track"] and b["fast_track_day"] is not None:
        el = g["day"] - b["fast_track_day"]
        if b["stage"] == "소관위 심사" and el >= 60:
            b["stage"], b["days_in_judiciary"] = "법사위 심사", 0
            g["log"].append({"turn": g["turn"], "day": g["day"], "actor": "제도", "effect": "신속처리 60일 경과 → 법사위 회부 간주(R5)", "label": "규칙"})
        if b["stage"] == "법사위 심사" and b["days_in_judiciary"] >= 30:
            b["stage"] = "본회의 대기"
            g["log"].append({"turn": g["turn"], "day": g["day"], "actor": "제도", "effect": "법사위 30일 경과 → 본회의 부의 간주(R5)", "label": "규칙"})


def play_turn(g: dict, player_move: dict, use_ai: bool = False) -> dict:
    g = copy.deepcopy(g)
    e = apply(g, g["player"], player_move)
    if not e["check"]["allowed"] or e["effect"].startswith("거부"):
        return {"game": g, "rejected": True, "entry": e}
    g["turn"] += 1
    responses = []
    for a in g["actors"]:
        if a["name"] == g["player"]:
            continue
        opts = legal_options(g, a)
        choice = None
        if use_ai and opts:
            try:
                choice = ai_response(g, a, opts)
            except Exception as ex:
                g.setdefault("ai_errors", []).append(str(ex)[:200])
        if not choice:
            choice = {**rule_based_response(g, a, opts), "by": "규칙 기반"}
        r = apply(g, a["name"], {k: v for k, v in choice.items() if k not in ("reason", "by")})
        r["by"], r["reason"] = choice.get("by"), choice.get("reason")
        responses.append(r)
    advance(g)
    return {"game": g, "rejected": False, "entry": e, "responses": responses}
