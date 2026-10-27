"""1단계 수집: 한국갤럽 데일리 오피니언 보고서 목록을 만들고 PDF를 내려받는다.

실행 예:
    python src/collect.py              # 대상 기간 전체
    python src/collect.py --limit 10   # 대상 기간 앞쪽 10개만

- 요청 전에 robots.txt 를 확인하고, 막힌 경로는 요청하지 않는다.
- 요청 사이에 config 의 min_interval_sec 이상 쉰다.
- 받은 HTML/PDF 는 data/raw/ 에 캐시하고 다시 받지 않는다.
"""
from __future__ import annotations

import argparse
import csv
import datetime as dt
import hashlib
import html as htmllib
import re
import sys
import time
import urllib.robotparser
from pathlib import Path
from urllib.parse import urlparse

import requests
import yaml

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "data"
RAW_HTML = DATA / "raw" / "html"
RAW_PDF = DATA / "raw" / "pdf"

TITLE_RE = re.compile(r"데일리\s*오피니언\s*제\s*(\d+)\s*호\s*\(\s*(\d{4})년\s*(\d{1,2})월\s*(\d)주\s*\)")
ITEM_RE = re.compile(
    r"fn_viewContents\('(\d+)'\);\s*return false;\">(.*?)</a>.*?(\d{4}/\d{2}/\d{2})",
    re.S,
)
LAST_PAGE_RE = re.compile(r"fn_goPage\((\d+)\);\s*return false;\">마지막")
PDF_RE = re.compile(r"https?://[^\"'\s<>]*GallupKoreaDailyOpinion_(\d+)\((\d{8})\)\.pdf", re.I)


def load_config() -> dict:
    with open(ROOT / "config.yaml", encoding="utf-8") as f:
        return yaml.safe_load(f)


class PoliteClient:
    """robots.txt 준수, 요청 간격 유지, User-Agent 명시."""

    def __init__(self, cfg: dict):
        c = cfg["collect"]
        self.ua = c["user_agent"]
        self.interval = float(c["min_interval_sec"])
        self.timeout = c["timeout_sec"]
        self.s = requests.Session()
        self.s.headers["User-Agent"] = self.ua
        self._last = 0.0
        self._robots: dict[str, urllib.robotparser.RobotFileParser | None] = {}
        self.robots_log: list[str] = []

    def _wait(self):
        gap = time.monotonic() - self._last
        if gap < self.interval:
            time.sleep(self.interval - gap)
        self._last = time.monotonic()

    def robots(self, url: str):
        host = urlparse(url).netloc
        if host in self._robots:
            return self._robots[host]
        rurl = f"https://{host}/robots.txt"
        self._wait()
        r = self.s.get(rurl, timeout=self.timeout)
        ctype = r.headers.get("Content-Type", "")
        if r.status_code == 200 and "text/plain" in ctype:
            rp = urllib.robotparser.RobotFileParser()
            rp.parse(r.text.splitlines())
            self._robots[host] = rp
            self.robots_log.append(f"{rurl}: HTTP 200 ({ctype}) -> 규칙 적용\n{r.text.strip()}")
        else:
            # 404 이거나, 200 이지만 HTML 오류 페이지인 경우 = robots.txt 없음 = 제한 없음
            self._robots[host] = None
            self.robots_log.append(
                f"{rurl}: HTTP {r.status_code} ({ctype or '-'}) -> robots.txt 없음(오류 페이지), 제한 규칙 없음"
            )
        return self._robots[host]

    def allowed(self, url: str) -> bool:
        rp = self.robots(url)
        return True if rp is None else rp.can_fetch(self.ua, url)

    def request(self, method: str, url: str, **kw) -> requests.Response:
        if not self.allowed(url):
            raise PermissionError(f"robots.txt 가 막은 경로: {url}")
        # 연결 끊김 같은 네트워크 오류만 간격을 늘려 가며 다시 시도한다(4, 8, 16, 32초)
        for attempt in range(5):
            self._wait()
            try:
                return self.s.request(method, url, timeout=self.timeout, **kw)
            except (requests.ConnectionError, requests.Timeout) as e:
                if attempt == 4:
                    raise
                delay = 4 * 2 ** attempt
                print(f"  네트워크 오류({type(e).__name__}), {delay}초 뒤 재시도: {url}")
                time.sleep(delay)


