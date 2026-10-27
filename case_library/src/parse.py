"""2단계 파싱: 데일리 오피니언 PDF에서 조사 개요, 직무 평가 교차표, 평가 이유, 정당 지지도 교차표를 뽑는다.

실행 예:
    python src/parse.py                 # manifest 에서 받은 PDF 전체
    python src/parse.py --issues 495-504
    python src/parse.py --force         # 이미 파싱한 호수도 다시

PDF의 숫자는 글자 단위로 흩어져 있어(예: "1 ,001") 좌표로 다시 붙이고,
각 표의 '전체' 행 숫자 위치(오른쪽 끝 x)를 열 기준점으로 삼아 칸을 배정한다.
빈 칸은 비워 두고(NULL) 추정으로 채우지 않는다.
"""
from __future__ import annotations

import argparse
import csv
import re
import sqlite3
from collections import Counter
from pathlib import Path

import pdfplumber

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "data"
DB = DATA / "weekly.sqlite"

NUM_RE = re.compile(r"^[\d,.\-%]+$")
WEEK_RE = re.compile(r"(\d{4})년\s*(\d{1,2})월\s*(\d)주")

# 표 왼쪽 첫 칸(구분)의 글자 → 표준 집단 이름
CATEGORY_MAP = {
    "지역별": "권역",
    "성별": "성",
    "연령별": "연령",
    "주요지지정당별": "지지정당",
    "직업별": "직업",
    "생활수준별": "생활수준",
    "성향별": "이념성향",
    "평소정치에관심이": "정치관심도",
    "대통령직무": "직무평가",          # 정당 지지도 표에만 있음(긍정/부정 평가자)
    "대통령직무평가별": "직무평가",
}
EXPECTED_CATEGORIES = ["권역", "성", "연령", "지지정당", "직업", "생활수준", "이념성향", "정치관심도"]
PARTY_EXPECTED_CATEGORIES = ["권역", "성", "연령", "직업", "생활수준", "이념성향", "직무평가", "정치관심도"]
# 하위 집단 사례수 합이 전체와 같아야 하는 구분(모든 응답자가 정확히 한 칸에 들어가는 구분)
EXHAUSTIVE = ["권역", "성", "연령", "직업"]

SCHEMA = """
CREATE TABLE IF NOT EXISTS survey (
    issue INTEGER PRIMARY KEY, week_label TEXT, post_date TEXT, pdf_url TEXT,
    survey_period TEXT, survey_start TEXT, survey_end TEXT,
    n_sample INTEGER, response_rate REAL, response_calls INTEGER, contact_rate REAL,
    method TEXT, sampling TEXT, margin_of_error REAL,
    approve_se REAL, approve_ci_low REAL, approve_ci_high REAL,
    disapprove_se REAL, disapprove_ci_low REAL, disapprove_ci_high REAL,
    approval_status TEXT,  -- asked | not_asked(탄핵소추로 직무 정지 기간)
    pages TEXT, parsed_at TEXT DEFAULT CURRENT_TIMESTAMP
);
CREATE TABLE IF NOT EXISTS approval_by_group (
    issue INTEGER, category TEXT, subgroup TEXT, row_order INTEGER,
    n_raw INTEGER, n_weighted INTEGER,
    approve REAL, disapprove REAL, neither REAL, dont_know REAL,
    reserved REAL,  -- '의견 유보' 열이 따로 있는 호수만(= 어느 쪽도 아님 + 모름/응답거절)
    suppressed INTEGER, blank_cells TEXT, page INTEGER,
    PRIMARY KEY (issue, category, subgroup)
);
CREATE TABLE IF NOT EXISTS reasons (
    issue INTEGER, polarity TEXT, rank INTEGER, item TEXT, pct REAL,
    change_pp REAL, base_n INTEGER, base_label TEXT, change_basis TEXT, page INTEGER,
    PRIMARY KEY (issue, polarity, rank)
);
CREATE TABLE IF NOT EXISTS party_by_group (
    issue INTEGER, category TEXT, subgroup TEXT, row_order INTEGER,
    n_raw INTEGER, n_weighted INTEGER, party TEXT, col_order INTEGER, pct REAL,
    suppressed INTEGER, page INTEGER,
    PRIMARY KEY (issue, category, subgroup, party)
);
"""


class ParseError(Exception):
    def __init__(self, kind: str, msg: str):
        super().__init__(f"{kind}: {msg}")
        self.kind = kind


