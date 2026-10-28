"""쟁점별 공개 입장 기록(0원): 주요 쟁점마다 정당별로 누가 무엇을 공개적으로 말했고, 관련 법안에 어떻게 표결했는지.

- 발언: 뉴스 사실(facts)의 '입장 표명'·'갈등'·'발의·표결 예고' 중 쟁점 키워드가 들어간 것. 기사 속 '언급된 의원'의 그 날짜 소속 정당으로 묶는다.
  주의: 사실은 언급된 의원에게 붙어 있어, 발언자가 다른 당 인사인 경우가 있다(예: 상대 당 대변인이 그 의원을 비판).
  모두 '보도' 표식 + 기사 링크. 기사에서 AI가 뽑은 요약이라 원문 확인이 필요하다.
- 표결: 법안명에 쟁점 키워드가 들어간 본회의 표결의 정당별 찬반(표결일 당시 소속, db.party_lookup).
쟁점 목록은 최근 기사에서 자주 나온 낱말을 보고 사람이 정했다(ISSUES). 새 쟁점은 여기에 추가한다.

사용: python src/stances.py              # data/stances.json 생성 후 요약 출력
"""
import json
import sys
from collections import Counter, defaultdict
from datetime import date, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from config import DATA
from db import connect, party_lookup

OUT = DATA / "stances.json"

# 쟁점: 기사 요약·법안명에서 찾을 키워드(하나라도 들어가면 해당)
ISSUES = {
    "조희대 대법원장(탄핵·국정조사)": ["조희대", "대법원장"],
    "조작기소 특검·검찰": ["조작기소", "공소취소", "검찰개혁"],
    "윤석열 재판·내란 청산": ["윤석열", "내란", "계엄"],
    "오세훈 서울시정(한강버스 등)": ["오세훈", "한강버스", "서울시장"],
    "한동훈": ["한동훈"],
    "부동산·주택 공급": ["부동산", "집값", "주택 공급", "공급 대책", "전월세"],
    "가상자산·디지털자산": ["가상자산", "디지털자산", "코인"],
    "전작권 전환·한미동맹": ["전작권", "전시작전", "한미동맹", "SCM"],
    "해킹·개인정보 유출": ["해킹", "개인정보 유출"],
    "선거 공정성(투표지·부정선거 주장)": ["투표지", "부정선거"],
    "국민연금": ["국민연금"],
    "AI·반도체 산업": ["반도체", "인공지능", "AI "],
    "북한·통일 정책": ["통일부", "북한", "대북"],
    "전기차·자동차 산업 지원": ["전기차"],
    "공공기관 이전·지역균형": ["공공기관 이전", "초광역", "균형발전"],
    "예산·재정": ["예산안", "재정", "추경"],
}
CATS = ("입장 표명", "갈등", "발의·표결 예고")
PARTY_SHORT = {"더불어민주당": "민주", "국민의힘": "국힘", "조국혁신당": "혁신", "개혁신당": "개혁", "진보당": "진보"}


def _match(text: str, kws: list[str]) -> bool:
    return any(k in text for k in kws)


