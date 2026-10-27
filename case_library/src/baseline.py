"""4단계 기준선 모델: 직무 긍정률의 기본 추세를 추정하고 잔차(실제 - 기준선)와 주간 변화량, 조사 오차를 저장한다.

실행 예:
    python src/baseline.py

- 대상: 직무 평가가 있는 주(제495~606호). 탄핵소추 뒤 직무 정지 기간(제607~618호)은 직무 평가가 없어 제외.
- 시간축: 취임일(2022-05-10)부터 조사 기간 가운데 날까지 경과 주 수. 조사를 쉰 주가 있어 간격이 일정하지 않다.
- 후보 모델
    log   : 긍정률 = a + b * ln(1 + 경과 주)
    exp   : 긍정률 = c + A * exp(-경과 주 / tau)
    loess : 국소 회귀(statsmodels lowess), frac 여러 개
- 선택 규칙: 창이 config 의 min_window_weeks 보다 짧은 LOESS 는 사건 효과까지 따라가므로 제외하고,
  남은 후보 중 '연속 8주 블록을 빼고 맞춘 뒤 빠진 블록을 예측'하는 교차검증 오차(RMSE)가 가장 작은 모델을 쓴다.
  전체 긍정률로 고른 모델을 모든 집단에 같은 방식으로 적용한다.
- 조사 오차: 전체는 보고서 표준오차(없으면 계산값), 집단은 sqrt(p(1-p)/n) 계산값(n = 조사완료 사례수).
  보고서 표준오차는 이 계산값의 약 0.96배(반올림 수준 차이)라서 계산값으로 대신해도 무리가 없다.
"""
from __future__ import annotations

import sqlite3
from pathlib import Path

import numpy as np
import pandas as pd
import yaml
from scipy.optimize import curve_fit
from statsmodels.nonparametric.smoothers_lowess import lowess

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "data"

SCHEMA = """
DROP TABLE IF EXISTS baseline;
CREATE TABLE baseline (
    issue INTEGER, category TEXT, subgroup TEXT, t_weeks REAL,
    n_raw INTEGER, approve REAL,
    baseline REAL, residual REAL,              -- 선택한 모델
    baseline_log REAL, residual_log REAL,      -- 비교용: 로그 감소 모델
    prev_issue INTEGER, gap_weeks REAL,        -- 직전 조사(쉰 주가 있으면 2주 이상 떨어짐)
    change REAL, residual_change REAL,         -- 직전 조사 대비 긍정률 변화, 잔차 변화
    se REAL, se_source TEXT, change_se REAL,   -- 조사 오차(표준오차, %p)와 변화량의 표준오차
    model TEXT,
    edge INTEGER,                              -- 1 = 처음/끝에서 LOESS 창 절반 안쪽(기준선이 한쪽 점만 보고 기울어질 수 있음)
    PRIMARY KEY (issue, category, subgroup)
);
"""


def load_config() -> dict:
    with open(ROOT / "config.yaml", encoding="utf-8") as f:
        return yaml.safe_load(f)


def fit_predict(kind: str, t: np.ndarray, y: np.ndarray, tp: np.ndarray) -> np.ndarray:
    if kind == "log":
        X = np.c_[np.ones_like(t), np.log1p(t)]
        b = np.linalg.lstsq(X, y, rcond=None)[0]
        return np.c_[np.ones_like(tp), np.log1p(tp)] @ b
    if kind == "exp":
        f = lambda x, c0, A, tau: c0 + A * np.exp(-x / tau)  # noqa: E731
        p, _ = curve_fit(f, t, y, p0=[np.median(y), y[0] - np.median(y), 10],
                         bounds=([0, -100, 0.5], [100, 100, 1000]), maxfev=20000)
        return f(tp, *p)
    frac = float(kind.split("_")[1])
    return lowess(y, t, frac=frac, xvals=tp)