# ---------- 좌표 기반 줄/토큰 처리 ----------

def lines_of(words: list[dict], tol: float = 2.5) -> list[list[dict]]:
    """단어를 같은 높이(top)끼리 묶어 줄로 만든다."""
    lines: list[list[dict]] = []
    for w in sorted(words, key=lambda w: (w["top"], w["x0"])):
        if lines and abs(lines[-1][0]["top"] - w["top"]) <= tol:
            lines[-1].append(w)
        else:
            lines.append([w])
    return [sorted(l, key=lambda w: w["x0"]) for l in lines]


def merge_numbers(line: list[dict], gap: float = 1.2) -> list[dict]:
    """'1' ',001' 처럼 붙어 있는 숫자 조각을 하나로 합친다."""
    out: list[dict] = []
    for w in line:
        if (out and NUM_RE.match(w["text"]) and NUM_RE.match(out[-1]["text"])
                and w["x0"] - out[-1]["x1"] < gap and out[-1]["text"] != "-" and w["text"] != "-"):
            p = out[-1]
            out[-1] = {**p, "text": p["text"] + w["text"], "x1": w["x1"]}
        else:
            out.append(dict(w))
    return out


def is_num(t: str) -> bool:
    return bool(NUM_RE.match(t)) and t not in {",", "."}


def to_int(t: str):
    return None if t == "-" else int(t.replace(",", ""))


def to_pct(t: str):
    if t == "-":
        return None
    if not t.endswith("%"):
        raise ValueError(t)
    return float(t[:-1])


def page_words(page) -> list[dict]:
    return page.extract_words(x_tolerance=1.5, keep_blank_chars=False, use_text_flow=False)


# ---------- 교차표 ----------

def find_total_row(words, min_pct: int):
    """'전체' 단어와 같은 높이에서 오른쪽이 모두 숫자인 곳을 찾는다(왼쪽 추이표와 섞이지 않게 단어 단위로 본다)."""
    for w in sorted(words, key=lambda w: (w["top"], w["x0"])):
        if w["text"] != "전체":
            continue
        right = merge_numbers(sorted([v for v in words if abs(v["top"] - w["top"]) < 3 and v["x0"] > w["x1"]],
                                     key=lambda v: v["x0"]))
        # 오른쪽에 다른 표가 붙어 있으면(예: 정당 지지 강도) 첫 글자 단어 앞에서 끊는다
        cut = next((k for k, t in enumerate(right) if not is_num(t["text"])), len(right))
        if cut >= 2 + min_pct:
            right_edge = right[cut]["x0"] - 2 if cut < len(right) else float("inf")
            return w, right[:cut], right_edge
    return None


def is_prefix(t: str) -> bool:
    return any(k.startswith(t) for k in CATEGORY_MAP)


