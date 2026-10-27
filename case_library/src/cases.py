"""5단계 케이스 도서관: 지지율이 기준선에서 유의하게 벗어난 시점을 찾아 케이스 카드(cases.json)를 만든다.

실행 예:
    python src/cases.py

감지 규칙(임계값은 config.yaml 의 cases 항목):
- 전체: 1~3번의 조사 사이 잔차 변화가 overall_z × 변화량 표준오차(sqrt(se_끝² + se_기준²))를 넘음
- 집단: 1~3번의 조사 사이 그 집단 잔차 변화가 group_moe_multiple × 집단 표본오차(moe_z × 표준오차)를 넘음
감지된 구간이 겹치면(같은 방향) 하나의 케이스로 묶는다. 집단 신호가 전체 케이스와 겹치면 그 케이스에 붙이고,
겹치지 않는 집단 신호끼리는 '집단 케이스'로 묶는다.

사건: data/events_reviewed.csv 가 있으면 '승인'·'수정' 사건만 쓰고, 없으면 자동 추출 사건을 '미검토 후보'로 싣는다.
원인을 하나로 단정하지 않고 같은 주와 앞 주의 사건을 모두 후보로 남긴다.
"""
from __future__ import annotations

import csv
import json
import re
import sqlite3
from pathlib import Path

import numpy as np
import pandas as pd
import yaml

import events as ev

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "data"
CONTENT_URL = "https://www.gallup.co.kr/gallupdb/reportContent.asp?seqNo={seq}"


def load_config() -> dict:
    with open(ROOT / "config.yaml", encoding="utf-8") as f:
        return yaml.safe_load(f)


def triggers(g: pd.DataFrame, windows, thr_fn) -> list[dict]:
    g = g.reset_index(drop=True)
    out = []
    for k in windows:
        for i in range(k, len(g)):
            d = g.residual[i] - g.residual[i - k]
            thr = thr_fn(g, i, k)
            if abs(d) > thr:
                out.append({"ref": int(g.issue[i - k]), "end": int(g.issue[i]), "k": k,
                            "d": float(d), "thr": float(thr), "z": float(d / thr)})
    return out


def merge(intervals: list[dict], same_sign: bool) -> list[list[dict]]:
    """[ref, end] 구간이 겹치면(한 단계 이상 공유) 묶는다."""
    groups: list[list[dict]] = []
    for t in sorted(intervals, key=lambda t: (t["ref"], t["end"])):
        if groups:
            g = groups[-1]
            g_end = max(x["end"] for x in g)
            sign_ok = (not same_sign) or (np.sign(g[0]["d"]) == np.sign(t["d"]))
            if t["ref"] < g_end and sign_ok:
                g.append(t)
                continue
        groups.append([t])
    return groups


