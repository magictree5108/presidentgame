"""6단계 역검증: 각 케이스 시점에 서서, 그보다 앞서 끝난 케이스만으로 다음 1~2주 집단별 변화를 예측해 본다.

실행 예:
    python src/backtest.py

설계
- 서 있는 시점 = 케이스 시작 주(기준 주 다음 조사). 이때 알 수 있는 것: 기준 주→시작 주의 긍정률 변화(첫 움직임)와
  평가 이유 변화. 예측 대상: 시작 주 → 그 뒤 h번째 조사(h=1,2)의 집단별 직무 긍정률 변화.
- 미래 정보 누설 방지: LOESS 기준선은 앞뒤 데이터를 다 쓰므로 여기서는 잔차 대신 '실제 긍정률 변화'를 예측한다.
  유사 사례로는 시작 주보다 먼저 끝난 케이스만 쓴다.
- 유사도: 기준 주→시작 주 사이 3%p 이상 바뀐 평가 이유의 (정책 분야 집합 Jaccard + 항목 집합 Jaccard) / 2.
- 유사 사례 예측: 가장 비슷한 k개 과거 케이스에서 같은 집단의 '시작 주 → h번째 뒤' 변화를 첫 움직임 방향에 맞춰
  (과거 케이스 방향 × 변화) 평균한 뒤 현재 첫 움직임 방향을 곱한다. 범위(최소~최대)도 함께 낸다.
- 비교 기준: 변화 없음(0), 직전 추세 연장(첫 움직임 × h).
- 지표: 방향 적중률(변화가 잡음 범위 안이면 '변화 없음'으로 보는 3분류), 평균 절대오차(%p), 범위 적중률.

한계: 케이스 시점 자체는 전체 기간 잔차로 고른 것이라, '움직임이 시작된 줄 안다'는 조건부 평가다.
"""
from __future__ import annotations

import json
import sqlite3
from pathlib import Path

import numpy as np
import pandas as pd
import yaml

import events as ev

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "data"


def jaccard(a: set, b: set) -> float:
    return len(a & b) / len(a | b) if a | b else 0.0


def reason_features(reasons: pd.DataFrame, a: int, s: int, thr: float):
    items, doms = set(), set()
    for pol in ("positive", "negative"):
        A = reasons[(reasons.issue == a) & (reasons.polarity == pol)]
        S = reasons[(reasons.issue == s) & (reasons.polarity == pol)]
        pa = dict(zip(A.item.str.replace(" ", ""), A.pct))
        ps = dict(zip(S.item.str.replace(" ", ""), S.pct))
        for k in set(pa) | set(ps):
            if k in ("기타", "모름/응답거절"):
                continue
            if abs(ps.get(k, 0) - pa.get(k, 0)) >= thr and (k in pa or ps.get(k, 0) >= thr):
                direction = "+" if ps.get(k, 0) > pa.get(k, 0) else "-"
                items.add(f"{pol}:{k}:{direction}")
                d, _ = ev.classify(k)
                if d != "기타":
                    doms.add(d)
    return items, doms


def direction(x: float, noise: float) -> int:
    return 0 if abs(x) < noise else int(np.sign(x))