def parse_crosstab(page, min_pct: int):
    """교차표 하나를 읽어 (머리글 줄, 열 기준점, 열 중심, 행 목록)을 돌려준다. 행 = [category, subgroup, 칸 값들]."""
    words = page_words(page)
    found = find_total_row(words, min_pct)
    if not found:
        raise ParseError("table_not_found", "'전체' 행을 찾지 못함")
    total_w, _, right_edge = found
    # 표의 왼쪽 경계 = '전체' 바로 아래 '지역별'의 시작 x. 그 왼쪽(추이표)은 버리고 줄을 다시 묶는다.
    below = [w for w in words if w["text"] == "지역별" and 0 < w["top"] - total_w["top"] < 25
             and w["x0"] < total_w["x0"]]
    if not below:
        raise ParseError("table_layout", "'전체' 아래에 '지역별'이 없음")
    left = max(w["x0"] for w in below) - 2
    # 오른쪽에 붙은 표의 '지역별'이 있으면 그 앞까지만 이 표로 본다
    last_x1 = max(t["x1"] for t in found[1])
    side = [w["x0"] for w in words if w["text"] == "지역별" and w["x0"] > last_x1 and 0 < w["top"] - total_w["top"] < 25]
    if side:
        right_edge = min(right_edge, min(side) - 2)
    lines = lines_of([w for w in words if left <= w["x0"] < right_edge])
    ti = next(i for i, l in enumerate(lines) if total_w in l)

    # 열 머리글 = '조사완료' 가 있는 줄부터 '전체' 행 바로 위까지(그 위의 질문 문구는 제외)
    hstart = next((k for k in range(ti - 1, max(-1, ti - 10), -1)
                   if any(w["text"] == "조사완료" for w in lines[k])), max(0, ti - 6))
    header_lines = [l for l in lines[hstart:ti] if l]

    raw_rows, label_x0s = [], []
    for l in lines[ti:]:
        toks = merge_numbers(l)
        if not toks:
            continue
        if toks[0]["text"].startswith("-") and len(toks) > 1 and not is_num(toks[1]["text"]):
            break  # 표 아래 주석("- 소수점 아래 ...")
        labels = [t for t in toks if not is_num(t["text"])]
        nums = [t for t in toks if is_num(t["text"])]
        if labels and nums and max(t["x0"] for t in labels) > min(t["x0"] for t in nums):
            break  # 숫자가 레이블 오른쪽에만 있어야 표 행이다
        if not nums:
            # 숫자 없는 줄: 구분 이름의 이어지는 줄('정당별')이거나, 값이 없는 행('대통령 직무 정지 중')
            raw_rows.append((labels, []))
            continue
        if not labels and raw_rows:
            raise ParseError("row_split", f"레이블 없는 숫자 줄: {[t['text'] for t in nums]}")
        raw_rows.append((labels, nums))
        label_x0s += [t["x0"] for t in labels]

    # 열 기준점: 모든 행의 숫자 토큰 오른쪽 끝 x 를 모아 4pt 안쪽끼리 한 열로 묶는다
    # ('전체' 행에 빈 칸이 있는 열도 놓치지 않기 위해)
    xs = sorted((t["x1"], (t["x0"] + t["x1"]) / 2) for _, nums in raw_rows for t in nums)
    clusters: list[list] = []
    for x1, c in xs:
        if clusters and x1 - clusters[-1][-1][0] < 4:
            clusters[-1].append((x1, c))
        else:
            clusters.append([(x1, c)])
    anchors = [sum(x for x, _ in cl) / len(cl) for cl in clusters]
    centers = [sum(c for _, c in cl) / len(cl) for cl in clusters]

    sub_x = Counter(round(x) for x in label_x0s).most_common(1)[0][0]
    blocks: list[str] = []      # 구분 블록별 이름(여러 줄을 이어 붙임)
    rows = []
    for labels, nums in raw_rows:
        cat_words = "".join(t["text"] for t in labels if t["x0"] < sub_x - 3)
        sub_words = [t["text"] for t in labels if t["x0"] >= sub_x - 3]
        if [t["text"] for t in labels] == ["전체"]:
            cat_words, sub_words = "", ["전체"]
        if cat_words:
            cur = blocks[-1] if blocks else None
            # 새 블록 시작: 블록이 없거나, 현재 이름이 완성됐거나, 이어 붙이면 아는 이름이 안 되는데 새 단어는 아는 이름의 시작일 때
            if cur is None or cur in CATEGORY_MAP or (not is_prefix(cur + cat_words) and is_prefix(cat_words)):
                blocks.append(cat_words)
            else:
                blocks[-1] = cur + cat_words
        if not nums:
            continue
        sub = " ".join(sub_words)
        cells = [None] * len(anchors)
        for t in nums:
            k = min(range(len(anchors)), key=lambda i: abs(anchors[i] - t["x1"]))
            if abs(anchors[k] - t["x1"]) > 6:
                raise ParseError("cell_misaligned", f"{sub}: '{t['text']}' 열을 정하지 못함")
            if cells[k] is not None:
                raise ParseError("cell_collision", f"{sub}: 한 칸에 값 두 개")
            cells[k] = t["text"]
        if sub == "전체":
            rows.append(["전체", sub, cells])
        elif not blocks:
            raise ParseError("category_unknown", f"'{sub}' 행의 구분을 정하지 못함")
        else:
            rows.append([len(blocks) - 1, sub, cells])

    for r in rows:
        if isinstance(r[0], int):
            name = blocks[r[0]]
            r[0] = CATEGORY_MAP.get(name, f"기타:{name}")
    return header_lines, anchors, centers, rows


def week_label_on_page(page) -> str | None:
    m = WEEK_RE.search(page.extract_text(x_tolerance=1.5) or "")
    return f"{m.group(1)}년 {int(m.group(2))}월 {m.group(3)}주" if m else None


