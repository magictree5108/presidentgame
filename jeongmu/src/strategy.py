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


def build_bundle(goal: str, side: str, on: str) -> tuple[Bundle, dict]:
    B = Bundle()
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
- 원칙집(책 8권 요약, [D3]·[W20] 같은 원칙 번호)을 전략 설계의 도구로 쓴다. 전략 카드마다 principles 에 근거 원칙 1~3개를 단다.
  원칙의 '실패조건'에 해당하는 상황이면 backlash_risk 를 올리고 rationale 에 그 이유를 쓴다.
  '방어' 원칙은 상대가 쓸 수를 예상해 opponent_counter·방어·수습 카드에 쓴다.
  뻔한 수(상대·언론이 예상할 대응)보다 원칙을 조합한 예상 밖의 수를 우선한다(W24, W20, L31, T6).
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
                         "principles"],
            "properties": {"name": {"type": "string"},
                           "kind": {"type": "string", "enum": ["프레임", "의제 전환", "공세", "쐐기", "연대", "정책 승부수",
                                                               "인사", "시점", "조직·당내", "언론·메시지", "방어·수습"]},
                           "steps": {"type": "array", "items": {"type": "string"}},
                           "target_audience": {"type": "string"},
                           "expected_pp_low": {"type": "number"}, "expected_pp_high": {"type": "number"},
                           "weeks": {"type": "integer"},
                           "legal_risk": {"type": "integer"}, "backlash_risk": {"type": "integer"},
                           "opponent_counter": {"type": "string"}, "counter_to_counter": {"type": "string"},
                           "rationale": {"type": "string"}, "refs": {"type": "array", "items": {"type": "string"}},
                           "principles": {"type": "array", "items": {"type": "string"}}}}},
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

# 실측 기반 대략 단가(Opus 5.5): 입력 $4/MTok, 출력 $20/MTok. 전략 1회는 출력·추론이 길다.
def estimate_usd(bundle: Bundle) -> tuple[float, float]:
    in_tok = len(SYSTEM + bundle.as_prompt() + playbook.as_prompt()) / 1.6 + 2500  # 한국어 대략 1.6자/토큰 + 스키마
    lo = in_tok * 4 / 1e6 + 6000 * 20 / 1e6
    hi = in_tok * 4 / 1e6 + 20000 * 20 / 1e6
    return round(lo, 3), round(hi, 3)


def run(goal: str, side: str, on: str | None = None, estimate_only: bool = False) -> dict:
    on = on or date.today().isoformat()
    B, ctx = build_bundle(goal, side, on)
    lo, hi = estimate_usd(B)
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
              f"원칙집:\n{playbook.as_prompt()}\n\n"
              "진단 → 전략 카드 6~10개(서로 다른 종류, 실전형) → 전개 시나리오 3~4개(확률 합 1) → 주시할 지표 → 채점 가능한 예측 순으로.")
    out = call_json(SYSTEM, prompt, SCHEMA, purpose="strategy", run_id=run_id, effort="high", max_tokens=20000)  # 비용 상한(출력 최대 약 $0.40)
    valid = B.refs()
    out["situation"] = check_refs([out["situation"]], valid)[0]
    for k in ("diagnosis", "strategies", "scenarios"):
        out[k] = check_refs(out[k], valid)
    out["strategies"] = playbook.check_principles(out["strategies"])
    res["playbook"] = playbook.lookup()
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
    a = ap.parse_args()
    r = run(a.goal, a.side, a.on, a.estimate)
    if a.estimate:
        print(f"근거 {r['n_evidence']}개, 예상 비용 ${r['estimate_usd'][0]}~${r['estimate_usd'][1]} "
              f"(약 {r['estimate_krw'][0]}~{r['estimate_krw'][1]}원)")
        print("\n".join(r["evidence_preview"][:40]))
    else:
        print(json.dumps({k: r[k] for k in ("goal", "side", "cost_usd")}, ensure_ascii=False))
        for s in r["strategies"]:
            print(f"- [{s['kind']}] {s['name']} {s['expected_pp_low']}~{s['expected_pp_high']}%p/{s['weeks']}주 "
                  f"법{s['legal_risk']} 역풍{s['backlash_risk']}")
