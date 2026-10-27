"""3단계 사건 타임라인: 각 호수 게시물 본문의 '주요 사건' 목록에서 사건을 뽑아 events.csv 로 만든다.

실행 예:
    python src/events.py

- 원문: 1단계에서 캐시한 게시물 페이지(data/raw/html/content_*.html). 새로 내려받지 않는다.
- 사건: '주요 사건' 목록의 항목을 '/' 단위로 나눈 것. 날짜가 없는 항목('· 의료 공백 지속')은 '주중 지속'으로 표시.
- 정책 분야: 고정 14개 분야. 키워드 규칙으로 자동 분류하므로 사람이 확인해야 한다(review_events.html).
- 관련 평가 이유: 같은 호수의 긍정·부정 이유 중 같은 분야로 분류되는 항목(증감 표시가 있거나 3% 이상)을 자동 연결.
- 해설 문단: '대통령 직무 수행 평가' 해설(◎ 문단)을 weekly_commentary.csv 에 따로 저장해 검토할 때 참고한다.
"""
from __future__ import annotations

import csv
import datetime as dt
import html
import json
import re
import sqlite3
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "data"
RAW_HTML = DATA / "raw" / "html"
CONTENT_URL = "https://www.gallup.co.kr/gallupdb/reportContent.asp?seqNo={seq}"

DOMAINS = ["경제·물가", "부동산", "노동", "복지·연금", "교육", "의료", "외교·안보", "대북",
           "검찰·사법", "인사", "소통·태도", "재난·안전", "정치·정당", "기타"]

# 분야별 키워드. 사건명에 들어 있는 키워드 수가 가장 많은 분야로 정한다.
KEYWORDS = {
    "대북": ["도발", "북 ", "북한", "대북", "북송", "김정은", "남북", "탈북", "9·19", "9.19", "오물", "통일", "北"],
    "의료": ["마스크", "의과", "의료", "의대", "전공의", "의사", "간호", "병원", "코로나", "백신", "방역", "감염", "응급", "필수의료", "의정"],
    "부동산": ["부동산", "집값", "전세", "임대차", "주택", "아파트", "재건축", "그린벨트", "청약", "분양", "종부세"],
    "노동": ["노동", "노조", "파업", "근로", "최저임금", "화물연대", "민노총", "민주노총", "근무시간", "69시간", "52시간",
           "중대재해", "임금", "노란봉투"],
    "교육": ["학생", "대입", "수시", "교육부", "교육", "학교", "입시", "수능", "교사", "교권", "학제", "만 5세", "사교육", "킬러 문항", "유보통합", "늘봄"],
    "재난·안전": ["소방", "강진", "구호", "참사", "사고", "재난", "수해", "폭우", "홍수", "태풍", "화재", "이태원", "산불", "지진", "침수", "오송",
              "붕괴", "폭염", "안전", "잼버리", "실종", "희생자"],
    "복지·연금": ["휴가", "배우자", "한부모", "양육비", "정년", "심리상담", "육아", "복지", "연금", "저출생", "저출산", "출산", "돌봄", "수당", "보육", "장애인", "노인", "여성가족부", "여가부",
              "기초생활", "인구"],
    "인사": ["인선", "교체", "차관", "인사", "임명", "장관", "후보자", "청문", "사퇴", "사임", "사의", "지명", "내정", "개각", "비서실장", "발탁", "경질"],
    "검찰·사법": ["1심", "2심", "실형", "징역", "조사 출석", "민정수석", "경찰국", "가석방", "석방", "법무부", "옥중", "검찰", "수사", "기소", "재판", "법원", "대법", "헌재", "헌법재판소", "특검", "압수수색", "구속", "영장",
              "공수처", "판결", "선고", "무죄", "유죄", "체포", "경찰", "고발", "사법", "변론", "혐의", "지검", "감사원"],
    "외교·안보": ["미 대선", "美", "사드", "중동", "가자", "팔레스타인", "하마스", "이란", "방한", "공관", "체코", "軍", "발사체", "독도", "북대서양", "외교", "정상회담", "방미", "방일", "방중", "순방", "한미", "한일", "한중", "한미일", "미국", "일본", "중국",
              "나토", "NATO", "G7", "G20", "유엔", "UN", "국방", "안보", "핵", "확장억제", "우크라이나", "러시아",
              "이스라엘", "강제징용", "징용", "오염수", "후쿠시마", "국빈", "바이든", "트럼프", "기시다", "시진핑",
              "해병대", "군 ", "파병", "APEC", "엑스포", "정상"],
    "경제·물가": ["기준금리", "유가", "휘발유", "경유", "채권", "원전", "에너지", "쌀값", "통행료", "요금", "버스비", "워크아웃", "건설", "AI", "인공지능", "대형마트", "단통법", "택시", "산업", "경제", "물가", "금리", "환율", "추경", "예산", "세제", "세금", "상속세", "관세", "수출", "주가", "코스피",
              "KOSPI", "증시", "금융", "밸류업", "가상자산", "반도체", "재정", "감세", "소상공인", "민생", "내수",
              "소비", "무역", "공매도", "은행", "투자", "경기", "전기요금", "가스요금", "난방비", "유류세", "기업"],
    "소통·태도": ["MBC", "KBS", "언론", "가짜 뉴스", "기자단", "관저", "메시지", "기념사", "연설", "만찬", "발언", "기자회견", "담화", "도어스테핑", "출근길", "사과", "거부권", "재의요구", "비속어", "김건희",
              "영부인", "여사", "소통", "논란", "격노", "회견", "대국민", "명품"],
    "정치·정당": ["권한대행", "단체장", "교육감", "재보궐", "국정감사", "국감", "전 총리", "전 대통령", "행정통합", "메가시티", "특별연합", "지도부", "원내", "비명", "친명", "친윤", "친한", "민주 ", "명태균", "인수위", "국민의힘", "민주당", "정의당", "개혁신당", "조국혁신당", "전당대회", "대표", "원내대표", "공천", "선거",
              "총선", "보궐", "지방선거", "탈당", "창당", "합당", "탄핵", "국회", "여야", "비대위", "비상대책", "계엄",
              "집회", "장외", "당정", "의원", "야권", "야당", "여당", "대선", "윤리위"],
}
# 점수가 같을 때의 우선순위(구체적인 분야 먼저)
TIE_ORDER = ["대북", "의료", "부동산", "노동", "교육", "재난·안전", "복지·연금", "인사", "검찰·사법",
             "외교·안보", "경제·물가", "소통·태도", "정치·정당"]