def find_page(pdf, start: int, must: list[str], reject: list[str] = ()):
    for i in range(start, len(pdf.pages)):
        t = (pdf.pages[i].extract_text(x_tolerance=1.5) or "").replace(" ", "")
        if all(m.replace(" ", "") in t for m in must) and not any(r.replace(" ", "") in t for r in reject):
            return i
    return None


# ---------- 각 부분 파서 ----------

def parse_overview(pdf) -> dict:
    t = pdf.pages[0].extract_text() or ""
    out = {}

    def grab(key):
        m = re.search(rf"-\s*{key}\s*:\s*(.+)", t)
        return m.group(1).strip() if m else None

    period = grab("조사기간")
    out["survey_period"] = period
    out["sampling"] = grab("표본추출")
    out["method"] = grab("응답방식")
    target = grab("조사대상") or ""
    m = re.search(r"([\d,]+)\s*명", target)
    out["n_sample"] = to_int(m.group(1)) if m else None
    rr = grab("응답률") or ""
    m = re.search(r"([\d.]+)%", rr)
    out["response_rate"] = float(m.group(1)) if m else None
    m = re.search(r"총\s*통화\s*([\d,]+)\s*명", rr)
    out["response_calls"] = to_int(m.group(1)) if m else None
    m = re.search(r"([\d.]+)%", grab("접촉률") or "")
    out["contact_rate"] = float(m.group(1)) if m else None
    moe = grab("표본오차") or ""
    m = re.search(r"±\s*([\d.]+)\s*%", moe)
    out["margin_of_error"] = float(m.group(1)) if m else None

    s = e = None
    if period:
        m = re.match(r"(\d{4})년\s*(\d{1,2})월\s*(\d{1,2})일?\s*(?:~\s*(?:(\d{1,2})월\s*)?(\d{1,2})일)?", period)
        if m:
            y, mo, d = int(m.group(1)), int(m.group(2)), int(m.group(3))
            s = f"{y:04d}-{mo:02d}-{d:02d}"
            if m.group(5):
                mo2 = int(m.group(4)) if m.group(4) else mo
                y2 = y + 1 if mo2 < mo else y
                e = f"{y2:04d}-{mo2:02d}-{int(m.group(5)):02d}"
            else:
                e = s
    out["survey_start"], out["survey_end"] = s, e
    missing = [k for k in ("survey_period", "n_sample", "response_rate", "method", "survey_start") if not out.get(k)]
    if missing:
        raise ParseError("overview_missing", ",".join(missing))
    return out


def parse_se(pdf) -> tuple[dict, int | None]:
    i = find_page(pdf, 0, ["대통령 직무 수행 평가 표준오차"])
    if i is None:
        return {}, None
    t = pdf.pages[i].extract_text(x_tolerance=1.5) or ""
    out = {}
    for key, label in (("approve", "잘하고 있다"), ("disapprove", "잘못하고 있다")):
        m = re.search(rf"{label}\s+(\d+)%\s+([\d.]+)%\s+(\d+)%\s+(\d+)%", t)
        if m:
            out[f"{key}_se"] = float(m.group(2))
            out[f"{key}_ci_low"] = float(m.group(3))
            out[f"{key}_ci_high"] = float(m.group(4))
    return out, i


TITLE_WORDS = {"대통령", "직무", "수행", "평가", "정당", "지지도", "(현재", "지지하는", "정당)"}
SKIP_WORDS = {"조사완료", "가중적용", "사례수", "(명)"}


def column_names(header, centers) -> list[str]:
    """머리글 단어를 가장 가까운 열 중심에 배정하고 위에서 아래로 붙여 열 이름을 만든다.
    표 제목('대통령 직무 수행 평가', '정당 지지도 (현재 지지하는 정당)')이 있는 줄의 제목 단어는 뺀다."""
    title_tops = [w["top"] for l in header for w in l if w["text"] in ("지지도", "평가")]
    names = [[] for _ in centers]
    for l in header:
        for w in l:
            t = w["text"]
            if t in SKIP_WORDS or WEEK_RE.search(t) or re.fullmatch(r"\(.*일\)", t):
                continue
            if t in TITLE_WORDS and any(abs(w["top"] - tt) < 2 for tt in title_tops):
                continue
            c = (w["x0"] + w["x1"]) / 2
            k = min(range(len(centers)), key=lambda j: abs(centers[j] - c))
            if abs(centers[k] - c) < 22:
                names[k].append((w["top"], w["x0"], t))
    return ["".join(t for _, _, t in sorted(n)) for n in names]


