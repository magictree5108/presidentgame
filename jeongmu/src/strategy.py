"""정무 전략 엔진: 지지율 같은 '정답 없는' 정무 과제에 대한 진단 → 전략 카드 → 전개 시나리오.

근거 묶음(여론조사 추이·변곡점 전후 보도·최근 쟁점·의석·제도 규칙)을 만들어 AI(Opus)에 넘긴다.
AI는 근거 번호를 달아야 하고, 근거 없는 판단은 '근거 약함'으로 표시된다.
전략은 실전형(공세·프레임·쐐기·시점·연대 흔들기 등)으로 내되, 허위사실 유포·매수·해킹·협박·조직적 여론조작은
실행 계획에서 제외하고 리스크로만 표시한다.

사용:
  python src/strategy.py --goal "민주당·이재명 지지율 회복" --side 더불어민주당 --estimate   # 근거만 만들고 비용 추정(0원)
  python src/strategy.py --goal "..." --side 더불어민주당                                  # 허락받은 뒤 실행
"""
import argparse
import json
import sys
import uuid
from collections import Counter, defaultdict
from datetime import date, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from config import DATA
from db import connect, seats_on
from engine import Bundle
import playbook

OUT_DIR = DATA / "strategy"


def _poll_section(B: Bundle, ctx: dict):
    try:
        from polls import series
    except Exception:
        return
    tracks = [("대통령국정", "긍정"), ("대통령국정", "부정"), ("정당", "더불어민주당"), ("정당", "국민의힘"),
              ("정당", "조국혁신당"), ("정당", "개혁신당"), ("인물", "한동훈"), ("인물", "오세훈"), ("인물", "김문수")]
    ctx["polls"] = {}
    for kind, target in tracks:
        s = [x for x in series(kind, target) if x["date"]]
        if not s:
            continue
        ctx["polls"][f"{kind}:{target}"] = s
        by_p = defaultdict(list)
        for x in s:
            by_p[x["pollster"]].append(x)
        for pl, xs in sorted(by_p.items(), key=lambda kv: -len(kv[1]))[:3]:
            if len(xs) < 2:
                continue
            tail = xs[-12:]
            line = ", ".join(f"{x['date']} {x['value']:g}%" for x in tail)
            B.add("보도", f"[여론조사 추이] {kind} {target} — {pl}: {line}", tail[-1]["urls"][0] if tail[-1]["urls"] else None,
                  data={"kind": kind, "target": target, "pollster": pl, "series": tail})


def _turning_points(ctx: dict, min_change: float = 3.0) -> list[dict]:
    """같은 조사기관 연속 조사에서 min_change(%p) 이상 움직인 구간."""
    out = []
    for key, s in ctx.get("polls", {}).items():
        by_p = defaultdict(list)
        for x in s:
            by_p[x["pollster"]].append(x)
        for pl, xs in by_p.items():
            for a, b in zip(xs, xs[1:]):
                d = b["value"] - a["value"]
                if abs(d) >= min_change:
                    out.append({"track": key, "pollster": pl, "from": a["date"], "to": b["date"], "change": round(d, 1)})
    return sorted(out, key=lambda x: -abs(x["change"]))[:8]


TRIVIAL = ("참석", "인사말", "축사", "기공식", "시삽", "개최 예정", "토론회", "간담회", "임명됨", "방문")


def _news_in(start: str, end: str, limit: int = 8) -> list[dict]:
    """기간 내 주요 보도 사실. 의례성 기사는 빼고, 같은 의원·같은 날은 한 건만, '갈등'을 앞에 둔다."""
    try:
        from news import nconnect
    except Exception:
        return []
    con = nconnect()
    rows = con.execute(
        """SELECT f.category, f.summary, a.pub_date, a.press_domain, a.url, m.entity_name FROM facts f
           JOIN articles a ON a.url=f.url LEFT JOIN mentions m ON m.url=f.url AND m.entity_id=f.entity_id
           WHERE a.pub_date BETWEEN ? AND ? AND f.category IN ('갈등','입장 표명','발의·표결 예고')""",
        (start, end)).fetchall()
    rank = {"갈등": 0, "발의·표결 예고": 1, "입장 표명": 2}
    rows = sorted((dict(r) for r in rows if r["summary"] and not any(t in r["summary"] for t in TRIVIAL)),
                  key=lambda r: (rank[r["category"]], r["pub_date"]), reverse=False)
    rows.sort(key=lambda r: (rank[r["category"]], -int(r["pub_date"].replace("-", ""))))
    # 같은 의원·같은 날은 1건, 하루 최대 4건 → 기간 전체에 고르게 퍼지도록 날짜를 돌아가며 뽑는다
    seen, by_day = set(), defaultdict(list)
    for r in rows:
        k = (r["entity_name"], r["pub_date"])
        if k in seen or len(by_day[r["pub_date"]]) >= 4:
            continue
        seen.add(k)
        by_day[r["pub_date"]].append(r)
    out, days = [], sorted(by_day, reverse=True)
    while len(out) < limit and any(by_day[d] for d in days):
        for d in days:
            if by_day[d] and len(out) < limit:
                out.append(by_day[d].pop(0))
    return sorted(out, key=lambda r: r["pub_date"], reverse=True)


