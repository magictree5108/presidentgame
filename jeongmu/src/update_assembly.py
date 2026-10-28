"""22대 국회 데이터 수집·증분 갱신.

사용:
  python src/update_assembly.py            # 증분 갱신(매일 새벽 예약 실행용)
  python src/update_assembly.py --full     # 처음부터 전부(캐시는 그대로 사용)
  python src/update_assembly.py --no-votes # 의원별 표결 제외(빠른 확인용)

순서: 의원 → 법안 → 의안별 표결 → 의원별 표결 → 당적 이력 재구성 → 수동 보정 CSV 반영
"""
import argparse
import csv
import json
import sys
from datetime import date, datetime, timedelta

sys.path.insert(0, str(__import__("pathlib").Path(__file__).parent))

import assembly_api as api
from api_fields import SERVICES, pick
from config import DATA, TERM_START
from db import compute_stage, connect

TODAY = date.today().isoformat()
# 실존 인물 보호: 연락처·생년월일·보좌진 등은 원본(raw_json)에도 남기지 않는다
PRIVATE_FIELDS = {"TEL_NO", "E_MAIL", "BTH_DATE", "BTH_GBN_NM", "STAFF", "SECRETARY", "SECRETARY2",
                  "ASSEM_ADDR", "ASSEM_TEL", "ASSEM_EMAIL", "ROOM_NO", "MEM_TITLE", "SEX_GBN_NM"}


def public(r: dict) -> dict:
    return {k: v for k, v in r.items() if k not in PRIVATE_FIELDS}


def log(msg: str) -> None:
    print(f"[{datetime.now():%H:%M:%S}] {msg}", flush=True)


def norm_date(v):
    if not v:
        return None
    s = str(v).strip().replace(".", "-").replace("/", "-")
    if len(s) >= 8 and s[:8].isdigit():  # '20261001 150401' 형식
        s = s[:8]
    s = s[:10]
    if len(s) == 8 and s.isdigit():
        s = f"{s[:4]}-{s[4:6]}-{s[6:]}"
    try:
        date.fromisoformat(s)
        return s
    except ValueError:
        return None


def split_names(v: str | None) -> list[str]:
    if not v:
        return []
    out = []
    for part in str(v).replace("·", ",").split(","):
        n = part.strip()
        if n:
            out.append(n)
    return out