def approval_column(name: str) -> str | None:
    n = name.replace(" ", "")
    if n.startswith("잘하고"):
        return "approve"
    if n.startswith("잘못하고"):
        return "disapprove"
    if "의견" in n or "유보" in n:
        return "reserved"
    if "쪽도" in n or n.startswith("어느"):
        return "neither"
    if n.startswith("모름") or "응답거절" in n:
        return "dont_know"
    return None


def parse_approval(pdf, week_label: str):
    i = find_page(pdf, 0, ["대통령 직무 수행 평가", "가중적용", "잘하고", "잘못하고", "성향별", week_label],
                  reject=["표준오차", "평가 이유"])
    if i is None:
        raise ParseError("approval_page_not_found", week_label)
    header, anchors, centers, rows = parse_crosstab(pdf.pages[i], min_pct=4)
    cols = [approval_column(c) for c in column_names(header, centers)[2:]]
    need = {"approve", "disapprove", "neither", "dont_know"}
    if None in cols or len(set(cols)) != len(cols) or not need <= set(cols):
        raise ParseError("approval_columns", f"열 이름을 읽지 못함: {column_names(header, centers)}")
    out = []
    for order, (cat, sub, cells) in enumerate(rows):
        try:
            n_raw = to_int(cells[0]) if cells[0] else None
            n_w = to_int(cells[1]) if cells[1] else None
            vals = {k: (to_pct(c) if c is not None else None) for k, c in zip(cols, cells[2:])}
        except ValueError as e:
            raise ParseError("bad_number", f"{sub}: {e}")
        suppressed = int(any(c == "-" for c in cells[2:]))
        blanks = ",".join(k for k, c in zip(cols, cells[2:]) if c is None)
        out.append(dict(category=cat, subgroup=sub, row_order=order, n_raw=n_raw, n_weighted=n_w,
                        approve=vals["approve"], disapprove=vals["disapprove"], neither=vals["neither"],
                        dont_know=vals["dont_know"], reserved=vals.get("reserved"),
                        suppressed=suppressed, blank_cells=blanks, page=i + 1))
    return out, i


def normalize_party(name: str) -> str:
    n = name.replace(" ", "")
    if "무당층" in n or "無黨" in n:
        return "무당층"
    if n.startswith("모름") or "응답거절" in n:
        return "모름/응답거절(무당층 중)"
    if n == "없음":
        return "없음(무당층 중)"
    if n in ("기타", "그외정당", "이외정당"):
        return "기타(그 외 정당)"
    return n


def parse_party(pdf, start: int, week_label: str):
    i = find_page(pdf, start, ["정당 지지도", "가중적용", "국민의힘", "성향별", week_label],
                  reject=["표준오차", "잘하고"])
    if i is None:
        raise ParseError("party_page_not_found", week_label)
    header, anchors, centers, rows = parse_crosstab(pdf.pages[i], min_pct=4)
    party_cols = [normalize_party(c) for c in column_names(header, centers)[2:]]
    if any(not c for c in party_cols) or len(set(party_cols)) != len(party_cols):
        raise ParseError("party_header", f"열 이름을 읽지 못함: {party_cols}")
    out = []
    for order, (cat, sub, cells) in enumerate(rows):
        n_raw = to_int(cells[0]) if cells[0] else None
        n_w = to_int(cells[1]) if cells[1] else None
        for k, (pname, c) in enumerate(zip(party_cols, cells[2:])):
            try:
                v = to_pct(c) if c is not None else None
            except ValueError as e:
                raise ParseError("bad_number", f"{sub}/{pname}: {e}")
            out.append(dict(category=cat, subgroup=sub, row_order=order, n_raw=n_raw, n_weighted=n_w,
                            party=pname, col_order=k, pct=v, suppressed=int(c == "-"), page=i + 1))
    return out, party_cols, i


ITEM_RE = re.compile(r"^(.*?)\s*(\d+)%$")
CHANGE_RE = re.compile(r"\s*\(([+-]\d+)\)")  # 증감 표시는 항목명 끝이나 중간에 올 수 있다