def build(on: str | None = None, days: int = 60, per_party: int = 4) -> dict:
    on = on or date.today().isoformat()
    since = (date.fromisoformat(on) - timedelta(days=days)).isoformat()
    con = connect()
    party_at = party_lookup(con)
    from news import nconnect
    nc = nconnect()
    rows = nc.execute(
        """SELECT f.entity_type, f.entity_id, f.category, f.summary, f.url, a.pub_date, m.entity_name
           FROM facts f JOIN articles a ON a.url=f.url
           LEFT JOIN mentions m ON m.url=f.url AND m.entity_type=f.entity_type AND m.entity_id=f.entity_id
           WHERE a.pub_date BETWEEN ? AND ? AND f.category IN (?,?,?)
           ORDER BY a.pub_date DESC""", (since, on, *CATS)).fetchall()
    votes = con.execute("SELECT bill_id, bill_name, vote_date, yes, no FROM votes WHERE vote_date IS NOT NULL").fetchall()
    out = {"as_of": on, "window_days": days, "issues": {}}
    for issue, kws in ISSUES.items():
        by_party: dict[str, list] = defaultdict(list)
        seen = set()
        for r in rows:
            if not _match(r["summary"], kws) or (r["summary"], r["entity_id"]) in seen:
                continue
            seen.add((r["summary"], r["entity_id"]))
            if r["entity_type"] == "member":
                party = party_at(r["entity_id"], r["pub_date"]) or "미확인"
            else:
                party = "정부·기관"
            by_party[party].append({"date": r["pub_date"], "who": r["entity_name"] or r["entity_id"],
                                    "cat": r["category"], "summary": r["summary"], "url": r["url"]})
        vrecs = []
        for v in votes:
            if not _match(v["bill_name"], kws):
                continue
            cnt: dict[str, Counter] = defaultdict(Counter)
            for mv in con.execute("SELECT member_id, vote FROM member_votes WHERE bill_id=?", (v["bill_id"],)):
                p = party_at(mv["member_id"], v["vote_date"]) if mv["member_id"] else None
                cnt[p or "미확인"][mv["vote"]] += 1
            vrecs.append({"bill_id": v["bill_id"], "bill_name": v["bill_name"], "vote_date": v["vote_date"],
                          "yes": v["yes"], "no": v["no"],
                          "by_party": {p: dict(c) for p, c in cnt.items() if p in PARTY_SHORT}})
        vrecs.sort(key=lambda x: x["vote_date"], reverse=True)
        out["issues"][issue] = {
            "keywords": kws,
            "counts": {p: len(v) for p, v in sorted(by_party.items(), key=lambda kv: -len(kv[1]))},
            "statements": {p: v[:per_party] for p, v in by_party.items()},
            "votes": vrecs[:5],
        }
    OUT.write_text(json.dumps(out, ensure_ascii=False, indent=1), encoding="utf-8")
    return out


def bundle_lines(d: dict, max_issues: int = 12) -> list[tuple[str, str, str | None]]:
    """전략 근거 묶음용 (label, text, link) 목록. 언급이 많은 쟁점 순."""
    items = []
    ranked = sorted(d["issues"].items(), key=lambda kv: -sum(kv[1]["counts"].values()))
    for issue, x in ranked[:max_issues]:
        total = sum(x["counts"].values())
        if not total and not x["votes"]:
            continue
        cnt = ", ".join(f"{PARTY_SHORT.get(p, p)} {n}" for p, n in x["counts"].items())
        items.append(("보도", f"[쟁점 입장 기록] {issue} — 최근 {d['window_days']}일 관련 보도 사실 {total}건(언급 의원 소속별: {cnt}). [소속]은 언급된 의원의 정당이며 발언자와 다를 수 있음", None))
        for p in ("더불어민주당", "국민의힘", "조국혁신당", "개혁신당", "진보당", "정부·기관"):
            for s in x["statements"].get(p, [])[:3 if p in ("더불어민주당", "국민의힘") else 2]:
                items.append(("보도", f"  └ [{PARTY_SHORT.get(p, p)}] {s['date']} {s['summary']}", s["url"]))
        for v in x["votes"][:2]:
            bp = "; ".join(f"{PARTY_SHORT[p]} 찬{c.get('찬성', 0)}/반{c.get('반대', 0)}/기{c.get('기권', 0)}"
                           for p, c in v["by_party"].items())
            items.append(("기록", f"  └ [표결] {v['vote_date']} {v['bill_name']} 가결여부 찬{v['yes']}·반{v['no']} ({bp})",
                          f"https://likms.assembly.go.kr/bill/billDetail.do?billId={v['bill_id']}"))
    return items


if __name__ == "__main__":
    d = build()
    for issue, x in sorted(d["issues"].items(), key=lambda kv: -sum(kv[1]["counts"].values())):
        print(f"{issue}: 발언 {sum(x['counts'].values())} {x['counts']} · 표결 {len(x['votes'])}건")
    print(f"근거 줄 수: {len(bundle_lines(d))}")