# ---------------------------------------------------------------- 의원
def load_members(con, use_cache=True) -> int:
    s = SERVICES["members"]
    rows = list(api.fetch_all(s["code"], s["params"], use_cache=use_cache))
    log(f"의원 {len(rows)}명 수신")
    current_ids = set()
    for r in rows:
        mid = pick(r, "members", "member_id")
        if not mid:
            continue
        current_ids.add(mid)
        party = pick(r, "members", "party")
        con.execute(
            """INSERT INTO members(member_id,name,name_hanja,name_eng,district,elect_type,
                 reelection,units,current_party,committees,homepage,raw_json,updated_at)
               VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?)
               ON CONFLICT(member_id) DO UPDATE SET name=excluded.name,
                 name_hanja=excluded.name_hanja,name_eng=excluded.name_eng,
                 district=excluded.district,elect_type=excluded.elect_type,
                 reelection=excluded.reelection,units=excluded.units,
                 current_party=excluded.current_party,committees=excluded.committees,
                 homepage=excluded.homepage,raw_json=excluded.raw_json,
                 updated_at=excluded.updated_at""",
            (mid, pick(r, "members", "name"), pick(r, "members", "name_hanja"),
             pick(r, "members", "name_eng"), pick(r, "members", "district"),
             pick(r, "members", "elect_type"), pick(r, "members", "reelection"),
             pick(r, "members", "units"), party, pick(r, "members", "committees"),
             pick(r, "members", "homepage"), json.dumps(public(r), ensure_ascii=False), TODAY),
        )
        # 의원직 기간: 처음 보는 현직 의원은 기본값으로 임기 시작일부터 현직.
        # (보궐·승계 의원의 실제 시작일은 data/member_terms.csv 로 보정)
        if not con.execute("SELECT 1 FROM member_terms WHERE member_id=?", (mid,)).fetchone():
            first_run = con.execute("SELECT value FROM meta WHERE key='first_roster_date'").fetchone()
            start = TERM_START if not first_run else TODAY
            reason = "총선 당선(기본값)" if not first_run else "명단 신규 등장(감지일, 보정 필요)"
            con.execute(
                "INSERT INTO member_terms VALUES(?,?,?,?,?,?)",
                (mid, start, reason, None, None, f"{s['code']} 명단 {TODAY}"),
            )
        # 당적 스냅샷 변화 감지
        if party:
            cur = con.execute(
                "SELECT party,start_date FROM party_affiliations WHERE member_id=? AND end_date IS NULL",
                (mid,),
            ).fetchone()
            if cur is None:
                start = con.execute(
                    "SELECT start_date FROM member_terms WHERE member_id=? ORDER BY start_date DESC",
                    (mid,),
                ).fetchone()[0]
                con.execute("INSERT OR IGNORE INTO party_affiliations VALUES(?,?,?,?,?)",
                            (mid, party, start, None, f"{s['code']} 명단 {TODAY}"))
            elif cur["party"] != party:
                con.execute(
                    "UPDATE party_affiliations SET end_date=? WHERE member_id=? AND end_date IS NULL",
                    (TODAY, mid),
                )
                con.execute("INSERT OR REPLACE INTO party_affiliations VALUES(?,?,?,?,?)",
                            (mid, party, TODAY, None,
                             f"명단 당적 변경 감지 {TODAY}(실제 변경일은 보정 필요)"))
                log(f"당적 변경 감지: {pick(r, 'members', 'name')} {cur['party']} → {party}")

    # 명단에서 사라진 현직 → 의원직 종료(사유 미확인)로 기록
    if rows:
        for row in con.execute("SELECT member_id FROM member_terms WHERE end_date IS NULL").fetchall():
            if row["member_id"] not in current_ids:
                con.execute(
                    "UPDATE member_terms SET end_date=?, end_reason=? WHERE member_id=? AND end_date IS NULL",
                    (TODAY, "명단에서 사라짐(사유·날짜 보정 필요)", row["member_id"]),
                )
                con.execute(
                    "UPDATE party_affiliations SET end_date=? WHERE member_id=? AND end_date IS NULL",
                    (TODAY, row["member_id"]),
                )
                log(f"명단에서 사라진 의원: {row['member_id']}")
        con.execute("INSERT OR IGNORE INTO meta VALUES('first_roster_date', ?)", (TODAY,))
    return len(rows)


def name_index(con) -> dict[str, list[str]]:
    idx: dict[str, list[str]] = {}
    for r in con.execute("SELECT member_id,name FROM members"):
        idx.setdefault(r["name"], []).append(r["member_id"])
    return idx


# ---------------------------------------------------------------- 법안
def save_sponsors(con, bid, b, idx):
    """대표·공동발의자. API가 주는 의원코드(RST_MONA_CD/PUBL_MONA_CD)를 이름과 짝지어 쓰고,
    코드가 없을 때만 이름으로 찾는다(동명이인이면 비움)."""
    def pairs(names, ids):
        ns, cs = split_names(names), split_names(ids)
        return list(zip(ns, cs)) if len(ns) == len(cs) else [(n, None) for n in ns]
    seen = set()
    for role, nm_key, id_key in (("lead", "lead", "lead_id"), ("co", "co", "co_ids")):
        for nm, mid in pairs(b.get(nm_key), b.get(id_key)):
            if nm in seen:
                continue
            seen.add(nm)
            if not mid:
                ids = idx.get(nm, [])
                mid = ids[0] if len(ids) == 1 else None
            con.execute("INSERT OR IGNORE INTO bill_sponsors VALUES(?,?,?,?)", (bid, mid, nm, role))