BULLET_RE = re.compile(r"^\s*[-·•]\s*")
DATE_RE = re.compile(r"^(\d{1,2})/(\d{1,2})(?:\s*~\s*\d{1,2}(?:/\d{1,2})?)?\s+(?:\d{1,2}:\d{2}\s+)?")


def page_text(seq: int) -> str:
    h = (RAW_HTML / f"content_{seq}.html").read_text(encoding="utf-8")
    t = re.sub(r"<script.*?</script>|<style.*?</style>", "", h, flags=re.S)
    t = html.unescape(re.sub(r"<br\s*/?>|</p>|</div>|</li>", "\n", t))
    t = re.sub(r"<[^>]+>", " ", t)
    t = re.sub(r"[ \t　\xa0]+", " ", t)
    return re.sub(r"\n\s*\n+", "\n", t)


def classify(text: str) -> tuple[str, list[str]]:
    # 부처 이름 속 글자가 엉뚱한 분야로 잡히지 않게('행정안전부'의 '안전')
    text = text.replace("행정안전부", "행안부")
    scores = {d: sum(1 for k in kws if k in text) for d, kws in KEYWORDS.items()}
    hit = [d for d in TIE_ORDER if scores[d] > 0]
    if not hit:
        return "기타", []
    best = max(hit, key=lambda d: (scores[d], -TIE_ORDER.index(d)))
    return best, sorted(hit, key=lambda d: (-scores[d], TIE_ORDER.index(d)))


def event_lines(t: str) -> list[str]:
    """'주요 사건' 목록을 글머리표 단위 줄로 돌려준다(이어지는 '/ ...' 줄은 앞 줄에 붙인다)."""
    m = re.search(r"/ 주요 사건\s*\n(.*?)\n\s*요약", t, re.S)
    if not m:
        return []
    items: list[str] = []
    for raw in m.group(1).split("\n"):
        s = raw.strip()
        if not s:
            continue
        if BULLET_RE.match(s) and not s.startswith("/"):
            items.append(BULLET_RE.sub("", s))
        elif items:
            items[-1] += " " + s
        else:
            items.append(s)
    return items


def resolve_date(month: int, day: int, survey_start: dt.date) -> str:
    year = survey_start.year
    # 1월 조사 보고서에 실린 12월 사건
    if month - survey_start.month > 6:
        year -= 1
    try:
        return dt.date(year, month, day).isoformat()
    except ValueError:
        return ""


def split_events(item: str, survey_start: dt.date) -> list[tuple[str, str, str]]:
    """글머리표 한 줄 → [(날짜, 날짜 표기, 사건명)]. 날짜는 줄 앞에 한 번 나오고 '/'로 여러 사건이 이어진다."""
    item = re.sub(r"\s+", " ", item).strip()
    m = DATE_RE.match(item)
    date, date_text = "", "주중 지속"
    if m:
        date_text = m.group(0).strip()
        date = resolve_date(int(m.group(1)), int(m.group(2)), survey_start)
        item = item[m.end():]
    out = []
    for part in re.split(r"\s+/\s*|\s*/\s+", item):
        part = part.strip(" /")
        # 사건 안의 시각 표기('04:27 尹, ...')는 날짜 표기 쪽으로 옮긴다
        tm = re.match(r"^(\d{1,2}:\d{2})\s+", part)
        dtext = date_text
        if tm:
            dtext = f"{date_text.split()[0]} {tm.group(1)}" if m else tm.group(1)
            part = part[tm.end():]
        if part:
            out.append((date, dtext, part))
    return out


