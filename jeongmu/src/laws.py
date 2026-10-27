"""법제처 국가법령정보 공동활용 API(DRF)로 현행 법령 원문을 받아 조문 단위로 꺼낸다.

OC 값은 .env 의 LAW_OC (가입 이메일 @ 앞부분). 비어 있으면 공개 테스트값 'test'를 쓴다.
받은 원문은 data/law_cache/ 에 저장하고, 7일이 지나면 다시 받는다.
"""
import json
import re
import time
from datetime import datetime, timedelta

import requests

from config import DATA, env

CACHE = DATA / "law_cache"
BASE = "https://www.law.go.kr/DRF/"
MAX_AGE = timedelta(days=7)


def _get(url: str, params: dict, retries: int = 6) -> dict:
    last = None
    for i in range(retries):
        try:
            r = requests.get(url, params=params, timeout=60)
            r.raise_for_status()
            return r.json()
        except (requests.RequestException, ValueError) as e:
            last = e
            time.sleep(min(2 * (i + 1), 10))
    raise RuntimeError(f"법제처 API 실패: {last}")


def fetch_law(name: str, refresh: bool = False) -> dict:
    """현행 법령 전체 JSON. name 은 '국회법', '대한민국헌법' 처럼 정식 명칭."""
    CACHE.mkdir(parents=True, exist_ok=True)
    path = CACHE / f"{name}.json"
    if path.exists() and not refresh:
        age = datetime.now() - datetime.fromtimestamp(path.stat().st_mtime)
        if age < MAX_AGE:
            return json.loads(path.read_text(encoding="utf-8"))
    oc = env("LAW_OC", "test")
    found = _get(BASE + "lawSearch.do", {"OC": oc, "target": "law", "type": "JSON", "query": name})
    laws = found["LawSearch"].get("law", [])
    laws = laws if isinstance(laws, list) else [laws]
    exact = [x for x in laws if x.get("법령명한글") == name and x.get("현행연혁코드", "현행") == "현행"]
    if not exact:
        raise RuntimeError(f"'{name}' 현행 법령을 찾지 못함")
    mst = exact[0]["법령일련번호"]
    time.sleep(1)
    data = _get(BASE + "lawService.do", {"OC": oc, "target": "law", "type": "JSON", "MST": mst})
    path.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")
    return data


def info(law: dict) -> dict:
    b = law["법령"]["기본정보"]
    return {"name": b["법령명_한글"], "law_id": b["법령ID"], "enforce_date": b["시행일자"],
            "promulgate_date": b["공포일자"], "promulgate_no": b["공포번호"]}


def _flatten(unit: dict) -> str:
    parts = [unit.get("조문내용", "")]

    def walk(items, key, sub):
        items = items if isinstance(items, list) else [items]
        for it in items:
            if not isinstance(it, dict):
                continue
            parts.append(it.get(key, ""))
            if sub:
                for k2, k3 in sub:
                    if k2 in it:
                        walk(it[k2], k3, [("목", "목내용")] if k2 == "호" else None)

    if "항" in unit:
        walk(unit["항"], "항내용", [("호", "호내용")])
    text = "\n".join(p if isinstance(p, str) else " ".join(map(str, p)) for p in parts if p)
    return re.sub(r"[ \t]+", " ", text).strip()


ART_RE = re.compile(r"제(\d+)조(?:의(\d+))?")


def article(law: dict, ref: str) -> str | None:
    """'제85조의2' 같은 참조로 조문 전체 텍스트를 돌려준다."""
    m = ART_RE.fullmatch(ref.strip())
    if not m:
        raise ValueError(ref)
    no, branch = m.group(1), m.group(2) or ""
    for u in law["법령"]["조문"]["조문단위"]:
        if u.get("조문여부") != "조문":
            continue
        if u.get("조문번호") == no and (u.get("조문가지번호") or "") == branch:
            return _flatten(u)
    return None