def cached_html(client: PoliteClient, name: str, method: str, url: str, **kw) -> str:
    path = RAW_HTML / name
    if path.exists():
        return path.read_text(encoding="utf-8")
    r = client.request(method, url, **kw)
    r.raise_for_status()
    text = r.content.decode("cp949", errors="replace")
    path.write_text(text, encoding="utf-8")
    return text


def build_index(client: PoliteClient, cfg: dict) -> list[dict]:
    """연도별 목록 페이지를 돌며 데일리 오피니언 호수/주차/게시일/게시물 번호를 모은다."""
    c = cfg["collect"]
    rows: dict[int, dict] = {}
    for year in c["years"]:
        page, last = 1, 1
        while page <= last:
            html = cached_html(
                client,
                f"list_{year}_p{page:02d}.html",
                "POST",
                c["list_url"],
                data={"selectYear": str(year), "pagePos": str(page),
                      "p_menu_1": "data", "p_submenu_1": "data01"},
            )
            m = LAST_PAGE_RE.search(html)
            if m:
                last = int(m.group(1))
            for seq, title, posted in ITEM_RE.findall(html):
                title = htmllib.unescape(re.sub(r"<[^>]+>", "", title)).replace("\xa0", " ").strip()
                t = TITLE_RE.search(title)
                if not t:
                    continue
                issue = int(t.group(1))
                rows[issue] = {
                    "issue": issue,
                    "week_label": f"{t.group(2)}년 {int(t.group(3))}월 {t.group(4)}주",
                    "post_date": posted.replace("/", "-"),
                    "seq_no": int(seq),
                    "title": title,
                }
            page += 1
    out = sorted(rows.values(), key=lambda r: r["issue"])
    with open(DATA / "report_index.csv", "w", newline="", encoding="utf-8-sig") as f:
        w = csv.DictWriter(f, fieldnames=list(out[0].keys()))
        w.writeheader()
        w.writerows(out)
    return out


def in_period(row: dict, start: dt.date, end: dt.date) -> bool:
    d = dt.date.fromisoformat(row["post_date"])
    # 게시일(보통 금요일)이 재임 기간 안에 있으면 대상. 조사 기간은 2단계에서 다시 확인한다.
    return start <= d <= end


def candidate_urls(issue: int, post_date: dt.date) -> list[str]:
    urls = []
    for delta in [0, -1, 1, -2, 2, -3, 3]:
        ymd = (post_date + dt.timedelta(days=delta)).strftime("%Y%m%d")
        for base in ("https://www.gallup.co.kr/dir/GallupKoreaDaily",
                     "https://panel.gallup.co.kr/Contents/GallupKoreaDaily"):
            urls.append(f"{base}/GallupKoreaDailyOpinion_{issue}({ymd}).pdf")
    return urls


def fetch_pdf(client: PoliteClient, cfg: dict, row: dict) -> dict:
    issue = row["issue"]
    existing = list(RAW_PDF.glob(f"GallupKoreaDailyOpinion_{issue}(*).pdf"))
    if existing:
        p = existing[0]
        chtml = RAW_HTML / f"content_{row['seq_no']}.html"
        m = PDF_RE.search(chtml.read_text(encoding="utf-8")) if chtml.exists() else None
        url = m.group(0) if m else ""
        return {"status": "downloaded", "local_path": str(p.relative_to(ROOT)), "pdf_url": url,
                "bytes": p.stat().st_size, "sha256": hashlib.sha256(p.read_bytes()).hexdigest(),
                "note": "cache"}

    html = cached_html(client, f"content_{row['seq_no']}.html", "GET",
                       cfg["collect"]["content_url"].format(seq=row["seq_no"]))
    found = [m for m in PDF_RE.finditer(html) if int(m.group(1)) == issue]
    urls = [found[0].group(0)] if found else []
    note = "게시물 첨부 링크" if found else "첨부 링크 없음 → 주소 추정"
    if not found:
        urls = candidate_urls(issue, dt.date.fromisoformat(row["post_date"]))

    for url in urls:
        try:
            r = client.request("GET", url)
        except PermissionError as e:
            note += f"; {e}"
            continue
        if r.status_code == 200 and r.content[:4] == b"%PDF":
            name = urlparse(url).path.rsplit("/", 1)[-1]
            p = RAW_PDF / name
            p.write_bytes(r.content)
            return {"status": "downloaded", "local_path": str(p.relative_to(ROOT)), "pdf_url": url,
                    "bytes": len(r.content), "sha256": hashlib.sha256(r.content).hexdigest(),
                    "note": note}
    return {"status": "pdf_not_found", "local_path": "", "pdf_url": "", "bytes": "",
            "sha256": "", "note": note}


