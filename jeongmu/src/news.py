"""5단계: 네이버 뉴스 검색 API로 동향 수집 → AI가 카드용 사실만 추출.

저작권 원칙: 기사 본문은 받지도 저장하지도 않는다. API가 주는 제목·요약문(description)은
동명이인 판별과 AI 추출에만 잠깐 쓰고 버린다. 저장하는 것은 제목, 날짜, 언론사(도메인), 링크,
AI가 뽑은 한두 문장 요약뿐이다. 모든 항목에 '보도' 표식을 붙인다.

사용:
  python src/news.py collect            # 의원·부처·주요 법안 검색 → 매칭 → 추출
  python src/news.py sample             # 동명이인 검수용 표본 50건 → docs/news_fp_sample.csv
  python src/news.py fprate             # 검수한 표본으로 오탐률 계산
"""
import argparse
import csv
import html
import json
import random
import re
import sqlite3
import sys
import time
from datetime import date, datetime
from email.utils import parsedate_to_datetime
from pathlib import Path
from urllib.parse import urlparse

import requests

sys.path.insert(0, str(Path(__file__).parent))

from config import DATA, DOCS, NEWS_DB, env
from db import connect

API = "https://openapi.naver.com/v1/search/news.json"
SCHEMA = """
CREATE TABLE IF NOT EXISTS articles (
  url TEXT PRIMARY KEY, title TEXT NOT NULL, pub_date TEXT, press_domain TEXT, naver_link TEXT,
  query TEXT, collected_at TEXT);
CREATE TABLE IF NOT EXISTS mentions (
  url TEXT, entity_type TEXT, entity_id TEXT, entity_name TEXT,
  match_rule TEXT, match_score REAL, PRIMARY KEY(url, entity_type, entity_id));
CREATE TABLE IF NOT EXISTS facts (
  url TEXT, entity_type TEXT, entity_id TEXT, category TEXT, summary TEXT, label TEXT DEFAULT '보도',
  extracted_at TEXT, PRIMARY KEY(url, entity_type, entity_id, category));
"""
CATEGORIES = ["입장 표명", "발의·표결 예고", "갈등", "협력", "지역구 현안"]


def nconnect(path=NEWS_DB):
    con = sqlite3.connect(str(path))
    con.row_factory = sqlite3.Row
    con.executescript(SCHEMA)
    return con


def clean(s: str) -> str:
    return html.unescape(re.sub(r"<[^>]+>", "", s or "")).strip()


HUB = "https://naverapihub.apigw.ntruss.com/search/v1/news"  # 네이버 클라우드 NAVER API HUB(2026~ 신규 발급)
_mode = None


def search(query: str, display: int = 100, start: int = 1) -> list[dict]:
    """뉴스 검색. NAVER API HUB 키와 예전 개발자센터 키를 모두 지원한다(같은 NAVER_CLIENT_ID/SECRET 칸).
    처음 호출에서 HUB → 개발자센터 순으로 시도해 되는 쪽을 기억한다. 하루 25,000회 한도."""
    global _mode
    cid, sec = env("NAVER_CLIENT_ID"), env("NAVER_CLIENT_SECRET")
    if not (cid and sec):
        raise RuntimeError("NAVER_CLIENT_ID/NAVER_CLIENT_SECRET이 .env에 없습니다.")
    targets = {
        "hub": (HUB, {"X-NCP-APIGW-API-KEY-ID": cid, "X-NCP-APIGW-API-KEY": sec}),
        "dev": (API, {"X-Naver-Client-Id": cid, "X-Naver-Client-Secret": sec}),
    }
    order = [_mode] if _mode else ["hub", "dev"]
    params = {"query": query, "display": display, "start": start, "sort": "date"}
    last = None
    for mode in order:
        url, headers = targets[mode]
        for i in range(4):
            r = requests.get(url, params=params, headers=headers, timeout=30)
            if r.status_code == 429:
                time.sleep(2 ** (i + 1))
                continue
            break
        if r.status_code in (401, 403) and not _mode:
            last = r
            continue
        r.raise_for_status()
        _mode = mode
        time.sleep(1)  # 요청 간격 1초
        return r.json().get("items", [])
    raise RuntimeError(f"네이버 검색 인증 실패({last.status_code if last is not None else '?'}): 키를 확인하세요")


# ------------------------------------------------------------------ 동명이인 판별 규칙
def region_words(district: str | None) -> list[str]:
    """'서울 종로구' → ['서울', '종로'] 처럼 지역구에서 판별용 단어를 뽑는다."""
    if not district or "비례" in district:
        return []
    words = []
    for w in re.split(r"[\s·,/()]+", district):
        w = re.sub(r"(특별시|광역시|특별자치시|특별자치도|도|시|군|구|갑|을|병|정)$", "", w)
        if len(w) >= 2:
            words.append(w)
    return words