def _poll_headlines(start: str, end: str, limit: int = 6) -> list[dict]:
    """해당 기간 여론조사 기사 제목(원인 설명이 제목에 담기는 경우가 많다). 제목만 쓴다."""
    try:
        from polls import pconnect
        con = pconnect()
        return [dict(r) for r in con.execute(
            """SELECT title, pub_date, press_domain, url FROM poll_articles WHERE pub_date BETWEEN ? AND ?
               AND (title LIKE '%하락%' OR title LIKE '%상승%' OR title LIKE '%반등%' OR title LIKE '%최저%'
                    OR title LIKE '%최고%' OR title LIKE '%여파%' OR title LIKE '%영향%')
               ORDER BY pub_date DESC LIMIT ?""", (start, end, limit))]
    except Exception:
        return []


def add_brief(B: Bundle, path: Path):
    """사람이 조사해 넣은 사실(지역구·후보 등). 한 줄 = '라벨 | 내용 | 링크'."""
    for line in Path(path).read_text(encoding="utf-8").splitlines():
        if not line.strip() or line.startswith("#"):
            continue
        parts = [x.strip() for x in line.split("|")]
        label, text = parts[0], parts[1]
        link = parts[2] if len(parts) > 2 and parts[2] else None
        B.add(label if label in ("기록", "보도", "규칙") else "보도", f"[과제 자료] {text}", link)


def build_bundle(goal: str, side: str, on: str, brief: Path | None = None) -> tuple[Bundle, dict]:
    B = Bundle()
    if brief:
        add_brief(B, brief)
    ctx = {"goal": goal, "side": side, "on": on}
    con = connect()
    s = seats_on(con, on)
    B.add("기록", f"{on} 기준 재적 {s['total']}명, 정당별 의석 {s['by_party']}")
    _poll_section(B, ctx)
    tps = _turning_points(ctx)
    ctx["turning_points"] = tps
    for tp in tps:
        B.add("보도", f"[변곡점] {tp['track']} ({tp['pollster']}) {tp['from']}→{tp['to']} {tp['change']:+g}%p")
        start = (date.fromisoformat(tp["from"]) - timedelta(days=3)).isoformat()
        for h in _poll_headlines(start, (date.fromisoformat(tp["to"]) + timedelta(days=3)).isoformat(), limit=3):
            B.add("보도", f"  └ 같은 기간 여론조사 기사 제목: {h['pub_date']} {h['title']} ({h['press_domain']})", h["url"])
        for n in _news_in(start, tp["to"], limit=4):
            B.add("보도", f"  └ 같은 기간 보도: {n['pub_date']} {n['entity_name'] or ''} [{n['category']}] {n['summary']}",
                  n["url"])
    for h in _poll_headlines((date.fromisoformat(on) - timedelta(days=21)).isoformat(), on, limit=8):
        B.add("보도", f"[최근 여론조사 기사 제목] {h['pub_date']} {h['title']} ({h['press_domain']})", h["url"])
    recent = _news_in((date.fromisoformat(on) - timedelta(days=14)).isoformat(), on, limit=25)
    for n in recent:
        B.add("보도", f"[최근 쟁점] {n['pub_date']} {n['entity_name'] or ''} [{n['category']}] {n['summary']}", n["url"])
    try:
        from news import nconnect
        nc = nconnect()
        conf = Counter()
        from engine import current_party_map
        pm = current_party_map(con, on)
        for r in nc.execute("""SELECT f.entity_id FROM facts f JOIN articles a ON a.url=f.url
                               WHERE f.category='갈등' AND a.pub_date >= ?""",
                            ((date.fromisoformat(on) - timedelta(days=30)).isoformat(),)):
            conf[pm.get(r[0], "기타")] += 1
        if conf:
            B.add("보도", f"[최근 30일 '갈등' 보도 건수, 언급 의원 소속 정당별] {dict(conf.most_common())}")
    except Exception:
        pass
    # 정치 일정 달력(data/calendar.json): 최근 7일 ~ 앞으로 70일
    cal = DATA / "calendar.json"
    if cal.exists():
        lo = (date.fromisoformat(on) - timedelta(days=7)).isoformat()
        hi = (date.fromisoformat(on) + timedelta(days=70)).isoformat()
        for e in sorted(json.loads(cal.read_text(encoding="utf-8"))["events"], key=lambda e: e["date"]):
            if lo <= e.get("end", e["date"]) and e["date"] <= hi:
                when = e["date"] + (f"~{e['end']}" if e.get("end") else "")
                link = e["source"] if e["source"].startswith("http") else None
                B.add(e["label"], f"[일정·{e['status']}] {when} {e['title']}" + ("" if link else f" (근거: {e['source']})"),
                      link.split(" ; ")[0] if link else None)
    # 쟁점별 공개 입장 기록(src/stances.py, 0원)
    try:
        import stances
        for label, text, link in stances.bundle_lines(stances.build(on)):
            B.add(label, text, link)
    except Exception as e:
        B.add("기록", f"[쟁점 입장 기록 생성 실패: {e}]")
    rules = json.loads((DATA / "rules_institutional.json").read_text(encoding="utf-8"))["rules"]
    for r in rules:
        if r["id"] in ("R8", "R9", "R10", "R11", "R16", "R17"):
            B.add("규칙", f"{r['id']} {r['title']}: {r['rule']}")
    return B, ctx