def missing_weeks(rows: list[dict], start: dt.date, end: dt.date) -> list[str]:
    have = {dt.date.fromisoformat(r["post_date"]).isocalendar()[:2] for r in rows}
    out, d = [], start - dt.timedelta(days=start.weekday())  # 시작 주 월요일
    while d <= end:
        if d.isocalendar()[:2] not in have:
            out.append(d.isoformat())
        d += dt.timedelta(days=7)
    return out


def write_manifest(targets: list[dict], results: dict[int, dict], gaps: list[str]):
    fields = ["issue", "week_label", "post_date", "seq_no", "status", "pdf_url",
              "local_path", "bytes", "sha256", "note", "title"]
    prev = {}
    mpath = DATA / "manifest.csv"
    if mpath.exists():
        with open(mpath, encoding="utf-8-sig") as f:
            prev = {int(r["issue"]): r for r in csv.DictReader(f) if r["issue"]}
    with open(mpath, "w", newline="", encoding="utf-8-sig") as f:
        w = csv.DictWriter(f, fieldnames=fields)
        w.writeheader()
        for r in targets:
            res = results.get(r["issue"]) or prev.get(r["issue"]) or {"status": "not_yet"}
            w.writerow({**{k: r.get(k, "") for k in fields}, **{k: res.get(k, "") for k in
                        ("status", "pdf_url", "local_path", "bytes", "sha256", "note")}})
        for monday in gaps:
            w.writerow({"week_label": f"{monday} 시작 주", "status": "no_report_this_week",
                        "note": "목록에 해당 주 데일리 오피니언 없음(조사 휴지 추정)"})


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--limit", type=int, default=None, help="앞쪽 N개 호수만 내려받기")
    args = ap.parse_args()

    cfg = load_config()
    RAW_HTML.mkdir(parents=True, exist_ok=True)
    RAW_PDF.mkdir(parents=True, exist_ok=True)
    start = dt.date.fromisoformat(str(cfg["government"]["start"]))
    end = dt.date.fromisoformat(str(cfg["government"]["end"]))

    client = PoliteClient(cfg)
    for host in ("https://www.gallup.co.kr/", "https://panel.gallup.co.kr/"):
        client.robots(host)
    (DATA / "robots_check.txt").write_text(
        f"확인 시각: {dt.datetime.now().isoformat(timespec='seconds')}\n\n" + "\n\n".join(client.robots_log) + "\n",
        encoding="utf-8")

    index = build_index(client, cfg)
    targets = [r for r in index if in_period(r, start, end)]
    gaps = missing_weeks(targets, start, end)
    todo = targets[: args.limit] if args.limit else targets
    print(f"목록 전체 {len(index)}개, 대상 기간 {len(targets)}개, 이번 실행 {len(todo)}개, 보고서 없는 주 {len(gaps)}개")

    results = {}
    for i, r in enumerate(todo, 1):
        res = fetch_pdf(client, cfg, r)
        results[r["issue"]] = res
        print(f"[{i}/{len(todo)}] 제{r['issue']}호 {r['post_date']} {res['status']} {res['note']}")
        write_manifest(targets, results, gaps)
    write_manifest(targets, results, gaps)
    bad = [k for k, v in results.items() if v["status"] != "downloaded"]
    if bad:
        print("받지 못한 호수:", bad)
        sys.exit(1)


if __name__ == "__main__":
    main()