def main():
    cfg_all = yaml.safe_load(open(ROOT / "config.yaml", encoding="utf-8"))
    cfg, thr = cfg_all["backtest"], cfg_all["cases"]["reason_change_pp"]
    con = sqlite3.connect(DATA / "weekly.sqlite")
    b = pd.read_sql("SELECT issue, category, subgroup, t_weeks, approve, se FROM baseline", con)
    reasons = pd.read_sql("SELECT issue, polarity, item, pct FROM reasons", con)
    cases = [c for c in json.loads((DATA / "cases.json").read_text(encoding="utf-8")) if c["type"] == "전체"]
    order = sorted(b[b.category == "전체"].issue.unique())
    pos = {i: n for n, i in enumerate(order)}
    val = {(r.issue, r.category, r.subgroup): (r.approve, r.se) for r in b.itertuples()}
    groups = sorted(set(zip(b.category, b.subgroup)))

    # 케이스별 특징과 '시작 주 → h번째 뒤' 변화
    info = []
    for c in cases:
        a, s = c["reference_issue"], c["start_issue"]
        items, doms = reason_features(reasons, a, s, thr)
        first = val[(s, "전체", "전체")][0] - val[(a, "전체", "전체")][0]
        resp = {}
        for h in cfg["horizons"]:
            j = pos[s] + h
            if j >= len(order):
                continue
            t = order[j]
            for g in groups:
                if (s, *g) in val and (t, *g) in val and (a, *g) in val:
                    v0, se0 = val[(s, *g)]
                    v1, se1 = val[(t, *g)]
                    va, _ = val[(a, *g)]
                    resp[(h, g)] = {"actual": v1 - v0, "first": v0 - va, "se": float(np.sqrt(se0 ** 2 + se1 ** 2)),
                                    "target_issue": int(t)}
        info.append({"case": c, "a": a, "s": s, "end": c["end_issue"], "items": items, "doms": doms,
                     "sign": int(np.sign(first)) or 1, "first": first, "resp": resp})

    rows = []
    for cur in info:
        past = [p for p in info if pos[p["end"]] < pos[cur["s"]]]
        sims = sorted(((0.5 * jaccard(cur["doms"], p["doms"]) + 0.5 * jaccard(cur["items"], p["items"]), p)
                       for p in past), key=lambda x: -x[0])
        analogs = [(sm, p) for sm, p in sims if sm >= cfg["min_similarity"]][:cfg["k_analogs"]]
        for (h, g), r in cur["resp"].items():
            preds = [p["sign"] * p["resp"][(h, g)]["actual"] for _, p in analogs if (h, g) in p["resp"]]
            analog = cur["sign"] * float(np.mean(preds)) if preds else None
            lo = hi = None
            if preds:
                vals = [cur["sign"] * x for x in preds]
                lo, hi = min(vals), max(vals)
            rows.append({
                "case_id": cur["case"]["case_id"], "start_issue": cur["s"], "target_issue": r["target_issue"],
                "horizon": h, "category": g[0], "subgroup": g[1], "actual": round(r["actual"], 1),
                "noise": round(cfg["noise_z"] * r["se"], 2),
                "pred_analog": None if analog is None else round(analog, 2),
                "analog_lo": lo, "analog_hi": hi, "n_analogs": len(preds),
                "analogs": " ".join(f"{p['case']['case_id']}({sm:.2f})" for sm, p in analogs),
                "pred_nochange": 0.0, "pred_trend": round(r["first"] * h, 2),
            })
    df = pd.DataFrame(rows)
    df.to_csv(DATA / "backtest_results.csv", index=False, encoding="utf-8-sig")

    ev_df = df[df.pred_analog.notna()].copy()
    methods = {"유사 사례 평균": "pred_analog", "변화 없음": "pred_nochange", "직전 추세 연장": "pred_trend"}
    summary = []
    for scope, sub in (("전체 긍정률", ev_df[ev_df.category == "전체"]), ("집단(34개)", ev_df[ev_df.category != "전체"])):
        for h in cfg["horizons"]:
            sh = sub[sub.horizon == h]
            if sh.empty:
                continue
            act_dir = [direction(x, n) for x, n in zip(sh.actual, sh.noise)]
            for name, col in methods.items():
                pdir = [direction(x, n) for x, n in zip(sh[col], sh.noise)]
                summary.append({"범위": scope, "h": h, "방법": name, "건수": len(sh),
                                "방향 적중률": float(np.mean([p == q for p, q in zip(pdir, act_dir)])),
                                "평균 절대오차": float(np.mean(np.abs(sh[col] - sh.actual)))})
    sm = pd.DataFrame(summary)
    cover = ev_df[ev_df.n_analogs >= 2]
    coverage = float(np.mean((cover.actual >= cover.analog_lo) & (cover.actual <= cover.analog_hi))) if len(cover) else None
    half = (cover.analog_hi - cover.analog_lo) / 2
    coverage_zero = float(np.mean((cover.actual >= -half) & (cover.actual <= half))) if len(cover) else None
    write_report(sm, df, ev_df, coverage, coverage_zero, len(cover), info)
    print(sm.round(3).to_string(index=False))