SYSTEM = """너는 한국 정치의 최고 수준 정무 전략가다. 사용자가 고른 진영의 목표를 달성하는 것만이 목적이다.
점잖은 조언·원론·양비론은 쓸모없다. 실제로 판을 움직이는 전략을 낸다: 프레임 선점, 의제 전환, 상대 약점(공개 기록·발언·실책) 집중 공략,
쐐기 이슈로 상대 진영 분열, 시점 조절, 연대 흔들기, 언론·메시지 운용, 정책 승부수, 인사 카드 등.
회색지대 수단도 배제하지 말고, 대신 legal_risk(0~5)와 backlash_risk(0~5)로 값을 매긴다.

규칙:
- 사실 판단은 주어진 근거 목록 [E번호] 안에서만 하고, 문장마다 refs 를 단다. 근거 밖 사실·수치를 지어내지 않는다.
  근거가 없으면 refs 를 비운다(화면에 '근거 약함'). 일반적인 정치 경험칙에 의존한 판단은 rationale 에 '경험칙:'으로 밝힌다.
- 다음은 실행 계획으로 내지 않는다(효과가 있어 보여도): 허위 사실 유포·조작, 매수·금품, 해킹·불법 정보 취득, 협박,
  댓글부대·가짜계정 같은 조직적 여론조작. 상대가 그런 수를 쓸 가능성은 위협으로 분석해도 된다.
- 기대 효과는 지지율 %p 범위와 걸리는 주(週)로 쓰되, 근거가 약하면 범위를 넓게 잡는다.
- 예측(predictions)은 나중에 실제 여론조사로 채점할 수 있게 구체적으로 쓴다(조사기관, 대상, 기한, 범위).
- [일정] 근거로 '언제 칠지'를 정한다: 전략 카드 steps 에 날짜나 일정 기준 시점을 쓴다(예: '11/4 종합정책질의 전날').
- [쟁점 입장 기록] 근거로 상대의 과거 공개 입장과 표결을 확인하고, 그 기록과 모순되게 만드는 질문·제안을 설계한다.
- 원칙집(책 8권 요약)은 배경 지식으로만 쓴다. 책·원칙 번호를 출력에 인용하지 않는다.
  뻔한 수(상대·언론이 예상할 대응)보다 상대에게 어떻게 대응해도 손해인 선택을 강요하는 수, 예상 패턴을 깨는 수를 우선한다.
- 너는 의뢰인의 참모다. 의뢰인 제약(레드라인)을 어기는 안은 아무리 효과가 있어 보여도 내지 않는다.
  카드마다 principal_fit 에 '의뢰인이 왜 이 안을 받아들일 수 있는가'와 수용 난도(하/중/상)를 쓴다.
- 종료된 이슈·피로한 프레임·금지 카드 유형 목록에 걸리는 안은 내지 않는다. 사용자 피드백을 반드시 반영한다.
- 카드마다 scale 을 '거시'(국면·구도를 바꿔 지지율 자체를 움직이는 수) 또는 '보조'(세부 정책·법안)로 표시하고 거시 카드를 중심으로 낸다.
- 여론조사 수치는 보도에서 자동 추출한 값이라 일부 오류가 있을 수 있다. 조사기관마다 방식(전화면접/ARS)이 달라 수준 차이가 크니
  기관 간 수치를 직접 비교하지 말고 같은 기관 안의 추세로 판단한다. 한 번만 튀는 급변은 신중히 해석한다."""

