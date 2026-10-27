"""SQLite 연결과 날짜 기준 조회."""
import sqlite3
from datetime import date
from pathlib import Path

from config import ASSEMBLY_DB, ROOT

SCHEMA = ROOT / "src" / "schema.sql"


def connect(path: Path | str = ASSEMBLY_DB) -> sqlite3.Connection:
    path = Path(path) if path != ":memory:" else path
    if isinstance(path, Path):
        path.parent.mkdir(parents=True, exist_ok=True)
    con = sqlite3.connect(str(path))
    con.row_factory = sqlite3.Row
    con.execute("PRAGMA foreign_keys=ON")
    con.executescript(SCHEMA.read_text(encoding="utf-8"))
    return con


def _active(alias: str, on: str) -> str:
    # start <= on 이고 (end 없음 또는 end > on)
    return f"{alias}.start_date <= '{on}' AND ({alias}.end_date IS NULL OR {alias}.end_date > '{on}')"


def seats_on(con: sqlite3.Connection, on: str | None = None) -> dict:
    """특정 날짜 기준 정당별 의석수. 의원직 보유 기간과 당적 이력을 함께 본다.

    반환: {"date", "total", "vacant", "by_party": {정당: 수}, "unknown_party": [의원코드]}
    """
    on = on or date.today().isoformat()
    for v in (on,):
        date.fromisoformat(v)  # SQL에 넣기 전 형식 검증
    rows = con.execute(
        f"""SELECT t.member_id, p.party
            FROM member_terms t
            LEFT JOIN party_affiliations p
              ON p.member_id = t.member_id AND {_active('p', on)}
            WHERE {_active('t', on)}"""
    ).fetchall()
    by_party: dict[str, int] = {}
    unknown = []
    seen = set()
    for r in rows:
        if r["member_id"] in seen:
            continue
        seen.add(r["member_id"])
        if r["party"] is None:
            unknown.append(r["member_id"])
            continue
        by_party[r["party"]] = by_party.get(r["party"], 0) + 1
    total = len(seen)
    from config import TOTAL_SEATS
    return {
        "date": on,
        "total": total,
        "vacant": TOTAL_SEATS - total,
        "by_party": dict(sorted(by_party.items(), key=lambda x: -x[1])),
        "unknown_party": unknown,
    }


def compute_stage(b: dict) -> str:
    """법안 행의 날짜·결과 칸으로 진행 단계를 정한다."""
    res = (b.get("proc_result") or "").strip()
    if res:
        if any(k in res for k in ("폐기", "부결", "철회", "반려")):
            return "폐기·철회"
        if "가결" in res:
            return "본회의 통과"
        return res
    if b.get("law_proc_dt"):
        return "본회의 대기"
    if b.get("law_submit_dt") or b.get("cmt_proc_dt"):
        return "법사위 심사"
    if b.get("cmt_present_dt"):
        return "소관위 심사"
    return "접수"
