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
import re
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
        # 당적 스냅샷: 바뀐 날만 남긴다. 당적 이력(party_affiliations)은 build_terms_and_parties 가 다시 만든다.
        last = con.execute("SELECT party FROM party_snapshots WHERE member_id=? ORDER BY seen_date DESC LIMIT 1",
                           (mid,)).fetchone()
        if party and (last is None or last[0] != party):
            con.execute("INSERT OR REPLACE INTO party_snapshots VALUES(?,?,?)", (mid, TODAY, party))
            if last is not None:
                log(f"당적 변경 감지: {pick(r, 'members', 'name')} {last[0]} → {party} (실제 변경일은 party_changes.csv 로 보정)")
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


# ---------------------------------------------------------------- 의원직 기간·당적 이력
def _frto(v):
    """'2024.05.30 ~ 2026.04.30' → ('2024-05-30', '2026-05-01'). 종료일은 '그 다음날'(이 날부터 아님)로 저장."""
    a, _, b = (v or "").partition("~")
    start = norm_date(a.strip())
    end = norm_date(b.strip())
    if end:
        end = (date.fromisoformat(end) + timedelta(days=1)).isoformat()
    return start, end


def build_terms_and_parties(con) -> None:
    """의원직 기간: 열린국회정보 의원이력(현직)·역대 의원이력(전직) 공식 날짜.
    당적 이력: data/party_changes.csv(출처 필수)가 있으면 그것, 없으면 일일 당적 스냅샷.
    주의: 본회의 표결정보 API의 POLY_NM 은 '표결 당시'가 아니라 '현재(마지막) 소속'이라 당적 이력에 쓰지 않는다."""
    # 전직 의원 인적사항(공개 필드만)
    s = SERVICES["former_members"]
    for r in api.fetch_all(s["code"], s["params"], use_cache=False):
        mid = r.get("MONA_CD")
        if not mid or con.execute("SELECT 1 FROM members WHERE member_id=?", (mid,)).fetchone():
            continue
        con.execute(
            """INSERT INTO members(member_id,name,name_hanja,name_eng,district,elect_type,reelection,units,
                 current_party,raw_json,updated_at) VALUES(?,?,?,?,?,?,?,?,?,?,?)""",
            (mid, r.get("HG_NM"), r.get("HJ_NM"), r.get("ENG_NM"), r.get("ORIG_NM"), r.get("ELECT_GBN_NM"),
             r.get("REELE_GBN_NM"), r.get("UNITS"), r.get("POLY_NM"), json.dumps(public(r), ensure_ascii=False), TODAY))
    terms = []
    for key in ("member_history", "former_member_history"):
        s = SERVICES[key]
        for r in api.fetch_all(s["code"], s["params"], use_cache=False):
            if str(r.get("UNIT_CD") or r.get("PROFILE_UNIT_CD") or "") not in ("100022", "") \
                    or not str(r.get("PROFILE_SJ", "")).startswith("제22대"):
                continue
            start, end = _frto(r.get("FRTO_DATE"))
            if start:
                terms.append((r["MONA_CD"], start, end, r.get("PROFILE_SJ"), s["code"]))
    if not terms:
        log("의원이력 응답이 비어 기간 재구성을 건너뜀")
        return
    con.execute("DELETE FROM member_terms WHERE source NOT LIKE '수동%'")
    for mid, start, end, prof, code in terms:
        reason = "총선 당선" if start == TERM_START else "보궐선거 당선·비례 승계 등(의원이력 시작일)"
        con.execute("INSERT OR REPLACE INTO member_terms VALUES(?,?,?,?,?,?)",
                    (mid, start, reason, end, "퇴직(사유는 의원이력에 없음)" if end else None,
                     f"열린국회정보 {code}: {prof}"))
    # 당적 이력
    con.execute("DELETE FROM party_affiliations WHERE source NOT LIKE '수동%'")
    manual = {r[0] for r in con.execute("SELECT DISTINCT member_id FROM party_affiliations")}
    for mid, start, end, prof, code in terms:
        if mid in manual:
            continue
        snaps = con.execute("SELECT seen_date, party FROM party_snapshots WHERE member_id=? ORDER BY seen_date",
                            (mid,)).fetchall()
        if not snaps:
            p = con.execute("SELECT current_party FROM members WHERE member_id=?", (mid,)).fetchone()
            snaps = [(start, p[0] if p else None)]
        for i, (seen, party) in enumerate(snaps):
            seg_start = start if i == 0 else seen
            seg_end = snaps[i + 1][0] if i + 1 < len(snaps) else end
            src = ("당적 변경 기록 없음 → 현재(마지막) 소속을 임기 전체에 적용" if i == 0
                   else f"일일 명단에서 {seen} 변경 감지(실제 변경일은 보정 필요)")
            con.execute("INSERT OR REPLACE INTO party_affiliations VALUES(?,?,?,?,?)",
                        (mid, party, seg_start, seg_end, src))
    log(f"의원직 기간 {len(terms)}건, 수동 당적 이력 {len(manual)}명 반영")


# ---------------------------------------------------------------- 재의요구(거부권)
REVOTE = re.compile(r"^\s*\d+\.\s*(.+?)\s*재의의 건\((대통령|정부) 제출\)")


def load_revotes(con) -> int:
    """본회의 회의록 안건 목록에서 '… 재의의 건'을 찾아 재의요구 이력으로 남긴다.
    법안 API는 거부된 법안도 처음 가결 결과(원안·수정가결)로 남겨 두므로 이 표로 따로 표시한다."""
    s = SERVICES["plenary_minutes"]
    found = {}
    for y in range(int(TERM_START[:4]), date.today().year + 1):
        for r in api.fetch_all(s["code"], {**s["params"], "CONF_DATE": str(y)}, use_cache=False):
            m = REVOTE.match(r.get("SUB_NAME") or "")
            if m:
                found[(r["CONF_DATE"], m.group(1))] = (m.group(2), r.get("PDF_LINK_URL"), r.get("TITLE"))
    con.execute("DELETE FROM vetoes WHERE source LIKE '본회의 회의록%'")
    for (d, name), (who, pdf, title) in sorted(found.items()):
        b = con.execute(
            """SELECT bill_id FROM bills WHERE (bill_name = ? OR bill_name LIKE ?) AND proc_result LIKE '%가결%'
               AND plenary_dt < ? ORDER BY plenary_dt DESC LIMIT 1""", (name, name + "(%", d)).fetchone()
        con.execute("INSERT INTO vetoes VALUES(?,?,?,?,?,?,?)",
                    (b[0] if b else None, name, None, d, None, "대통령" if who == "대통령" else "정부(권한대행)",
                     f"본회의 회의록 안건 '{title}' {pdf or ''}"))
    log(f"재의 표결 안건 {len(found)}건(회의록)")
    return len(found)


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
        con.execute("DELETE FROM vetoes WHERE source LIKE '수동%'")
        for r in csv.DictReader(p.open(encoding="utf-8")):
            if r.get("source") and r.get("bill_name"):
                con.execute("INSERT INTO vetoes VALUES(?,?,?,?,?,?,?)",
                            (r.get("bill_id") or None, r["bill_name"], r.get("request_dt") or None,
                             r.get("revote_dt") or None, r.get("revote_result") or None,
                             r.get("requester") or None, "수동: " + r["source"]))


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
        load_revotes(con)
        apply_manual(con)  # 수동 당적·기간을 먼저 넣고
        build_terms_and_parties(con)  # 나머지를 공식 의원이력으로 채운다
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
