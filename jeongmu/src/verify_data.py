"""2단계 검증표 만들기 → docs/verification.md

1) 오늘 기준 정당별 의석수(DB 계산값) — 국회 홈페이지 공식 수치를 옆 칸에 사람이 적어 대조
2) 무작위 법안 5건의 진행 단계 — 의안정보시스템 링크를 열어 화면과 대조
사용: python src/verify_data.py [--seed 숫자]
"""
import argparse
import random
import sys
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from config import DOCS
from db import connect, seats_on


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--seed", type=int, default=int(date.today().strftime("%Y%m%d")))
    a = ap.parse_args()
    con = connect()
    s = seats_on(con)
    lines = [f"# 데이터 대조 검증표 ({s['date']})", "",
             "## 1. 정당별 의석수", "",
             "공식 수치: 국회 홈페이지(assembly.go.kr) 의석 현황을 보고 '공식' 칸을 채운다.", "",
             "| 정당 | DB 계산 | 공식 | 일치 |", "|---|---|---|---|"]
    for p, n in s["by_party"].items():
        lines.append(f"| {p} | {n} |  |  |")
    lines += [f"| 합계(재적) | {s['total']} |  |  |", f"| 공석 | {s['vacant']} |  |  |"]
    if s["unknown_party"]:
        lines.append(f"\n당적 미확인 의원 {len(s['unknown_party'])}명: {', '.join(s['unknown_party'])}")
    rows = con.execute("SELECT bill_id, bill_no, bill_name, stage, proc_result, detail_link FROM bills").fetchall()
    lines += ["", f"## 2. 무작위 법안 5건 진행 단계 (seed {a.seed})", "",
              "| 의안번호 | 법안 | DB 단계 | DB 처리결과 | 의안정보시스템 | 일치 |", "|---|---|---|---|---|---|"]
    for r in random.Random(a.seed).sample(rows, min(5, len(rows))):
        lines.append(f"| {r['bill_no']} | {r['bill_name']} | {r['stage']} | {r['proc_result'] or ''} | "
                     f"{'[열기](' + r['detail_link'] + ')' if r['detail_link'] else ''} |  |")
    DOCS.mkdir(exist_ok=True)
    (DOCS / "verification.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    print("\n".join(lines))


if __name__ == "__main__":
    main()