def write_report(sm, df, ev_df, coverage, coverage_zero, n_cover, info):
    # 첫 줄: 유사 사례 예측이 단순 기준보다 못한 경우를 그대로 쓴다
    worse_mae, worse_dir = [], []
    for (scope, h), g in sm.groupby(["범위", "h"], sort=False):
        a = g[g["방법"] == "유사 사례 평균"].iloc[0]
        o = g[g["방법"] != "유사 사례 평균"]
        if o["평균 절대오차"].min() < a["평균 절대오차"]:
            worse_mae.append(f"{scope} {h}주 뒤")
        if o["방향 적중률"].max() > a["방향 적중률"]:
            worse_dir.append(f"{scope} {h}주 뒤")
    n_all = sm.groupby(["범위", "h"]).ngroups
    if worse_mae or worse_dir:
        first = (f"**유사 사례 예측은 단순 기준보다 못했다. 평균 절대오차는 {n_all}개 범위 중 {len(worse_mae)}개에서 "
                 f"'변화 없음'이 더 작았고, 방향 적중률은 {n_all}개 중 {len(worse_dir)}개에서 단순 기준이 더 높았다.**")
    else:
        first = "**유사 사례 예측이 모든 범위에서 단순 기준보다 나았다.**"
    n_cases = len(info)
    n_eval = ev_df.case_id.nunique()
    lines = [
        first,
        "",
        "# 6단계 역검증 보고",
        "",
        f"- 대상: '전체' 케이스 {n_cases}개 중 앞서 끝난 비슷한 케이스가 있어 예측할 수 있었던 {n_eval}개 "
        f"(나머지 {n_cases - n_eval}개는 비교할 과거 케이스 없음)",
        "- 예측: 케이스 시작 주에 서서 다음 1·2번째 조사의 직무 긍정률 변화(%p)를 전체와 집단 34개에 대해 예측",
        "- 방향 적중: 변화가 잡음 범위(변화량 표준오차 1배) 안이면 '변화 없음'으로 보고 상승/변화 없음/하락 3분류로 비교",
        "",
        "| 범위 | 몇 주 뒤 | 방법 | 건수 | 방향 적중률 | 평균 절대오차(%p) |",
        "|---|---|---|---|---|---|",
    ]
    for _, r in sm.iterrows():
        lines.append(f"| {r['범위']} | {r.h} | {r['방법']} | {r['건수']} | {r['방향 적중률']:.0%} | {r['평균 절대오차']:.2f} |")
    lines += ["", "## 과거 유사 사례로 '범위'를 보여주는 방식은 쓸모 있나", ""]
    if coverage is not None:
        lines += [
            f"- 유사 사례가 2개 이상인 {n_cover}건에서 실제 변화가 유사 사례들의 최소~최대 범위 안에 든 비율: {coverage:.0%}",
            f"- 같은 폭의 범위를 0(변화 없음) 중심에 놓았을 때 든 비율: {coverage_zero:.0%}",
            "- 즉 범위가 맞은 것은 범위의 폭(1주 잡음 크기) 덕분이고, 유사 사례가 범위의 위치를 더 잘 잡아 준 증거는 없다.",
            "  지금 형태로는 '이 정도 폭으로 흔들릴 수 있다'는 잡음 크기 안내 이상의 쓸모를 확인하지 못했다.",
        ]
    lines += [
        "",
        "## 한계와 다음에 해 볼 것",
        "",
        "- 케이스 시점은 전체 기간 잔차로 고른 것이라 '움직임이 시작된 걸 안다'는 조건부 평가다. 실제 실시간 예측보다 유리한 조건인데도 못했다.",
        "- 과거 사례가 적다(케이스 22개, 앞쪽 케이스일수록 비교할 과거가 거의 없음).",
        "- 유사도는 평가 이유 변화로만 쟀다. 사람이 검토한 사건 정보(정책 분야)를 넣으면 달라질 수 있다.",
        "- 집단 표본이 100~300명이라 1주 변화의 잡음(±3~6%p)이 크다. 1~2주 뒤 집단별 변화는 잡음이 신호보다 크다.",
        "- 다른 정부(문재인·박근혜 등)로 사례를 늘리면 유사 사례 풀이 커져 다시 평가할 가치가 있다.",
    ]
    (DATA / "backtest_report.md").write_text("\n".join(lines) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