def evaluate(kind: str, t, y, block: int) -> dict:
    fitted = fit_predict(kind, t, y, t)
    resid = y - fitted
    blocks = np.arange(len(t)) // block
    errs = []
    for b in np.unique(blocks):
        m = blocks == b
        errs += list(y[m] - fit_predict(kind, t[~m], y[~m], t[m]))
    return {"model": kind, "rmse_in_sample": float(np.sqrt(np.mean(resid ** 2))),
            "rmse_cv": float(np.sqrt(np.nanmean(np.square(errs)))),
            "resid_lag1_autocorr": float(np.corrcoef(resid[:-1], resid[1:])[0, 1])}


def loess_window_weeks(frac: float, t: np.ndarray) -> float:
    """LOESS 이웃 점 수(frac * n)가 걸치는 평균 기간(주)."""
    k = max(2, int(np.ceil(frac * len(t))))
    spans = [t[i + k - 1] - t[i] for i in range(len(t) - k + 1)]
    return float(np.mean(spans))


def main():
    cfg = load_config()["baseline"]
    con = sqlite3.connect(DATA / "weekly.sqlite")
    sv = pd.read_sql("SELECT issue, survey_start, survey_end, n_sample, approve_se FROM survey "
                     "WHERE approval_status = 'asked' ORDER BY issue", con)
    mid = pd.to_datetime(sv.survey_start) + (pd.to_datetime(sv.survey_end) - pd.to_datetime(sv.survey_start)) / 2
    sv["t_weeks"] = (mid - pd.Timestamp("2022-05-10")).dt.days / 7
    ap = pd.read_sql("SELECT issue, category, subgroup, n_raw, approve FROM approval_by_group "
                     "WHERE category NOT LIKE '기타:%'", con)
    df = ap.merge(sv[["issue", "t_weeks", "approve_se"]], on="issue")

    # ---- 모델 비교(전체 긍정률) ----
    total = df[df.category == "전체"].sort_values("t_weeks")
    t, y = total.t_weeks.values, total.approve.values
    kinds = ["log", "exp"] + [f"loess_{f}" for f in cfg["loess_fracs"]]
    rows = []
    for k in kinds:
        r = evaluate(k, t, y, cfg["cv_block_weeks"])
        if k.startswith("loess"):
            r["window_weeks"] = round(loess_window_weeks(float(k.split("_")[1]), t), 1)
            r["eligible"] = r["window_weeks"] >= cfg["min_window_weeks"]
        else:
            r["window_weeks"] = None
            r["eligible"] = True
        rows.append(r)
    comp = pd.DataFrame(rows)
    chosen = comp[comp.eligible].sort_values("rmse_cv").iloc[0]["model"]
    comp["chosen"] = comp.model == chosen
    win = comp.loc[comp.chosen, "window_weeks"].iloc[0]
    half = 0.0 if pd.isna(win) else win / 2

    # ---- 집단별로 같은 모델 적용 ----
    n_weeks = total.issue.nunique()
    out = []
    group_eval = []
    for (cat, sub), g in df.groupby(["category", "subgroup"]):
        g = g.dropna(subset=["approve"]).sort_values("t_weeks")
        if len(g) < cfg["min_coverage"] * n_weeks:
            continue
        tt, yy = g.t_weeks.values, g.approve.values
        base = fit_predict(chosen, tt, yy, tt)
        base_log = fit_predict("log", tt, yy, tt)
        p = yy / 100
        se_calc = np.sqrt(p * (1 - p) / g.n_raw.values) * 100
        if cat == "전체":
            se = np.where(g.approve_se.notna(), g.approve_se, se_calc)
            src = np.where(g.approve_se.notna(), "report", "computed")
        else:
            se, src = se_calc, np.array(["computed"] * len(g))
        g = g.assign(baseline=base, residual=yy - base, baseline_log=base_log, residual_log=yy - base_log,
                     se=se, se_source=src)
        g["prev_issue"] = g.issue.shift(1)
        g["gap_weeks"] = g.t_weeks.diff()
        g["change"] = g.approve.diff()
        g["residual_change"] = g.residual.diff()
        g["change_se"] = np.sqrt(g.se ** 2 + g.se.shift(1) ** 2)
        g["model"] = chosen
        g["edge"] = ((g.t_weeks < tt.min() + half) | (g.t_weeks > tt.max() - half)).astype(int)
        out.append(g)
        if cat != "전체":
            for k in ("log", chosen):
                e = evaluate(k, tt, yy, cfg["cv_block_weeks"])
                group_eval.append({"category": cat, "subgroup": sub, **e})

    res = pd.concat(out)
    con.executescript(SCHEMA)
    cols = ["issue", "category", "subgroup", "t_weeks", "n_raw", "approve", "baseline", "residual",
            "baseline_log", "residual_log", "prev_issue", "gap_weeks", "change", "residual_change",
            "se", "se_source", "change_se", "model", "edge"]
    res[cols].to_sql("baseline", con, if_exists="append", index=False)
    con.commit()

    comp.to_csv(DATA / "baseline_model_comparison.csv", index=False, encoding="utf-8-sig")
    ge = pd.DataFrame(group_eval)
    ge.to_csv(DATA / "baseline_group_eval.csv", index=False, encoding="utf-8-sig")
    write_report(comp, chosen, ge, res, cfg, half)
    print(comp.round(2).to_string(index=False))
    print(f"선택: {chosen} / 기준선을 만든 집단 {res.groupby(['category', 'subgroup']).ngroups}개, 행 {len(res)}개")