SCHEMA = {
    "type": "object", "additionalProperties": False,
    "required": ["situation", "diagnosis", "strategies", "scenarios", "watch", "predictions"],
    "properties": {
        "situation": {"type": "object", "additionalProperties": False, "required": ["text", "refs"],
                      "properties": {"text": {"type": "string"}, "refs": {"type": "array", "items": {"type": "string"}}}},
        "diagnosis": {"type": "array", "items": {"type": "object", "additionalProperties": False,
            "required": ["driver", "direction", "weight", "rationale", "refs"],
            "properties": {"driver": {"type": "string"}, "direction": {"type": "string", "enum": ["하락 요인", "상승 요인"]},
                           "weight": {"type": "string", "enum": ["상", "중", "하"]}, "rationale": {"type": "string"},
                           "refs": {"type": "array", "items": {"type": "string"}}}}},
        "strategies": {"type": "array", "items": {"type": "object", "additionalProperties": False,
            "required": ["name", "kind", "steps", "target_audience", "expected_pp_low", "expected_pp_high", "weeks",
                         "legal_risk", "backlash_risk", "opponent_counter", "counter_to_counter", "rationale", "refs",
                         "scale", "principal_fit"],
            "properties": {"name": {"type": "string"},
                           "kind": {"type": "string", "enum": ["프레임", "의제 전환", "공세", "쐐기", "연대", "정책 승부수",
                                                               "인사", "시점", "구도 재편", "언론·메시지", "방어·수습"]},
                           "steps": {"type": "array", "items": {"type": "string"}},
                           "target_audience": {"type": "string"},
                           "expected_pp_low": {"type": "number"}, "expected_pp_high": {"type": "number"},
                           "weeks": {"type": "integer"},
                           "legal_risk": {"type": "integer"}, "backlash_risk": {"type": "integer"},
                           "opponent_counter": {"type": "string"}, "counter_to_counter": {"type": "string"},
                           "rationale": {"type": "string"}, "refs": {"type": "array", "items": {"type": "string"}},
                           "scale": {"type": "string", "enum": ["거시", "보조"]},
                           "principal_fit": {"type": "string"}}}},
        "scenarios": {"type": "array", "items": {"type": "object", "additionalProperties": False,
            "required": ["name", "probability", "path", "end_state", "refs"],
            "properties": {"name": {"type": "string"}, "probability": {"type": "number"},
                           "path": {"type": "array", "items": {"type": "string"}},
                           "end_state": {"type": "string"}, "refs": {"type": "array", "items": {"type": "string"}}}}},
        "watch": {"type": "array", "items": {"type": "string"}},
        "predictions": {"type": "array", "items": {"type": "object", "additionalProperties": False,
            "required": ["pollster", "target_kind", "target", "by_date", "low", "high"],
            "properties": {"pollster": {"type": "string"}, "target_kind": {"type": "string"}, "target": {"type": "string"},
                           "by_date": {"type": "string"}, "low": {"type": "number"}, "high": {"type": "number"}}}},
    },
}

CONSTRAINTS = OUT_DIR / "constraints.json"


def constraints_text(path: Path | None = None) -> str:
    path = Path(path) if path else CONSTRAINTS
    if not path.exists():
        return "(없음)"
    c = json.loads(path.read_text(encoding="utf-8"))
    parts = [f"의뢰인: {c.get('principal', '')}"]
    for key, title in (("red_lines", "레드라인(어기면 안 됨)"), ("closed_issues", "종료된 이슈(쓰지 말 것)"),
                       ("fatigued_frames", "피로한 프레임(쓰지 말 것)"), ("banned_card_patterns", "금지 카드 유형")):
        parts.append(title + ":\n" + "\n".join(f"- {x}" for x in c.get(key, [])))
    if c.get("analysis_standard"):
        parts.append("분석 기준(모든 진단·카드에 적용):\n" + "\n".join(f"- {x}" for x in c["analysis_standard"]))
    if c.get("scale_rule"):
        parts.append("규모 기준: " + c["scale_rule"])
    fb = c.get("feedback_log", [])[-5:]
    if fb:
        parts.append("사용자 피드백(최근):\n" + "\n".join(f"- {f['date']} {f['note']}" for f in fb))
    return "\n\n".join(parts)