def parse_reasons(pdf):
    i = find_page(pdf, 0, ["긍정 평가 이유", "부정 평가 이유", "평가자"])
    if i is None:
        raise ParseError("reasons_page_not_found", "")
    page = pdf.pages[i]
    words = page_words(page)
    neg_head = next((w for l in lines_of(words) for j, w in enumerate(l)
                     if w["text"] == "부정" and j + 2 < len(l) and l[j + 1]["text"] == "평가" and l[j + 2]["text"] == "이유"), None)
    if neg_head is None:
        raise ParseError("reasons_layout", "부정 평가 이유 제목 위치를 찾지 못함")
    # 왼쪽(긍정) 칸의 '%' 바로 다음 단어가 오른쪽(부정) 칸의 시작이다. 그 x의 최솟값을 경계로 삼는다.
    starts = [l[j + 1]["x0"] for l in lines_of(words) if l[0]["top"] > neg_head["top"]
              for j in range(len(l) - 1) if l[j]["text"].endswith("%")]
    if not starts:
        raise ParseError("reasons_layout", "두 칸의 경계를 찾지 못함")
    split_x = min(starts) - 2
    text = page.extract_text(x_tolerance=1.5) or ""
    # 증감 기준 문구 전체를 남긴다(예: '지난주 대비', '직전 조사(2주 전, 5월 7~9일) 대비')
    m = re.search(r"-\s*([^\n]*?대비)\s*±", text)
    basis = m.group(1).strip() if m else None

    out = []
    for pol, (x0, x1) in (("positive", (0, split_x)), ("negative", (split_x, page.width))):
        region = [w for w in words if x0 <= w["x0"] < x1]
        base_n, base_label, items = None, None, []
        for l in lines_of(region):
            # 칸 안에서 첫 '%' 까지만 한 항목이다(오른쪽에 다른 도표가 붙은 호수가 있음)
            cut = next((j for j, w in enumerate(l) if w["text"].endswith("%")), None)
            if cut is not None:
                l = l[:cut + 1]
            s = " ".join(w["text"] for w in l).strip()
            mb = re.search(r"\((긍정|부정)\s*평가자\s*([\d,]+)\s*명\)", s)
            if mb:
                base_n, base_label = to_int(mb.group(2)), s
                continue
            if base_n is None or s.startswith("-"):
                continue
            mi = ITEM_RE.match(s)
            if mi and mi.group(1):
                chg = CHANGE_RE.findall(mi.group(1))
                if len(chg) > 1:
                    raise ParseError("reasons_change", f"증감 표시가 둘: {s}")
                name = re.sub(r"\s+", " ", CHANGE_RE.sub("", mi.group(1))).strip()
                items.append((name, float(mi.group(2)), float(chg[0]) if chg else None))
        if base_n is None or not items:
            raise ParseError("reasons_empty", pol)
        for r, (name, pct, chg) in enumerate(items, 1):
            out.append(dict(polarity=pol, rank=r, item=name, pct=pct, change_pp=chg,
                            base_n=base_n, base_label=base_label, change_basis=basis, page=i + 1))
    return out, i


# ---------- 검증 ----------