def party_words(party: str | None) -> list[str]:
    if not party:
        return []
    out = [party]
    if party.endswith("당") and len(party) > 3:
        out.append(party[-3:])  # 예: '○○○당' 줄임말 대비. 짧은 이름은 그대로만 쓴다
    return out


def match_member(text: str, m: dict) -> tuple[bool, str, float]:
    """규칙: (1) 이름 등장 필수 (2) '이름 + 의원' 붙어 나오면 강한 신호
    (3) 정당명 또는 지역구 단어가 함께 나오면 신호. (2)+(3) 또는 (3) 두 개 이상이면 채택."""
    name = m["name"]
    if not name or name not in text:
        return False, "이름 없음", 0.0
    sig = []
    if re.search(re.escape(name) + r"\s*(국회)?의원", text) or re.search(r"의원\s*" + re.escape(name), text):
        sig.append("이름+의원")
    if any(p in text for p in party_words(m.get("party"))):
        sig.append("정당")
    if any(w in text for w in region_words(m.get("district"))):
        sig.append("지역구")
    if any(c in text for c in (m.get("committee_words") or [])):
        sig.append("위원회")
    strong = "이름+의원" in sig
    ok = (strong and len(sig) >= 2) or (len([s for s in sig if s != "이름+의원"]) >= 2)
    return ok, "+".join(sig) or "이름만", len(sig) / 4


# ------------------------------------------------------------------ AI 추출
EXTRACT_SYSTEM = """너는 국회 동향 기록원이다. 기사 제목과 짧은 요약문만 보고, 지정된 인물·기관에 대해
기사에 명시된 사실만 뽑는다. 범주: 입장 표명 / 발의·표결 예고 / 갈등 / 협력 / 지역구 현안.
해당되는 것이 없으면 빈 목록을 낸다. 추측·해석·평가는 쓰지 않는다.
요약 규칙(저작권): 기사 문장을 복사하지 않는다. 원문과 같은 어절이 다섯 개 이상 이어지면 안 된다.
'[누가] [무엇에 대해] [어떤 행동/입장]' 형태의 40자 안팎 한 문장으로 직접 다시 쓴다. 예: '가나다 의원, ○○법 개정안 반대 입장 표명'."""
EXTRACT_SCHEMA = {
    "type": "object", "additionalProperties": False, "required": ["facts"],
    "properties": {"facts": {"type": "array", "items": {
        "type": "object", "additionalProperties": False, "required": ["category", "summary"],
        "properties": {"category": {"type": "string", "enum": CATEGORIES}, "summary": {"type": "string"}}}}},
}


def extract(title: str, desc: str, entity: str) -> list[dict]:
    from llm import call_json
    from llm import CHEAP_MODEL
    out = call_json(EXTRACT_SYSTEM, f"대상: {entity}\n제목: {title}\n요약문: {desc}", EXTRACT_SCHEMA,
                    purpose="news_extract", effort="low", max_tokens=2000, model=CHEAP_MODEL)
    return out["facts"]


def collect(max_members: int | None = None, do_extract: bool = True, dry_run: bool = False) -> dict:
    """dry_run: 검색·판별만 하고 DB 저장·AI 호출 없이 'AI가 처리할 새 기사 수'만 센다(비용 0원)."""
    acon = connect()
    ncon = nconnect()
    members = [dict(r) for r in acon.execute("SELECT member_id, name, current_party AS party, district FROM members")]
    gov = json.loads((DATA / "government.json").read_text(encoding="utf-8")) if (DATA / "government.json").exists() else {"orgs": []}
    targets = [("member", m["member_id"], m["name"], m) for m in members[:max_members]]
    targets += [("org", o["name"], o["name"], o) for o in gov["orgs"] if o["level"] in ("행정각부", "대통령 소속")]
    tracked = DATA / "tracked_bills.txt"
    if tracked.exists():
        for line in tracked.read_text(encoding="utf-8").splitlines():
            if line.strip():
                targets.append(("bill", line.strip(), line.strip(), {}))
    stats = {"queries": 0, "articles": 0, "matched": 0, "facts": 0}
    today = date.today().isoformat()
    for etype, eid, name, ent in targets:
        q = f"{name} 의원" if etype == "member" else name
        try:
            items = search(q, display=50)
        except Exception as e:
            print(f"검색 실패 {q}: {e}")
            continue
        stats["queries"] += 1
        for it in items:
            url = it.get("originallink") or it.get("link")
            title, desc = clean(it.get("title")), clean(it.get("description"))
            try:
                pub = parsedate_to_datetime(it["pubDate"]).date().isoformat()
            except Exception:
                pub = None
            if etype == "member":
                ok, rule, sc = match_member(title + " " + desc, ent)
            else:
                ok, rule, sc = (name in title + desc), "이름 포함", 1.0
            if not ok:
                continue
            if dry_run:
                done = ncon.execute("SELECT 1 FROM facts WHERE url=? AND entity_id=?", (url, eid)).fetchone()
                stats["matched"] += 1
                stats["to_extract"] = stats.get("to_extract", 0) + (0 if done else 1)
                continue
            new = ncon.execute("SELECT 1 FROM articles WHERE url=?", (url,)).fetchone() is None
            ncon.execute("INSERT OR IGNORE INTO articles VALUES(?,?,?,?,?,?,?)",
                         (url, title, pub, urlparse(url).netloc, it.get("link"), q, today))
            ncon.execute("INSERT OR IGNORE INTO mentions VALUES(?,?,?,?,?,?)", (url, etype, eid, name, rule, sc))
            stats["articles"] += new
            stats["matched"] += 1
            already = ncon.execute("SELECT 1 FROM facts WHERE url=? AND entity_id=?", (url, eid)).fetchone()
            if do_extract and not already:
                try:
                    for f in extract(title, desc, name):
                        ncon.execute("INSERT OR IGNORE INTO facts(url,entity_type,entity_id,category,summary,extracted_at) VALUES(?,?,?,?,?,?)",
                                     (url, etype, eid, f["category"], f["summary"], datetime.now().isoformat(timespec="seconds")))
                        stats["facts"] += 1
                except Exception as e:
                    print(f"추출 실패: {e}")
                    do_extract = False  # 키가 없거나 오류면 이번 실행은 추출 생략
        ncon.commit()
    return stats


