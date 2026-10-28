"""2단계 검증표 → docs/verification.md

1) 오늘 기준 정당별 의석수: DB 계산값 vs 열린국회정보 '정당 및 교섭단체 의석수 현황'(공식)
2) 무작위 법안 5건: DB 처리결과 vs 의안정보시스템(likms) 상세 화면의 '의결결과'
사용: python src/verify_data.py [--seed 숫자]
"""
import argparse
import html
import random
import re
import sys
from datetime import date
from pathlib import Path

import requests

sys.path.insert(0, str(Path(__file__).parent))

import assembly_api as api
from api_fields import SERVICES
from config import DOCS
from db import connect, seats_on

LIKMS = "https://likms.assembly.go.kr/bill/billDetail.do?billId="


def likms_result(session, bill_id: str) -> str | None:
    """의안정보시스템 상세 화면의 '의결결과' 칸. 비어 있으면 ''(계류), 접속 실패면 None."""
    for _ in range(4):
        try:
            t = session.get(LIKMS + bill_id, headers=api.HEADERS, timeout=(10, 40)).text
            break
        except requests.RequestException:
            continue
    else:
        return None
    t = re.sub(r"<script.*?</script>", "", t, flags=re.S)
    t = html.unescape(re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", t)))
    m = re.search(r"의결결과\s*(\S*)", t)
    if not m:
        return None
    v = m.group(1)
    return "" if v in ("관심법률안", "") else v


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--seed", type=int, default=int(date.today().strftime("%Y%m%d")))
    a = ap.parse_args()
    con = connect()
    s = seats_on(con)
    try:
        off = {r["POLY_NM"]: int(r["N3"]) for r in api.fetch_all(SERVICES["seat_status"]["code"], {}, use_cache=False)}
    except api.AssemblyAPIError as e:
        off = {}
        print(f"공식 의석수 조회 실패: {e}")
    lines = [f"# 데이터 대조 검증표 ({s['date']})", "",
             "## 1. 정당별 의석수", "",
             "공식: 열린국회정보 「정당 및 교섭단체 의석수 현황」(nepjpxkkabqiqpbvk) — 국회 홈페이지 교섭단체 의석수 현황과 같은 값", "",
             "| 정당 | DB 계산 | 공식 | 일치 |", "|---|---|---|---|"]
    ok_all = True
    for p in sorted(set(s["by_party"]) | (set(off) - {"합계"}), key=lambda x: -s["by_party"].get(x, 0)):
        d, o = s["by_party"].get(p, 0), off.get(p)
        ok = o is not None and d == o
        ok_all &= ok
        lines.append(f"| {p} | {d} | {o if o is not None else '—'} | {'O' if ok else 'X'} |")
    ok = off.get("합계") == s["total"]
    ok_all &= ok
    lines += [f"| 합계(재적) | {s['total']} | {off.get('합계', '—')} | {'O' if ok else 'X'} |",
              "", f"**결과: {'전부 일치' if ok_all else '불일치 있음'}**"]

    rows = con.execute("SELECT bill_id, bill_no, bill_name, stage, proc_result FROM bills").fetchall()
    sess = requests.Session()
    lines += ["", f"## 2. 무작위 법안 5건 처리결과 (seed {a.seed})", "",
              "의안정보시스템 상세 화면의 '의결결과' 칸과 DB 처리결과를 비교(빈칸 = 아직 결과 없음)", "",
              "| 의안번호 | 법안 | DB 단계 | DB 처리결과 | 의안정보시스템 의결결과 | 일치 |", "|---|---|---|---|---|---|"]
    n_ok = 0
    sample = random.Random(a.seed).sample(rows, min(5, len(rows)))
    for r in sample:
        web = likms_result(sess, r["bill_id"])
        db = r["proc_result"] or ""
        ok = web is not None and web == db
        n_ok += ok
        lines.append(f"| [{r['bill_no']}]({LIKMS}{r['bill_id']}) | {r['bill_name']} | {r['stage']} | {db} | "
                     f"{'접속 실패' if web is None else web} | {'O' if ok else 'X'} |")
    lines += ["", f"**결과: {n_ok}/{len(sample)} 일치**"]
    DOCS.mkdir(exist_ok=True)
    (DOCS / "verification.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    print("\n".join(lines))


if __name__ == "__main__":
    main()