def validate(ov, appr, reasons, party, party_cols):
    errs, warns = [], []
    for r in appr + party:
        if r["category"].startswith("기타:"):
            warns.append(("extra_category", f"이 호수에만 있는 구분 '{r['category']}' / {r['subgroup']}"))
    if appr:
        total = next((r for r in appr if r["category"] == "전체"), None)
        if not total:
            return [("no_total_row", "직무 평가 '전체' 행 없음")], warns
        if total["n_raw"] != ov["n_sample"]:
            errs.append(("n_mismatch", f"개요 {ov['n_sample']} vs 직무 평가 표 {total['n_raw']}"))
        cats = {r["category"] for r in appr}
        for c in EXPECTED_CATEGORIES:
            if c not in cats:
                errs.append(("category_missing", f"직무 평가 표에 '{c}' 없음"))
        for c in EXHAUSTIVE:
            s = sum(r["n_raw"] or 0 for r in appr if r["category"] == c)
            if s and s != total["n_raw"]:
                errs.append(("group_n_sum", f"직무 평가 {c} 사례수 합 {s} != 전체 {total['n_raw']}"))
        for r in appr:
            vals = [r[k] for k in ("approve", "disapprove", "neither", "dont_know")]
            if r["suppressed"]:
                if (r["n_raw"] or 0) >= 50 and (r["n_weighted"] or 0) >= 50:
                    warns.append(("suppressed_large_n", f"{r['category']}/{r['subgroup']}"))
                continue
            s = sum(v for v in vals if v is not None)
            if not 98 <= s <= 102:
                errs.append(("approval_sum", f"{r['category']}/{r['subgroup']} 합 {s}"))
            if r["reserved"] is not None:
                parts = (r["neither"] or 0) + (r["dont_know"] or 0)
                if abs(r["reserved"] - parts) > 1:
                    errs.append(("reserved_sum", f"{r['category']}/{r['subgroup']} 의견유보 {r['reserved']} != {parts}"))
            if r["blank_cells"]:
                warns.append(("blank_cell", f"{r['category']}/{r['subgroup']}: {r['blank_cells']} 빈 칸(합 {s})"))
        for pol in ("positive", "negative"):
            rs = [r for r in reasons if r["polarity"] == pol]
            s = sum(r["pct"] for r in rs)
            # 이유는 20~30개 항목을 각각 정수로 반올림해 싣기 때문에 합이 100에서 몇 %p 벗어날 수 있다.
            # 98~102 밖이면 경고, 95~106 밖이면 파싱 오류로 본다.
            if not 95 <= s <= 106:
                errs.append(("reasons_sum", f"{pol} 합 {s} ({len(rs)}개 항목)"))
            elif not 98 <= s <= 102:
                warns.append(("reasons_sum_rounding", f"{pol} 합 {s} ({len(rs)}개 항목)"))
            expect = round(total[{"positive": "approve", "negative": "disapprove"}[pol]] / 100 * total["n_weighted"])
            if rs and abs(rs[0]["base_n"] - expect) > 15:
                warns.append(("reasons_base", f"{pol} 응답자 {rs[0]['base_n']} vs 전체×비율 {expect}"))

    main_cols = [c for c in party_cols if "무당층 중" not in c]
    by_row: dict = {}
    for r in party:
        by_row.setdefault((r["category"], r["subgroup"]), []).append(r)
    ptotal = by_row.get(("전체", "전체"))
    if not ptotal or ptotal[0]["n_raw"] != ov["n_sample"]:
        errs.append(("party_n_mismatch", "정당 표 전체 사례수가 조사 개요 표본 수와 다름"))
    for c in EXHAUSTIVE:
        s = sum(rs[0]["n_raw"] or 0 for (cat, _), rs in by_row.items() if cat == c)
        if s and s != ov["n_sample"]:
            errs.append(("group_n_sum", f"정당 표 {c} 사례수 합 {s} != 전체 {ov['n_sample']}"))
    for (c, sgrp), rs in by_row.items():
        if any(r["suppressed"] for r in rs):
            continue
        s = sum(r["pct"] or 0 for r in rs if r["party"] in main_cols)
        if not 98 <= s <= 102:
            errs.append(("party_sum", f"{c}/{sgrp} 합 {s}"))
        sub = [r["pct"] for r in rs if "무당층 중" in r["party"]]
        nop = next((r["pct"] for r in rs if r["party"] == "무당층"), None)
        if nop is not None and sub and abs(sum(v or 0 for v in sub) - nop) > 1:
            errs.append(("party_noparty_sum", f"{c}/{sgrp} 무당층 {nop} != 세부 합 {sum(v or 0 for v in sub)}"))
    pcats = {r["category"] for r in party}
    expected = PARTY_EXPECTED_CATEGORIES if appr else [c for c in PARTY_EXPECTED_CATEGORIES if c != "직무평가"]
    for c in expected:
        if c not in pcats:
            errs.append(("category_missing", f"정당 표에 '{c}' 없음"))
    return errs, warns


# ---------- 실행 ----------

def load_manifest():
    with open(DATA / "manifest.csv", encoding="utf-8-sig") as f:
        return [r for r in csv.DictReader(f) if r["issue"] and r["status"] == "downloaded"]


def parse_issue(m: dict):
    with pdfplumber.open(ROOT / m["local_path"]) as pdf:
        ov = parse_overview(pdf)
        cover = (pdf.pages[0].extract_text() or "").replace(" ", "")
        # 2024-12-14 탄핵소추안 가결 뒤에는 '직무 정지로 직무 평가 불가' (직무 평가·이유 문항 없음)
        if "직무평가불가" in cover:
            ov["approval_status"] = "not_asked"
            se, se_page, appr, ap, reasons, rp = {}, None, [], None, [], None
        else:
            ov["approval_status"] = "asked"
            se, se_page = parse_se(pdf)
            appr, ap = parse_approval(pdf, m["week_label"])
            reasons, rp = parse_reasons(pdf)
        party, party_cols, pp = parse_party(pdf, (ap + 1) if ap is not None else 0, m["week_label"])
    errs, warns = validate(ov, appr, reasons, party, party_cols)
    if appr and "approve_se" not in se:
        warns.append(("se_missing", "직무 평가 표준오차를 읽지 못함(페이지가 회전돼 있는 등) → 비워 둠"))
    pg = lambda i: "-" if i is None else i + 1
    pages = f"approval:{pg(ap)},reasons:{pg(rp)},party:{pg(pp)},se:{pg(se_page)}"
    return {**ov, **se, "pages": pages}, appr, reasons, party, errs, warns