def main():
    cfg = load_config()["cases"]
    con = sqlite3.connect(DATA / "weekly.sqlite")
    b = pd.read_sql("SELECT * FROM baseline ORDER BY category, subgroup, t_weeks", con)
    sv = pd.read_sql("SELECT issue, week_label, survey_start, survey_end, post_date FROM survey", con).set_index("issue")
    reasons = pd.read_sql("SELECT issue, polarity, item, pct, change_pp, base_n FROM reasons", con)
    with open(DATA / "manifest.csv", encoding="utf-8-sig") as f:
        manifest = {int(r["issue"]): r for r in csv.DictReader(f) if r["issue"]}
    commentary = {}
    with open(DATA / "weekly_commentary.csv", encoding="utf-8-sig") as f:
        for r in csv.DictReader(f):
            commentary[int(r["issue"])] = r["approval_commentary"]

    reviewed_path = DATA / "events_reviewed.csv"
    reviewed = reviewed_path.exists()
    with open(reviewed_path if reviewed else DATA / "events.csv", encoding="utf-8-sig") as f:
        evs = list(csv.DictReader(f))
    if reviewed:
        evs = [e for e in evs if e["review_status"] in ("승인", "수정")]
    events_by_issue: dict[int, list] = {}
    for e in evs:
        events_by_issue.setdefault(int(e["issue"]), []).append(e)

    tot = b[b.category == "전체"].reset_index(drop=True)
    order = list(tot.issue)                      # 직무 평가가 있는 호수 순서
    pos = {iss: i for i, iss in enumerate(order)}
    groups = {k: g.reset_index(drop=True) for k, g in b[b.category != "전체"].groupby(["category", "subgroup"])}

    # ---- 신호 감지 ----
    ov = triggers(tot, cfg["windows"],
                  lambda g, i, k: cfg["overall_z"] * np.sqrt(g.se[i] ** 2 + g.se[i - k] ** 2))
    gt = []
    for key, g in groups.items():
        for t in triggers(g, cfg["windows"], lambda g, i, k: cfg["group_moe_multiple"] * cfg["moe_z"] * g.se[i]):
            gt.append({**t, "group": key})

    cases = []
    for grp in merge(ov, same_sign=True):
        cases.append({"type": "전체", "ref": min(t["ref"] for t in grp), "end": max(t["end"] for t in grp),
                      "overall_triggers": grp, "group_triggers": []})
    rest = []
    for t in gt:
        host = next((c for c in cases if t["ref"] < c["end"] and t["end"] > c["ref"]), None)
        (host["group_triggers"].append(t) if host else rest.append(t))
    for grp in merge(rest, same_sign=False):
        cases.append({"type": "집단", "ref": min(t["ref"] for t in grp), "end": max(t["end"] for t in grp),
                      "overall_triggers": [], "group_triggers": grp})
    # 끝 주 = 구간 안에서 기준 주 잔차로부터 케이스 방향으로 가장 멀리 간 주(떨어졌다 반등한 경우 저점)
    for c in cases:
        trig = c["overall_triggers"] or c["group_triggers"]
        if c["overall_triggers"]:
            sign = np.sign(trig[0]["d"])
            ia, ib = pos[c["ref"]], pos[c["end"]]
            seg = tot.iloc[ia + 1:ib + 1]
            c["end"] = int(seg.issue.iloc[int(np.argmax(sign * (seg.residual.values - tot.residual[ia])))])
    cases.sort(key=lambda c: (pos[c["ref"]], pos[c["end"]]))

    # ---- 카드 만들기 ----
    cards = []
    for n, c in enumerate(cases, 1):
        a, e = c["ref"], c["end"]
        ia, ie = pos[a], pos[e]
        span = order[ia:ie + 1]
        ra, re_ = tot.iloc[ia], tot.iloc[ie]
        d_res = float(re_.residual - ra.residual)
        d_raw = float(re_.approve - ra.approve)
        ch_se = float(np.sqrt(re_.se ** 2 + ra.se ** 2))

        # 집단별 변화량 순위
        trig_groups = {t["group"] for t in c["group_triggers"]}
        gl = []
        for (cat, sub), g in groups.items():
            ga, ge = g[g.issue == a], g[g.issue == e]
            if ga.empty or ge.empty:
                continue
            ga, ge = ga.iloc[0], ge.iloc[0]
            dr = float(ge.residual - ga.residual)
            thr = cfg["group_moe_multiple"] * cfg["moe_z"] * float(ge.se)
            gl.append({"category": cat, "subgroup": sub, "approve_from": float(ga.approve), "approve_to": float(ge.approve),
                       "change": round(float(ge.approve - ga.approve), 1), "residual_change": round(dr, 1),
                       "threshold": round(thr, 1), "detected": (cat, sub) in trig_groups or abs(dr) > thr,
                       "n_raw_to": int(ge.n_raw)})
        gl.sort(key=lambda x: -abs(x["residual_change"]))
        for r, x in enumerate(gl, 1):
            x["rank"] = r

        # 방향
        if c["type"] == "전체":
            direction = "상승" if d_res > 0 else "하락"
        else:
            s = sum(t["z"] for t in c["group_triggers"])
            direction = ("상승" if s > 0 else "하락") + "(집단)"

        # 평가 이유 변화
        rc = []
        changed_domains = set()
        for pol, lab in (("positive", "긍정"), ("negative", "부정")):
            # 같은 항목이 호수마다 띄어쓰기만 다르게 적히는 경우가 있어(강제동원/강제 동원) 공백을 빼고 맞춘다
            A = reasons[(reasons.issue == a) & (reasons.polarity == pol)].assign(key=lambda d: d["item"].str.replace(" ", "")).set_index("key")
            E = reasons[(reasons.issue == e) & (reasons.polarity == pol)].assign(key=lambda d: d["item"].str.replace(" ", "")).set_index("key")
            for key in sorted(set(A.index) | set(E.index)):
                item = E.item[key] if key in E.index else A.item[key]
                if item in ("기타", "모름/응답거절"):
                    continue
                pa = float(A.pct[key]) if key in A.index else None
                pe = float(E.pct[key]) if key in E.index else None
                if pa is not None and pe is not None:
                    if abs(pe - pa) < cfg["reason_change_pp"]:
                        continue
                    kind = "증가" if pe > pa else "감소"
                elif pe is not None and pe >= cfg["reason_change_pp"]:
                    kind = "새로 등장(기준 주 목록에 없음)"
                elif pa is not None and pa >= cfg["reason_change_pp"]:
                    kind = "사라짐(끝 주 목록에 없음)"
                else:
                    continue
                dom, _ = ev.classify(item)
                if dom != "기타":
                    changed_domains.add(dom)
                rc.append({"polarity": lab, "item": item, "pct_from": pa, "pct_to": pe,
                           "change": None if pa is None or pe is None else round(pe - pa, 1),
                           "kind": kind, "domain": dom})
        rc.sort(key=lambda x: -abs(x["change"] if x["change"] is not None else (x["pct_to"] or x["pct_from"])))

        # 사건 후보: 케이스 기간의 주 + 앞 주(기준 주 a)
        event_weeks = [a] + [i for i in span if i != a]
        cand = []
        for i in event_weeks:
            for x in events_by_issue.get(i, []):
                cand.append({"event_id": x["event_id"], "issue": i, "week_role": "앞 주" if i == a else "케이스 주",
                             "date": x["date_text"], "event": x["event"], "domain": x["domain"],
                             "matches_changed_reason": x["domain"] in changed_domains,
                             "reviewed": reviewed})
        cand.sort(key=lambda x: (not x["matches_changed_reason"], x["issue"]))
        matched = [x for x in cand if x["matches_changed_reason"]]

        # 신뢰 수준
        notes = []
        if len(matched) == 1:
            conf = "높음"
        elif len(matched) >= 2:
            conf = "낮음"
            notes.append(f"이유 변화와 같은 분야 사건이 {len(matched)}개 겹침 → 원인 후보를 모두 남김")
        else:
            conf = "판단 불가"
            notes.append("이유 변화와 같은 분야로 분류된 사건이 없음")
        if not reviewed:
            notes.append("사건이 사람 검토 전(자동 추출·자동 분류) → 신뢰 수준은 잠정")
        if int(ra.edge) or int(re_.edge):
            notes.append("기준선 가장자리 구간 → 잔차 신뢰도 낮음")
        if c["type"] == "전체" and abs(d_raw) < ch_se:
            notes.append(f"실제 긍정률 변화({d_raw:+g}%p)는 조사 오차 안이고 기준선이 움직여 생긴 신호일 수 있음")
        if c["type"] == "집단":
            notes.append("전체 긍정률은 유의하게 움직이지 않았고 일부 집단만 움직임")
        nd = len(c["group_triggers"])
        if nd:
            notes.append(f"집단 신호 {nd}건 중 일부는 우연일 수 있음(집단 34개×여러 주를 동시에 보므로)")

        # 회복: 끝 주 뒤 잔차가 기준 주 잔차 근처로 돌아오기까지
        rec = None
        for j in range(ie + 1, len(tot)):
            rj = tot.iloc[j]
            if abs(rj.residual - ra.residual) <= cfg["recovery_z"] * np.sqrt(rj.se ** 2 + ra.se ** 2):
                rec = {"weeks": round(float(rj.t_weeks - re_.t_weeks), 1), "issue": int(rj.issue)}
                break

        # 해설 발췌: 끝 주 해설 중 긍정률·부정률 변화를 설명하는 첫 ◎ 문단
        paras = [p.strip() for p in re.split(r"◎", commentary.get(e, "")) if p.strip()]
        # 직전 대비 변화를 설명하는 문단을 우선한다
        scored = [(bool(re.search(r"지난주|전주|직전|주 전", p)) + bool(re.search(r"하락|상승|올랐|떨어|늘|줄|최저|최고|반등", p)), p)
                  for p in paras[1:] if re.search(r"긍정률|부정률", p)]
        excerpt = max(scored, key=lambda x: x[0])[1] if scored else ""
        if len(excerpt) > 300:
            excerpt = excerpt[:300] + "…"

        src = sorted(set(span) | {a})
        cards.append({
            "case_id": f"C{n:03d}", "type": c["type"], "direction": direction,
            "reference_issue": a, "start_issue": order[ia + 1], "end_issue": e,
            "reference_week": sv.loc[a, "week_label"], "start_week": sv.loc[order[ia + 1], "week_label"],
            "end_week": sv.loc[e, "week_label"],
            "period": f"{sv.loc[order[ia + 1], 'survey_start']} ~ {sv.loc[e, 'survey_end']}",
            "overall": {"approve_from": float(ra.approve), "approve_to": float(re_.approve), "change": round(d_raw, 1),
                        "residual_change": round(d_res, 1), "change_se": round(ch_se, 2),
                        "z": round(d_res / ch_se, 2), "significant": abs(d_res) > cfg["overall_z"] * ch_se},
            "group_changes": gl,
            "reason_changes": rc,
            "event_candidates": cand,
            "event_weeks": event_weeks,
            "recovery": rec,
            "recovery_note": None if rec else "관측 끝(제606호)까지 기준 주 수준으로 돌아오지 않음",
            "confidence": conf, "confidence_notes": notes,
            "gallup_commentary_excerpt": excerpt,
            "sources": [{"issue": i, "week": sv.loc[i, "week_label"],
                         "url": CONTENT_URL.format(seq=manifest[i]["seq_no"]), "pdf": manifest[i]["pdf_url"]}
                        for i in src],
            "events_reviewed": reviewed,
        })

    (DATA / "cases.json").write_text(json.dumps(cards, ensure_ascii=False, indent=1), encoding="utf-8")
    summ = [{"case_id": c["case_id"], "type": c["type"], "direction": c["direction"],
             "start": c["start_week"], "end": c["end_week"], "weeks": len(c["event_weeks"]) - 1,
             "approve": f"{c['overall']['approve_from']:g}→{c['overall']['approve_to']:g}",
             "residual_change": c["overall"]["residual_change"], "z": c["overall"]["z"],
             "groups_detected": sum(g["detected"] for g in c["group_changes"]),
             "top_reason": (lambda r: f"{r['polarity']}:{r['item']} {r['change'] if r['change'] is not None else r['kind']}")(c["reason_changes"][0]) if c["reason_changes"] else "",
             "matched_events": sum(x["matches_changed_reason"] for x in c["event_candidates"]),
             "confidence": c["confidence"],
             "recovery_weeks": c["recovery"]["weeks"] if c["recovery"] else None,
             "sources": " ".join(str(s["issue"]) for s in c["sources"])} for c in cards]
    pd.DataFrame(summ).to_csv(DATA / "cases_summary.csv", index=False, encoding="utf-8-sig")
    print(f"신호: 전체 {len(ov)}건, 집단 {len(gt)}건 → 케이스 {len(cards)}개 "
          f"(전체 {sum(c['type'] == '전체' for c in cards)}, 집단 {sum(c['type'] == '집단' for c in cards)})")
    print("사건:", "검토 결과 사용" if reviewed else "미검토 자동 사건을 후보로 사용")
    # 검토 페이지에 케이스 관련 주 표시를 넣기 위해 다시 만든다
    ev.main()


if __name__ == "__main__":
    main()
