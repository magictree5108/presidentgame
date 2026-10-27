"""4단계 확인용 그래프: 전체 직무 긍정률, 선택 기준선(LOESS), 비교용 로그 감소 기준선. data/baseline_chart.html 로 저장."""
import json
import sqlite3
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
con = sqlite3.connect(ROOT / "data" / "weekly.sqlite")
rows = con.execute("""SELECT b.issue, s.week_label, b.t_weeks, b.approve, b.baseline, b.baseline_log, b.edge, b.se
                      FROM baseline b JOIN survey s USING(issue) WHERE b.category='전체' ORDER BY b.t_weeks""").fetchall()
data = [dict(zip(["issue", "week", "t", "y", "b", "bl", "edge", "se"], r)) for r in rows]
html = (ROOT / "src" / "baseline_chart_template.html").read_text(encoding="utf-8")
(ROOT / "data" / "baseline_chart.html").write_text(html.replace("/*__DATA__*/[]", json.dumps(data, ensure_ascii=False)),
                                                   encoding="utf-8")