def facts_for(entity_id: str, limit: int = 20, con=None) -> list[dict]:
    con = con or nconnect()
    rows = con.execute(
        """SELECT f.category, f.summary, f.label, a.title, a.pub_date, a.press_domain, a.url
           FROM facts f JOIN articles a ON a.url=f.url WHERE f.entity_id=?
           ORDER BY a.pub_date DESC LIMIT ?""", (entity_id, limit)).fetchall()
    return [dict(r) for r in rows]


def alerts(on: str | None = None, con=None) -> list[dict]:
    """오늘의 알림 후보: 갈등·발의/표결 예고 범주. 위협/기회 구분은 관점이 필요하므로 화면에서 관점을 고른 뒤
    판단 엔진이 'AI 추정'으로 붙인다. 모든 알림에 기사 링크가 있다."""
    on = on or date.today().isoformat()
    con = con or nconnect()
    rows = con.execute(
        """SELECT f.entity_type, f.entity_id, m.entity_name, f.category, f.summary, a.title, a.url, a.press_domain, a.pub_date
           FROM facts f JOIN articles a ON a.url=f.url
           LEFT JOIN mentions m ON m.url=f.url AND m.entity_id=f.entity_id
           WHERE a.pub_date=? AND f.category IN ('갈등','발의·표결 예고','입장 표명')""", (on,)).fetchall()
    return [dict(r) for r in rows]


def make_sample(n: int = 50, seed: int = 7):
    con = nconnect()
    rows = [dict(r) for r in con.execute(
        """SELECT m.entity_name, m.match_rule, a.title, a.url, a.pub_date FROM mentions m
           JOIN articles a ON a.url=m.url WHERE m.entity_type='member'""")]
    random.Random(seed).shuffle(rows)
    p = DOCS / "news_fp_sample.csv"
    with p.open("w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=["entity_name", "match_rule", "title", "url", "pub_date", "is_correct(O/X)"])
        w.writeheader()
        for r in rows[:n]:
            w.writerow({**r, "is_correct(O/X)": ""})
    print(f"{p} 에 {min(n, len(rows))}건. 마지막 칸에 O(맞음)/X(동명이인 오탐)를 채운 뒤 fprate 실행")


def fp_rate():
    p = DOCS / "news_fp_sample.csv"
    rows = [r for r in csv.DictReader(p.open(encoding="utf-8")) if r["is_correct(O/X)"].strip().upper() in ("O", "X")]
    if not rows:
        print("검수된 행이 없습니다.")
        return None
    x = sum(r["is_correct(O/X)"].strip().upper() == "X" for r in rows)
    print(f"검수 {len(rows)}건 중 오탐 {x}건 → 오탐률 {x / len(rows):.1%}")
    return x / len(rows)


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("cmd", choices=["collect", "sample", "fprate"])
    ap.add_argument("--max-members", type=int)
    ap.add_argument("--no-extract", action="store_true")
    ap.add_argument("--dry-run", action="store_true", help="AI 없이 처리할 기사 수만 세어 비용 추정")
    a = ap.parse_args()
    if a.cmd == "collect":
        st = collect(a.max_members, not a.no_extract, a.dry_run)
        print(st)
        if a.dry_run:
            n = st.get("to_extract", 0)
            print(f"AI 추출 대상 {n}건 → 예상 비용 약 ${n * 0.00012:.3f}~${n * 0.0003:.3f} "
                  f"(약 {n * 0.00012 * 1400:.0f}~{n * 0.0003 * 1400:.0f}원, Haiku 실측 1건 $0.00012 기준)")
    elif a.cmd == "sample":
        make_sample()
    else:
        fp_rate()
