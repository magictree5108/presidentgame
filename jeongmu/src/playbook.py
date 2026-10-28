"""정치전략 원칙집(data/playbook/principles.json) 불러오기·프롬프트용 요약·인용 검사.

원칙집은 책 8권의 원칙을 요약·재서술한 것이다(원문은 저장하지 않는다).
mode '공격' = 우리가 쓰는 수, '방어' = 상대가 쓸 때 알아채고 받아치는 법.
fails = 책의 '반전(Reversal)'·한계 → 역풍 점수의 근거.

사용: python src/playbook.py            # 책별·태그별 원칙 수
      python src/playbook.py 쐐기        # 태그로 찾기
"""
import json
import sys
from collections import Counter
from functools import lru_cache
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from config import DATA

PATH = DATA / "playbook" / "principles.json"


@lru_cache(maxsize=1)
def load() -> dict:
    return json.loads(PATH.read_text(encoding="utf-8"))


def principles(tag: str | None = None, mode: str | None = None) -> list[dict]:
    return [p for p in load()["principles"]
            if (tag is None or tag in p["tags"]) and (mode is None or p["mode"] == mode)]


def ids() -> set[str]:
    return {p["id"] for p in load()["principles"]}


def as_prompt() -> str:
    """전략 엔진에 넣을 압축본: 'ID [모드/태그] 제목 — 적용 | 실패조건'."""
    books = load()["books"]
    lines = ["책: " + "; ".join(f"{k}={v}" for k, v in books.items())]
    for p in load()["principles"]:
        fails = "" if p["fails"] in ("", "—") else f" | 실패조건: {p['fails']}"
        lines.append(f"{p['id']} [{p['mode']}/{','.join(p['tags'])}] {p['title']} — {p['apply']}{fails}")
    return "\n".join(lines)


def check_principles(items: list[dict]) -> list[dict]:
    """AI가 단 원칙 번호 중 원칙집에 없는 것은 지우고 표시한다."""
    valid = ids()
    for it in items:
        cited = it.get("principles") or []
        it["principles"] = [x for x in cited if x in valid]
        if len(it["principles"]) < len(cited):
            it["principles_dropped"] = [x for x in cited if x not in valid]
    return items


def lookup() -> dict:
    """화면용: id → {제목, 책, 위치, 실패조건}."""
    books = load()["books"]
    return {p["id"]: {"title": p["title"], "book": books[p["book"]], "loc": p["loc"], "mode": p["mode"],
                      "fails": p["fails"]} for p in load()["principles"]}


if __name__ == "__main__":
    if len(sys.argv) > 1:
        for p in principles(tag=sys.argv[1]):
            print(f"{p['id']} [{p['mode']}] {p['title']}\n   {p['apply']}")
    else:
        ps = load()["principles"]
        print(f"원칙 {len(ps)}개 · 책별 {dict(Counter(p['book'] for p in ps))} · 모드 {dict(Counter(p['mode'] for p in ps))}")
        print("태그별", dict(Counter(t for p in ps for t in p["tags"]).most_common()))