def parse_range(s: str) -> set[int]:
    out = set()
    for part in s.split(","):
        a, _, b = part.partition("-")
        out |= set(range(int(a), int(b or a) + 1))
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--issues", help="예: 495-504,510")
    ap.add_argument("--force", action="store_true")
    args = ap.parse_args()

    con = sqlite3.connect(DB)
    con.executescript(SCHEMA)
    done = {r[0] for r in con.execute("SELECT issue FROM survey")}
    todo = load_manifest()
    if args.issues:
        want = parse_range(args.issues)
        todo = [m for m in todo if int(m["issue"]) in want]

    fail_path = DATA / "parse_failures.csv"
    old_fail = []
    if fail_path.exists():
        with open(fail_path, encoding="utf-8-sig") as f:
            old_fail = [r for r in csv.DictReader(f)]
    redo = {int(m["issue"]) for m in todo if args.force or int(m["issue"]) not in done}
    failures = [r for r in old_fail if int(r["issue"]) not in redo]
    warn_path = DATA / "parse_warnings.csv"
    old_warn = []
    if warn_path.exists():
        with open(warn_path, encoding="utf-8-sig") as f:
            old_warn = [r for r in csv.DictReader(f)]
    warnings = [r for r in old_warn if int(r["issue"]) not in redo]

    ok = 0
    for m in todo:
        issue = int(m["issue"])
        if issue not in redo:
            continue
        for t in ("survey", "approval_by_group", "reasons", "party_by_group"):
            con.execute(f"DELETE FROM {t} WHERE issue=?", (issue,))
        try:
            sv, appr, reasons, party, errs, warns = parse_issue(m)
        except ParseError as e:
            failures.append({"issue": issue, "kind": e.kind, "detail": str(e)})
            print(f"제{issue}호 실패 {e}")
            continue
        except Exception as e:  # 예상 못한 오류도 기록하고 다음 호수로
            failures.append({"issue": issue, "kind": "exception", "detail": repr(e)})
            print(f"제{issue}호 예외 {e!r}")
            continue
        for k, d in dict.fromkeys(warns):
            warnings.append({"issue": issue, "kind": k, "detail": d})
        if errs:
            for k, d in errs:
                failures.append({"issue": issue, "kind": k, "detail": d})
            print(f"제{issue}호 검증 실패 {len(errs)}건: {errs[:3]}")
            continue
        sv.update(issue=issue, week_label=m["week_label"], post_date=m["post_date"], pdf_url=m["pdf_url"])
        con.execute(f"INSERT INTO survey ({','.join(sv)}) VALUES ({','.join('?' * len(sv))})", list(sv.values()))
        for table, rows in (("approval_by_group", appr), ("reasons", reasons), ("party_by_group", party)):
            for r in rows:
                r = {"issue": issue, **r}
                con.execute(f"INSERT INTO {table} ({','.join(r)}) VALUES ({','.join('?' * len(r))})", list(r.values()))
        con.commit()
        ok += 1
        print(f"제{issue}호 OK  직무평가 {len(appr)}행, 이유 {len(reasons)}개, 정당 {len(party)}칸, 경고 {len(warns)}")

    for path, rows in ((fail_path, failures), (warn_path, warnings)):
        with open(path, "w", newline="", encoding="utf-8-sig") as f:
            w = csv.DictWriter(f, fieldnames=["issue", "kind", "detail"])
            w.writeheader()
            w.writerows(sorted(rows, key=lambda r: int(r["issue"])))
    n_total = con.execute("SELECT COUNT(*) FROM survey").fetchone()[0]
    print(f"이번 실행 성공 {ok}/{len(redo)}, DB 전체 {n_total}개 호수")
    kinds = Counter(r["kind"] for r in failures)
    if kinds:
        print("실패 유형:", dict(kinds))


if __name__ == "__main__":
    main()
