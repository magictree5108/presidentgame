"""여론조사 수치 수집(보도 기반).

원칙: 중앙선거여론조사심의위원회(nesdc.go.kr)는 자동 수집하지 않는다. 언론 보도에 나온 수치만, 기사 링크와 '보도' 표식을 붙여 저장한다.
기사 본문은 저장하지 않는다(제목·요약문으로 AI가 수치만 뽑음).

사용:
  python src/polls.py collect --dry-run   # 검색만, AI 추출 대상 건수와 예상 비용(0원)
  python src/polls.py collect             # 허락받은 뒤: 싼 모델(Haiku)로 수치 추출
  python src/polls.py show                # 저장된 추이 요약
"""
import argparse
import json
import re
import sqlite3
import sys
from datetime import date, datetime
from email.utils import parsedate_to_datetime
from pathlib import Path
from urllib.parse import urlparse

sys.path.insert(0, str(Path(__file__).parent))

from config import DATA
from news import clean, search

DB = DATA / "polls.sqlite"
QUERIES = ["대통령 국정 지지율 여론조사", "이재명 지지율", "민주당 지지율", "국민의힘 지지율",
           "정당 지지율 갤럽", "정당 지지율 리얼미터", "차기 대권 지지율", "한동훈 지지율",
           "오세훈 지지율", "조국혁신당 지지율", "개혁신당 지지율", "지지율 하락 원인"]
PAGES = 10  # 검색어당 100건 x 10쪽(네이버 최대 1000건)
SCHEMA = """
CREATE TABLE IF NOT EXISTS poll_articles (url TEXT PRIMARY KEY, title TEXT, pub_date TEXT, press_domain TEXT,
  query TEXT, extracted INTEGER DEFAULT 0, collected_at TEXT);
CREATE TABLE IF NOT EXISTS poll_values (
  url TEXT, pollster TEXT, field_end TEXT, sample INTEGER, target_kind TEXT, target TEXT, value REAL,
  pub_date TEXT, label TEXT DEFAULT '보도', PRIMARY KEY(url, pollster, field_end, target_kind, target));
"""
POLL_HINT = re.compile(r"\d+(\.\d+)?\s*%|지지율|여론조사")

EXTRACT_SYSTEM = """너는 여론조사 수치 기록원이다. 기사 제목과 요약문에 '명시된' 여론조사 수치만 뽑는다.
- target_kind: 대통령국정(대통령 직무 긍정률), 정당, 인물(대권주자 등), 기타
- target: 대통령국정이면 '긍정' 또는 '부정', 정당이면 정당명, 인물이면 이름
- pollster: 조사기관(한국갤럽, 리얼미터, NBS(엠브레인·케이스탯·코리아리서치·한국리서치) 등). 없으면 '미상'
- field_end: 조사 마지막 날 YYYY-MM-DD(본문에 없으면 빈 문자열), sample: 표본 수(없으면 0)
- value: 퍼센트 숫자
수치가 없거나 추측이 필요하면 빈 목록. 숫자를 만들지 않는다."""
EXTRACT_SCHEMA = {
    "type": "object", "additionalProperties": False, "required": ["values"],
    "properties": {"values": {"type": "array", "items": {
        "type": "object", "additionalProperties": False,
        "required": ["pollster", "field_end", "sample", "target_kind", "target", "value"],
        "properties": {"pollster": {"type": "string"}, "field_end": {"type": "string"},
                       "sample": {"type": "integer"},
                       "target_kind": {"type": "string", "enum": ["대통령국정", "정당", "인물", "기타"]},
                       "target": {"type": "string"}, "value": {"type": "number"}}}}},
}


def pconnect():
    con = sqlite3.connect(str(DB))
    con.row_factory = sqlite3.Row
    con.executescript(SCHEMA)
    return con


