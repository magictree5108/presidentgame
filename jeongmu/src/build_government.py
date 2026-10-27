"""정부조직법 현행 원문에서 정부 조직도 뼈대를 만든다 → data/government.json

조직 이름·소속·장(長)의 직위는 조문에서 직접 뽑고 근거 조문을 붙인다.
현직자 이름은 법령에 없으므로 비워 두고, data/government_people.csv(출처 필수)로 채운다.
"""
import csv
import json
import re
import sys
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

import laws
from config import DATA

ORG_TITLE = re.compile(r"^(.+?(부|처|실|원|청|위원회))$")
HEAD = re.compile(r"(장관|처장|실장|원장|청장|위원장) 1명")
DEPUTY = re.compile(r"(차관|차장) (\d+)명")


def build() -> dict:
    L = laws.fetch_law("정부조직법")
    info = laws.info(L)
    orgs = []
    titles = {}
    for u in L["법령"]["조문"]["조문단위"]:
        if u.get("조문여부") == "조문":
            ref = f"제{u['조문번호']}조" + (f"의{u['조문가지번호']}" if u.get("조문가지번호") else "")
            titles[ref] = (u.get("조문제목") or "").strip()

    # 대통령 소속·국무총리 소속 기관: 조문 제목이 기관명이고 '...소속으로'/보좌 조직
    for ref, title in titles.items():
        if not ORG_TITLE.match(title) or title in ("행정각부",):
            continue
        text = laws.article(L, ref) or ""
        h = HEAD.search(text)
        if not h or h.group(1) == "청장":
            continue
        if "대통령의 직무를 보좌" in text or "대통령 소속으로" in text or "대통령 등의 경호" in text \
                or "국가안보에 관한 대통령" in text:
            level = "대통령 소속"
        elif "국무총리 소속으로" in text or "국무총리를 보좌" in text or "국무총리의 직무를 보좌" in text:
            level = "국무총리 소속"
        else:
            continue
        orgs.append({"name": title, "level": level, "head_title": h.group(1),
                     "deputies": [f"{d[0]} {d[1]}명" for d in DEPUTY.findall(text)],
                     "basis": f"정부조직법 {ref}", "is_cabinet": "국무위원으로 보" in text})

    # 행정각부: 제29조 ①의 목록, 차관 수는 ② 단서
    art29 = laws.article(L, "제29조")
    ministries = re.findall(r"^\d+\. (\S+부)$", art29, re.M)
    two = re.search(r"다만, (.+?)에는 차관 2명", art29)
    two = set(two.group(1).split("ㆍ")) if two else set()
    by_title = {t: r for r, t in titles.items()}
    for m in ministries:
        ref = by_title.get(m)
        orgs.append({"name": m, "level": "행정각부", "head_title": "장관",
                     "deputies": [f"차관 {2 if m in two else 1}명"],
                     "basis": "정부조직법 제29조" + (f", {ref}" if ref else ""), "is_cabinet": True})
        text = laws.article(L, ref) if ref else ""
        for sub in dict.fromkeys(re.findall(r"장관 소속으로 (\S+?청)을 둔다", text or "")):
            orgs.append({"name": sub, "level": "외청", "parent": m, "head_title": "청장",
                         "deputies": [], "basis": f"정부조직법 {ref}", "is_cabinet": False})
    people = {}
    p = DATA / "government_people.csv"
    if p.exists():
        for r in csv.DictReader(p.open(encoding="utf-8")):
            if r.get("source"):
                people.setdefault(r["org"], []).append(r)
    for o in orgs:
        o["people"] = people.get(o["name"], [])
    return {
        "as_of": date.today().isoformat(),
        "source": f"정부조직법(법률 제{info['promulgate_no']}호, {info['promulgate_date']} 공포, {info['enforce_date']} 시행) — 법제처 현행 원문",
        "note": "현직자 이름은 data/government_people.csv 에 출처와 함께 입력해야 표시됩니다. 비어 있으면 '미입력'입니다.",
        "president": {"name": None, "source": None},
        "prime_minister": {"name": None, "source": None, "basis": "헌법 제86조"},
        "orgs": orgs,
    }


if __name__ == "__main__":
    g = build()
    (DATA / "government.json").write_text(json.dumps(g, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    from collections import Counter
    print(Counter(o["level"] for o in g["orgs"]))
    for o in g["orgs"]:
        print(o["level"], o["name"], o.get("parent", ""), o["head_title"], o["basis"])