# 실측 기반 대략 단가(Opus 5.5): 입력 $4/MTok, 출력 $20/MTok. 전략 1회는 출력·추론이 길다.
def estimate_usd(bundle: Bundle, constraints: Path | None = None) -> tuple[float, float]:
    in_tok = len(SYSTEM + bundle.as_prompt() + playbook.as_prompt() + constraints_text(constraints)) / 1.6 + 2500  # 한국어 대략 1.6자/토큰 + 스키마
    lo = in_tok * 4 / 1e6 + 6000 * 20 / 1e6
    hi = in_tok * 4 / 1e6 + 32000 * 20 / 1e6
    return round(lo, 3), round(hi, 3)


def run(goal: str, side: str, on: str | None = None, estimate_only: bool = False,
        constraints: Path | None = None, brief: Path | None = None) -> dict:
    on = on or date.today().isoformat()
    B, ctx = build_bundle(goal, side, on, brief)
    lo, hi = estimate_usd(B, constraints)
    res = {"goal": goal, "side": side, "on": on, "n_evidence": len(B.items),
           "estimate_usd": [lo, hi], "estimate_krw": [round(lo * 1400), round(hi * 1400)]}
    if estimate_only:
        res["evidence_preview"] = [f"{i['ref']} ({i['label']}) {i['text'][:120]}" for i in B.items[:60]]
        return res
    from engine import check_refs
    from llm import call_json, usage_summary
    run_id = "st_" + uuid.uuid4().hex[:10]
    before = usage_summary()["cost_usd"]
    prompt = (f"진영: {side}\n목표: {goal}\n기준일: {on}\n\n근거 목록:\n{B.as_prompt()}\n\n"
              f"의뢰인 제약·피로도·사용자 피드백(반드시 지킬 것):\n{constraints_text(constraints)}\n\n"
              f"원칙집(배경 지식, 인용 금지):\n{playbook.as_prompt()}\n\n"
              "진단 → 전략 카드 6~10개(서로 다른 종류, 실전형) → 전개 시나리오 3~4개(확률 합 1) → 주시할 지표 → 채점 가능한 예측 순으로.")
    out = call_json(SYSTEM, prompt, SCHEMA, purpose="strategy", run_id=run_id, effort="medium", max_tokens=32000)  # 출력 최대 약 $0.64. high 는 추론이 길어 2만 토큰에서 잘림(2026-10-28)
    valid = B.refs()
    out["situation"] = check_refs([out["situation"]], valid)[0]
    for k in ("diagnosis", "strategies", "scenarios"):
        out[k] = check_refs(out[k], valid)
    res.update(out)
    res["evidence"] = B.items
    res["run_id"] = run_id
    res["cost_usd"] = round(usage_summary()["cost_usd"] - before, 4)
    from predictions import record
    for p in out["predictions"]:
        record("poll_range", p, subject=f"{p['pollster']} {p['target_kind']} {p['target']}", source="strategy",
               resolve_by=p["by_date"], basis=[run_id])
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    (OUT_DIR / f"{run_id}.json").write_text(json.dumps(res, ensure_ascii=False, indent=1, default=str), encoding="utf-8")
    (OUT_DIR / "latest.json").write_text(json.dumps(res, ensure_ascii=False, indent=1, default=str), encoding="utf-8")
    return res


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--goal", required=True)
    ap.add_argument("--side", required=True)
    ap.add_argument("--on")
    ap.add_argument("--estimate", action="store_true", help="근거만 만들고 예상 비용 출력(0원)")
    ap.add_argument("--constraints", help="의뢰인 제약 파일(기본 data/strategy/constraints.json)")
    ap.add_argument("--brief", help="과제 자료 파일(라벨 | 내용 | 링크)")
    a = ap.parse_args()
    r = run(a.goal, a.side, a.on, a.estimate, a.constraints, a.brief)
    if a.estimate:
        print(f"근거 {r['n_evidence']}개, 예상 비용 ${r['estimate_usd'][0]}~${r['estimate_usd'][1]} "
              f"(약 {r['estimate_krw'][0]}~{r['estimate_krw'][1]}원)")
        print("\n".join(r["evidence_preview"][:40]))
    else:
        print(json.dumps({k: r[k] for k in ("goal", "side", "cost_usd")}, ensure_ascii=False))
        for s in r["strategies"]:
            print(f"- [{s['kind']}] {s['name']} {s['expected_pp_low']}~{s['expected_pp_high']}%p/{s['weeks']}주 "
                  f"법{s['legal_risk']} 역풍{s['backlash_risk']}")