def collect(dry_run: bool, budget_usd: float | None = None) -> dict:
    """budget_usd: 이번 실행의 AI 비용 상한. 닿으면 즉시 멈춘다(이미 처리한 건 저장됨, 다시 돌리면 이어서)."""
    con = pconnect()
    seen, todo = set(), []
    stats = {"queries": 0, "results": 0, "candidates": 0, "new": 0, "extracted": 0, "values": 0}
    for q in QUERIES:
        for page in range(PAGES):
            try:
                items = search(q, display=100, start=1 + page * 100)
            except Exception as e:
                print(f"검색 실패 {q} p{page}: {e}")
                break
            stats["queries"] += 1
            stats["results"] += len(items)
            for it in items:
                url = it.get("originallink") or it.get("link")
                if url in seen:
                    continue
                seen.add(url)
                title, desc = clean(it.get("title")), clean(it.get("description"))
                if not POLL_HINT.search(title + " " + desc):
                    continue
                stats["candidates"] += 1
                if con.execute("SELECT extracted FROM poll_articles WHERE url=?", (url,)).fetchone():
                    continue
                stats["new"] += 1
                try:
                    pub = parsedate_to_datetime(it["pubDate"]).date().isoformat()
                except Exception:
                    pub = None
                todo.append((url, title, desc, pub, q))
            if len(items) < 100:
                break
    if dry_run:
        return stats
    from llm import CHEAP_MODEL, call_json, cost_usd
    todo.sort(key=lambda x: x[3] or "", reverse=True)  # 최근 기사부터
    spent = 0.0
    import llm as _llm
    _orig_log = _llm.log_usage

    def _track(purpose, usage, run_id=None, model=_llm.MODEL):
        nonlocal spent
        spent += cost_usd(usage, model)
        return _orig_log(purpose, usage, run_id, model)
    _llm.log_usage = _track
    for url, title, desc, pub, q in todo:
        if budget_usd is not None and spent >= budget_usd:
            print(f"예산 상한 ${budget_usd} 도달 → 중단 (사용 ${spent:.4f})")
            stats["stopped_by_budget"] = True
            break
        con.execute("INSERT OR IGNORE INTO poll_articles(url,title,pub_date,press_domain,query,collected_at) VALUES(?,?,?,?,?,?)",
                    (url, title, pub, urlparse(url).netloc, q, datetime.now().isoformat(timespec="seconds")))
        try:
            out = call_json(EXTRACT_SYSTEM, f"제목: {title}\n요약문: {desc}\n기사 날짜: {pub}", EXTRACT_SCHEMA,
                            purpose="poll_extract", effort="low", max_tokens=2000, model=CHEAP_MODEL)
        except Exception as e:
            print(f"추출 실패: {e}")
            continue
        for v in out["values"]:
            if not (0 < v["value"] <= 100):
                continue
            con.execute("INSERT OR IGNORE INTO poll_values(url,pollster,field_end,sample,target_kind,target,value,pub_date) "
                        "VALUES(?,?,?,?,?,?,?,?)", (url, v["pollster"], v["field_end"] or None, v["sample"] or None,
                                                    v["target_kind"], v["target"], v["value"], pub))
            stats["values"] += 1
        con.execute("UPDATE poll_articles SET extracted=1 WHERE url=?", (url,))
        stats["extracted"] += 1
        if stats["extracted"] % 50 == 0:
            con.commit()
    con.commit()
    stats["spent_usd"] = round(spent, 4)
    return stats


def series(target_kind: str, target: str, pollster: str | None = None) -> list[dict]:
    """조사 단위로 중복을 합친 추이: (기관, 조사종료일) 별 최빈값."""
    con = pconnect()
    q = """SELECT pollster, COALESCE(field_end, pub_date) AS d, value, url FROM poll_values
           WHERE target_kind=? AND target=?""" + (" AND pollster=?" if pollster else "")
    rows = con.execute(q, (target_kind, target, pollster) if pollster else (target_kind, target)).fetchall()
    by = {}
    for r in rows:
        by.setdefault((r["pollster"], r["d"]), []).append((r["value"], r["url"]))
    out = []
    for (pl, d), vs in by.items():
        vals = [v for v, _ in vs]
        mode = max(set(vals), key=vals.count)
        out.append({"pollster": pl, "date": d, "value": mode, "n_reports": len(vs),
                    "urls": [u for v, u in vs if v == mode][:3], "label": "보도"})
    return sorted(out, key=lambda x: x["date"] or "")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("cmd", choices=["collect", "show"])
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--budget-usd", type=float, help="이번 실행 AI 비용 상한(달러). 닿으면 멈춤")
    a = ap.parse_args()
    if a.cmd == "collect":
        st = collect(a.dry_run, a.budget_usd)
        print(st)
        if a.dry_run:
            n = st["new"]
            print(f"AI 추출 대상 {n}건 → 예상 약 ${n * 0.0001:.2f}~${n * 0.0003:.2f} "
                  f"(약 {n * 0.0001 * 1400:.0f}~{n * 0.0003 * 1400:.0f}원, Haiku)")
    else:
        for k, t in [("대통령국정", "긍정"), ("정당", "더불어민주당"), ("정당", "국민의힘")]:
            s = series(k, t)
            print(k, t, len(s), "건", [(x["pollster"], x["date"], x["value"]) for x in s[-8:]])