def approval_commentary(t: str) -> str:
    """'조사 결과' 아래 대통령 직무 평가 해설(첫 구분선 '──' 전까지)."""
    m = re.search(r"\n\s*조사 결과\s*\n", t)
    if not m:
        return ""
    body = t[m.end() - 1:]
    j = body.find("──")
    body = body[:j] if j > 0 else body[:4000]
    lines = [l.strip() for l in body.split("\n") if l.strip()]
    return "\n".join(lines)


def main():
    con = sqlite3.connect(DATA / "weekly.sqlite")
    surveys = {r[0]: r[1:] for r in con.execute(
        "SELECT issue, week_label, survey_start, survey_end, approval_status FROM survey")}
    reasons: dict[int, list] = {}
    for issue, pol, item, pct, chg in con.execute(
            "SELECT issue, polarity, item, pct, change_pp FROM reasons ORDER BY issue, polarity, rank"):
        reasons.setdefault(issue, []).append((pol, item, pct, chg))
    with open(DATA / "manifest.csv", encoding="utf-8-sig") as f:
        manifest = [r for r in csv.DictReader(f) if r["issue"] and r["status"] == "downloaded"]

    events, commentary = [], []
    for m in manifest:
        issue, seq = int(m["issue"]), int(m["seq_no"])
        week_label, s_start, s_end, appr_status = surveys[issue]
        t = page_text(seq)
        url = CONTENT_URL.format(seq=seq)
        commentary.append({"issue": issue, "week_label": week_label, "source_url": url,
                           "approval_commentary": approval_commentary(t)})
        # 이유 항목 분야 분류(같은 분야 사건과 연결용)
        rs = []
        for pol, item, pct, chg in reasons.get(issue, []):
            if item in ("기타", "모름/응답거절"):
                continue
            d, _ = classify(item)
            rs.append((pol, item, pct, chg, d))
        n = 0
        for line in event_lines(t):
            for date, dtext, name in split_events(line, dt.date.fromisoformat(s_start)):
                n += 1
                dom, cands = classify(name)
                rel = [f"{'긍정' if pol == 'positive' else '부정'}:{item} {pct:g}%"
                       + (f"({chg:+g})" if chg is not None else "")
                       for pol, item, pct, chg, d in rs
                       if d == dom and dom != "기타" and (chg is not None or pct >= 3)]
                events.append({
                    "event_id": f"{issue}-{n:02d}", "issue": issue, "week_label": week_label,
                    "survey_period": f"{s_start}~{s_end}", "event_date": date, "date_text": dtext,
                    "event": name, "source_line": re.sub(r"\s+", " ", line).strip(), "domain": dom, "domain_candidates": "|".join(cands),
                    "related_reasons": "; ".join(rel), "approval_status": appr_status,
                    "source_issue": issue, "source_url": url,
                })
        if n == 0:
            print(f"제{issue}호: 주요 사건 없음")

    fields = list(events[0].keys())
    with open(DATA / "events.csv", "w", newline="", encoding="utf-8-sig") as f:
        w = csv.DictWriter(f, fieldnames=fields)
        w.writeheader()
        w.writerows(events)
    with open(DATA / "weekly_commentary.csv", "w", newline="", encoding="utf-8-sig") as f:
        w = csv.DictWriter(f, fieldnames=list(commentary[0].keys()))
        w.writeheader()
        w.writerows(commentary)

    build_review_page(events, commentary, reasons)
    from collections import Counter
    print(f"사건 {len(events)}개 ({len(manifest)}개 호수), 분야별:", dict(Counter(e["domain"] for e in events).most_common()))
    print(f"관련 이유가 자동 연결된 사건: {sum(1 for e in events if e['related_reasons'])}개")


def build_review_page(events, commentary, reasons):
    weeks = {c["issue"]: {"week_label": c["week_label"], "url": c["source_url"],
                          "commentary": c["approval_commentary"],
                          "reasons": [f"{'긍정' if p == 'positive' else '부정'}:{i} {pc:g}%" + (f"({ch:+g})" if ch is not None else "")
                                      for p, i, pc, ch in reasons.get(c["issue"], [])
                                      if i not in ("기타", "모름/응답거절") and (ch is not None or pc >= 5)]} for c in commentary}
    payload = json.dumps({"events": events, "weeks": weeks, "domains": DOMAINS}, ensure_ascii=False)
    tpl = (ROOT / "src" / "review_template.html").read_text(encoding="utf-8")
    (ROOT / "review_events.html").write_text(tpl.replace("/*__DATA__*/null", payload), encoding="utf-8")


if __name__ == "__main__":
    main()
