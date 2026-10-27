"""7단계 결과 페이지: 모든 결과를 report.html 한 파일로 묶는다(외부 서버·라이브러리 없이 더블클릭으로 열림).

실행 예:
    python src/report.py
"""
from __future__ import annotations

import csv
import datetime as dt
import json
import sqlite3
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "data"


def main():
    con = sqlite3.connect(DATA / "weekly.sqlite")
    with open(DATA / "manifest.csv", encoding="utf-8-sig") as f:
        man = {int(r["issue"]): r for r in csv.DictReader(f) if r["issue"]}
    sv = pd.read_sql("SELECT issue, week_label, survey_start, survey_end, n_sample, approval_status FROM survey ORDER BY issue", con)
    sources = {int(r.issue): {"week": r.week_label, "period": f"{r.survey_start}~{r.survey_end}", "n": int(r.n_sample),
                              "url": f"https://www.gallup.co.kr/gallupdb/reportContent.asp?seqNo={man[r.issue]['seq_no']}",
                              "pdf": man[r.issue]["pdf_url"], "asked": r.approval_status == "asked"}
               for r in sv.itertuples()}

    b = pd.read_sql("SELECT * FROM baseline", con)
    tot = b[b.category == "전체"].sort_values("t_weeks")
    overall = [{"issue": int(r.issue), "t": round(r.t_weeks, 2), "y": r.approve, "b": round(r.baseline, 2),
                "se": round(r.se, 2), "edge": int(r.edge)} for r in tot.itertuples()]
    issues = [int(i) for i in tot.issue]
    cat_order = ["권역", "성", "연령", "지지정당", "이념성향", "직업", "생활수준", "정치관심도"]
    rows = sorted({(c, s) for c, s in zip(b.category, b.subgroup) if c != "전체"},
                  key=lambda x: (cat_order.index(x[0]) if x[0] in cat_order else 99, x[1]))
    rows = [("전체", "전체")] + rows
    look = {(r.issue, r.category, r.subgroup): r for r in b.itertuples()}
    heat = {"issues": issues, "rows": [{"cat": c, "sub": s} for c, s in rows],
            "values": [[None if (i, c, s) not in look else round(look[(i, c, s)].residual, 1) for i in issues] for c, s in rows],
            "approve": [[None if (i, c, s) not in look else look[(i, c, s)].approve for i in issues] for c, s in rows],
            "n": [[None if (i, c, s) not in look else int(look[(i, c, s)].n_raw) for i in issues] for c, s in rows]}

    cases = json.loads((DATA / "cases.json").read_text(encoding="utf-8"))
    for c in cases:
        c.pop("event_weeks", None)
        for e in c["event_candidates"]:
            e.pop("reviewed", None)

    bt_text = (DATA / "backtest_report.md").read_text(encoding="utf-8")
    bt_first = bt_text.split("\n", 1)[0].strip("* ")
    bt = pd.read_csv(DATA / "backtest_results.csv")
    with open(DATA / "backtest_report.md", encoding="utf-8") as f:
        bt_lines = f.read().splitlines()
    table = [l for l in bt_lines if l.startswith("| ") and not l.startswith("| 범위") and not l.startswith("|---")]
    bt_rows = [dict(zip(["scope", "h", "method", "n", "dir", "mae"], [x.strip() for x in l.strip("|").split("|")])) for l in table]
    cov = [l[2:] for l in bt_lines if l.startswith("- ") and ("비율" in l or "즉 " in l)]
    bt_cases = sorted(bt[bt.pred_analog.notna()].case_id.unique().tolist())

    base_txt = (DATA / "baseline_report.md").read_text(encoding="utf-8")
    model_line = next((l for l in base_txt.splitlines() if l.startswith("- 선택 모델")), "")
    with open(DATA / "parse_failures.csv", encoding="utf-8-sig") as f:
        n_fail = sum(1 for _ in csv.DictReader(f))
    reviewed = (DATA / "events_reviewed.csv").exists()

    meta = {
        "generated": dt.date.today().isoformat(),
        "n_reports": len(sv), "n_asked": int((sv.approval_status == "asked").sum()),
        "first_issue": int(sv.issue.min()), "last_issue": int(sv.issue.max()),
        "n_parse_fail": n_fail, "n_cases": len(cases),
        "n_cases_overall": sum(c["type"] == "전체" for c in cases),
        "model": model_line.replace("- 선택 모델: ", "").replace("*", ""),
        "events_reviewed": reviewed,
        "n_events": sum(1 for _ in open(DATA / "events.csv", encoding="utf-8-sig")) - 1,
        "bt_first": bt_first, "bt_rows": bt_rows, "bt_cov": cov, "bt_cases": len(bt_cases),
    }
    payload = {"meta": meta, "overall": overall, "heat": heat, "cases": cases, "sources": sources}
    tpl = (ROOT / "src" / "report_template.html").read_text(encoding="utf-8")
    out = tpl.replace("/*__DATA__*/null", json.dumps(payload, ensure_ascii=False, separators=(",", ":")))
    (ROOT / "report.html").write_text(out, encoding="utf-8")
    print(f"report.html {len(out.encode()) / 1e6:.1f}MB")


if __name__ == "__main__":
    main()