def load_other_bills(con, use_cache=True) -> int:
    """의원 발의 API에 없는 법안(위원장 대안, 정부 제출 등)을 의안검색 API로 보충한다."""
    s = SERVICES["all_bills"]
    idx = name_index(con)
    have = {r[0] for r in con.execute("SELECT bill_id FROM bills")}
    n = 0
    for r in api.fetch_all(s["code"], s["params"], use_cache=use_cache):
        bid = pick(r, "all_bills", "bill_id")
        if not bid or bid in have:
            continue
        b = {k: pick(r, "all_bills", k) for k in s["fields"]}
        for k in ("propose_dt", "cmt_present_dt", "cmt_proc_dt", "law_submit_dt", "law_proc_dt", "plenary_dt"):
            b[k] = norm_date(b[k])
        b["stage"] = compute_stage(b)
        con.execute(
            """INSERT OR REPLACE INTO bills(bill_id,bill_no,bill_name,proposer_kind,proposer,propose_dt,
                 committee,committee_id,cmt_present_dt,cmt_proc_dt,cmt_result,law_submit_dt,
                 law_proc_dt,law_result,plenary_dt,proc_result,stage,detail_link,raw_json,updated_at)
               VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
            (bid, b["bill_no"], b["bill_name"], b["proposer_kind"], b["proposer"], b["propose_dt"],
             b["committee"], b["committee_id"], b["cmt_present_dt"], b["cmt_proc_dt"], b["cmt_result"],
             b["law_submit_dt"], b["law_proc_dt"], b["law_result"], b["plenary_dt"], b["proc_result"],
             b["stage"], b["detail_link"], json.dumps(r, ensure_ascii=False), TODAY))
        if b.get("lead"):
            save_sponsors(con, bid, b, idx)
        n += 1
    log(f"위원장 대안·정부안 등 보충 {n}건")
    return n


def load_committees(con) -> int:
    """위원회 현황과 위원 명단(현재 시점 스냅샷). 바뀐 부분만 날짜를 남긴다.
    연락처·보좌진 정보는 저장하지 않는다."""
    s = SERVICES["committees"]
    for r in api.fetch_all(s["code"], use_cache=False):
        con.execute("INSERT OR REPLACE INTO committees VALUES(?,?,?,?)",
                    (pick(r, "committees", "committee_id"), pick(r, "committees", "name"),
                     pick(r, "committees", "kind"),
                     json.dumps({k: r.get(v) for k, v in s["fields"].items()}, ensure_ascii=False)))
    s = SERVICES["committee_members"]
    first = con.execute("SELECT COUNT(*) FROM committee_roles").fetchone()[0] == 0
    current = set()
    n = 0
    for r in api.fetch_all(s["code"], use_cache=False):
        row = {k: pick(r, "committee_members", k) for k in s["fields"]}
        key = (row["committee"], row["member_id"], row["role"])
        current.add(key)
        exists = con.execute(
            "SELECT 1 FROM committee_roles WHERE committee=? AND member_id=? AND role=? AND end_date IS NULL", key).fetchone()
        if not exists:
            con.execute("INSERT INTO committee_roles VALUES(?,?,?,?,?,?,?,?,?)",
                        (row["committee_id"], row["committee"], row["member_id"], row["name"], row["role"],
                         row["party"], None if first else TODAY, None,
                         f"{s['code']} 명단 {TODAY}" + ("(최초 수집: 시작일 미상)" if first else "(변동 감지일)")))
        n += 1
    for r in con.execute("SELECT rowid, committee, member_id, role FROM committee_roles WHERE end_date IS NULL").fetchall():
        if (r["committee"], r["member_id"], r["role"]) not in current:
            con.execute("UPDATE committee_roles SET end_date=? WHERE rowid=?", (TODAY, r["rowid"]))
    log(f"위원회 위원 {n}명(위원회 중복 포함)")
    return n


def load_bills(con, use_cache=True) -> int:
    s = SERVICES["bills"]
    idx = name_index(con)
    n = 0
    for r in api.fetch_all(s["code"], s["params"], use_cache=use_cache):
        bid = pick(r, "bills", "bill_id")
        if not bid:
            continue
        b = {k: pick(r, "bills", k) for k in s["fields"]}
        for k in ("propose_dt", "cmt_present_dt", "cmt_proc_dt", "law_submit_dt",
                  "law_proc_dt", "plenary_dt"):
            b[k] = norm_date(b[k])
        b["stage"] = compute_stage(b)
        con.execute(
            """INSERT INTO bills(bill_id,bill_no,bill_name,proposer_kind,proposer,propose_dt,
                 committee,committee_id,cmt_present_dt,cmt_proc_dt,cmt_result,law_submit_dt,
                 law_proc_dt,law_result,plenary_dt,proc_result,stage,detail_link,raw_json,updated_at)
               VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
               ON CONFLICT(bill_id) DO UPDATE SET bill_name=excluded.bill_name,
                 committee=excluded.committee,committee_id=excluded.committee_id,
                 cmt_present_dt=excluded.cmt_present_dt,cmt_proc_dt=excluded.cmt_proc_dt,
                 cmt_result=excluded.cmt_result,law_submit_dt=excluded.law_submit_dt,
                 law_proc_dt=excluded.law_proc_dt,law_result=excluded.law_result,
                 plenary_dt=excluded.plenary_dt,proc_result=excluded.proc_result,
                 stage=excluded.stage,raw_json=excluded.raw_json,updated_at=excluded.updated_at""",
            (bid, b["bill_no"], b["bill_name"], "의원", b["proposer"], b["propose_dt"],
             b["committee"], b["committee_id"], b["cmt_present_dt"], b["cmt_proc_dt"],
             b["cmt_result"], b["law_submit_dt"], b["law_proc_dt"], b["law_result"],
             b["plenary_dt"], b["proc_result"], b["stage"], b["detail_link"],
             json.dumps(r, ensure_ascii=False), TODAY),
        )
        save_sponsors(con, bid, b, idx)
        n += 1
        if n % 2000 == 0:
            con.commit()
            log(f"법안 {n}건 저장")
    log(f"법안 {n}건 저장 완료")
    return n


# ---------------------------------------------------------------- 표결
def load_bill_votes(con, use_cache=True) -> list[str]:
    s = SERVICES["bill_votes"]
    ids = []
    for r in api.fetch_all(s["code"], s["params"], use_cache=use_cache):
        bid = pick(r, "bill_votes", "bill_id")
        if not bid:
            continue
        ids.append(bid)

        def num(f):
            v = pick(r, "bill_votes", f)
            try:
                return int(v)
            except (TypeError, ValueError):
                return None
        con.execute(
            "INSERT OR REPLACE INTO votes VALUES(?,?,?,?,?,?,?,?,?,?,?)",
            (bid, pick(r, "bill_votes", "bill_no"), pick(r, "bill_votes", "bill_name"),
             norm_date(pick(r, "bill_votes", "vote_date")), num("member_tcnt"),
             num("vote_tcnt"), num("yes"), num("no"), num("abstain"),
             pick(r, "bill_votes", "result"), json.dumps(r, ensure_ascii=False)),
        )
    log(f"의안별 표결 {len(ids)}건")
    return ids


def load_member_votes(con, bill_ids, use_cache=True, only_new=True) -> int:
    s = SERVICES["member_votes"]
    done = {r[0] for r in con.execute("SELECT DISTINCT bill_id FROM member_votes")}
    n = 0
    for i, bid in enumerate(bill_ids, 1):
        if only_new and bid in done:
            continue
        for r in api.fetch_all(s["code"], {**s["params"], "BILL_ID": bid}, use_cache=use_cache, size=300):
            con.execute(
                "INSERT OR REPLACE INTO member_votes VALUES(?,?,?,?,?,?)",
                (bid, pick(r, "member_votes", "member_id"), pick(r, "member_votes", "name"),
                 pick(r, "member_votes", "party"), pick(r, "member_votes", "vote", "불참"),
                 norm_date(pick(r, "member_votes", "vote_date"))),
            )
            n += 1
        if i % 50 == 0:
            con.commit()
            log(f"의원별 표결 {i}/{len(bill_ids)} 의안 처리")
    log(f"의원별 표결 {n}행 저장")
    return n


# ---------------------------------------------------------------- 당적 이력 재구성
def rebuild_party_history_from_votes(con) -> int:
    """의원별 표결 기록의 '표결 당시 정당' 값으로 당적 변경을 찾는다.

    표결 기록으로는 정확한 변경일을 알 수 없어서, 변경 전 마지막 표결일 다음날을 시작일로 둔다.
    source 에 '표결기록 추정'이라고 남기고, data/party_changes.csv 에 확인된 날짜가 있으면 그게 우선이다.
    """
    changes = 0
    members = [r[0] for r in con.execute(
        "SELECT DISTINCT member_id FROM member_votes WHERE member_id IS NOT NULL")]
    for mid in members:
        seq = con.execute(
            """SELECT vote_date, party FROM member_votes
               WHERE member_id=? AND party IS NOT NULL AND vote_date IS NOT NULL
               ORDER BY vote_date""", (mid,)).fetchall()
        if not seq:
            continue
        runs = []  # (party, first_date, last_date)
        for d, p in seq:
            if runs and runs[-1][0] == p:
                runs[-1][2] = d
            else:
                runs.append([p, d, d])
        if len(runs) < 2:
            continue
        manual = con.execute(
            "SELECT 1 FROM party_affiliations WHERE member_id=? AND source LIKE '수동%'", (mid,)).fetchone()
        if manual:
            continue
        term_start = con.execute(
            "SELECT MIN(start_date) FROM member_terms WHERE member_id=?", (mid,)).fetchone()[0] or TERM_START
        con.execute("DELETE FROM party_affiliations WHERE member_id=?", (mid,))
        for i, (p, first, last) in enumerate(runs):
            start = term_start if i == 0 else (
                date.fromisoformat(runs[i - 1][2]) + timedelta(days=1)).isoformat()
            end = None if i == len(runs) - 1 else (
                date.fromisoformat(last) + timedelta(days=1)).isoformat()
            con.execute("INSERT OR REPLACE INTO party_affiliations VALUES(?,?,?,?,?)",
                        (mid, p, start, end,
                         f"표결기록 추정(변경 전후 표결일 {last if end else first})"))
        changes += len(runs) - 1
    log(f"표결기록으로 추정한 당적 변경 {changes}건")
    return changes


# ---------------------------------------------------------------- 수동 보정
def apply_manual(con) -> None:
    """data/member_terms.csv, data/party_changes.csv, data/vetoes.csv 를 반영한다.
    출처(source) 칸이 비어 있는 줄은 넣지 않는다."""
    p = DATA / "member_terms.csv"
    if p.exists():
        for r in csv.DictReader(p.open(encoding="utf-8")):
            if not r.get("source") or not r.get("member_id"):
                continue
            con.execute("DELETE FROM member_terms WHERE member_id=? AND source NOT LIKE '수동%'",
                        (r["member_id"],))
            con.execute("INSERT OR REPLACE INTO member_terms VALUES(?,?,?,?,?,?)",
                        (r["member_id"], r["start_date"], r.get("start_reason"),
                         r.get("end_date") or None, r.get("end_reason") or None,
                         "수동: " + r["source"]))
    p = DATA / "party_changes.csv"
    if p.exists():
        by_member: dict[str, list] = {}
        for r in csv.DictReader(p.open(encoding="utf-8")):
            if r.get("source") and r.get("member_id"):
                by_member.setdefault(r["member_id"], []).append(r)
        for mid, rs in by_member.items():
            con.execute("DELETE FROM party_affiliations WHERE member_id=?", (mid,))
            for r in rs:
                con.execute("INSERT OR REPLACE INTO party_affiliations VALUES(?,?,?,?,?)",
                            (mid, r["party"], r["start_date"], r.get("end_date") or None,
                             "수동: " + r["source"]))
    p = DATA / "vetoes.csv"
    if p.exists():
        con.execute("DELETE FROM vetoes")
        for r in csv.DictReader(p.open(encoding="utf-8")):
            if r.get("source") and r.get("bill_name") and r.get("request_dt"):
                con.execute("INSERT INTO vetoes VALUES(?,?,?,?,?,?)",
                            (r.get("bill_id") or None, r["bill_name"], r["request_dt"],
                             r.get("revote_dt") or None, r.get("revote_result") or None, r["source"]))


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--full", action="store_true", help="모든 의원별 표결을 다시 받는다")
    ap.add_argument("--no-votes", action="store_true")
    ap.add_argument("--fresh", action="store_true", help="캐시를 쓰지 않는다")
    a = ap.parse_args(argv)
    use_cache = not a.fresh
    con = connect()
    try:
        load_members(con, use_cache=False)  # 의원 명단은 매번 새로 받아 변동을 감지
        con.commit()
        load_committees(con)
        con.commit()
        load_bills(con, use_cache=use_cache)
        con.commit()
        load_other_bills(con, use_cache=use_cache)
        con.commit()
        if not a.no_votes:
            ids = load_bill_votes(con, use_cache=use_cache)  # 마지막 페이지는 fetch_all 이 항상 새로 받음
            con.commit()
            load_member_votes(con, ids, use_cache=use_cache, only_new=not a.full)
            con.commit()
            rebuild_party_history_from_votes(con)
        apply_manual(con)
        con.execute("INSERT OR REPLACE INTO meta VALUES('last_update', ?)", (datetime.now().isoformat(timespec="seconds"),))
        con.commit()
    except api.AssemblyAPIError as e:
        log(f"중단: {e}")
        return 1
    finally:
        con.close()
    log("완료")
    return 0


if __name__ == "__main__":
    sys.exit(main())