def write_report(comp, chosen, ge, res, cfg, half):
    tot = res[res.category == "전체"]
    lines = [
        "# 4단계 기준선 모델 보고",
        "",
        f"- 대상: 직무 평가가 있는 {len(tot)}주(제{int(tot.issue.min())}~{int(tot.issue.max())}호)",
        f"- 선택 모델: **{chosen}**",
        "",
        "## 전체 긍정률 모델 비교",
        "",
        "| 모델 | 창(주) | 표본 내 RMSE | 교차검증 RMSE | 잔차 1차 자기상관 | 후보 자격 |",
        "|---|---|---|---|---|---|",
    ]
    for _, r in comp.iterrows():
        w = "-" if pd.isna(r.window_weeks) else f"{r.window_weeks:g}"
        mark = " ← 선택" if r.chosen else ""
        lines.append(f"| {r.model}{mark} | {w} | {r.rmse_in_sample:.2f} | {r.rmse_cv:.2f} | "
                     f"{r.resid_lag1_autocorr:.2f} | {'예' if r.eligible else f'아니오(창 {cfg['min_window_weeks']}주 미만)'} |")
    if len(ge):
        med = ge.groupby("model")[["rmse_cv", "resid_lag1_autocorr"]].median()
        lines += ["", "## 집단별(전체 제외) 교차검증 RMSE 중앙값", "",
                  "| 모델 | 교차검증 RMSE 중앙값 | 잔차 자기상관 중앙값 |", "|---|---|---|"]
        for m, r in med.iterrows():
            lines.append(f"| {m} | {r.rmse_cv:.2f} | {r.resid_lag1_autocorr:.2f} |")
    edge = tot[tot.edge == 1]
    lines += ["", "## 기준선 가장자리", "",
              f"- LOESS는 처음과 끝에서 이웃 점이 한쪽에만 있어 기준선이 기울어질 수 있다. 창 절반({half:.1f}주) 안쪽 "
              f"{len(edge)}주(제{', '.join(str(int(i)) for i in edge.issue)}호)에 edge=1 표시.",
              f"- 예: 취임 첫 주 실제 {tot.approve.iloc[0]:g}% vs 기준선 {tot.baseline.iloc[0]:.1f}% "
              "(바로 뒤 급락 구간에 끌려 올라감). 이 구간의 잔차는 신뢰도를 낮춰 해석한다."]
    lines += ["", "## 조사 오차", "",
              f"- 전체 긍정률 표준오차: 보고서 값 {int((tot.se_source == 'report').sum())}주, "
              f"계산값 {int((tot.se_source == 'computed').sum())}주 (보고서 값이 회전된 페이지라 못 읽은 주)",
              f"- 전체 긍정률 표준오차 범위: {tot.se.min():.1f}~{tot.se.max():.1f}%p, "
              f"주간 변화량 표준오차 중앙값 {tot.change_se.median():.1f}%p"]
    (DATA / "baseline_report.md").write_text("\n".join(lines) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
