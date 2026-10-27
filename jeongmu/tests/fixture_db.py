"""테스트 전용 가상 DB. 이름·정당·법안은 모두 가짜이며 실제 데이터로 쓰지 않는다."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from db import connect


def make():
    con = connect(":memory:")
    members = [("M1", "가가가", "갑당"), ("M2", "나나나", "갑당"), ("M3", "다다다", "갑당"),
               ("M4", "라라라", "을당"), ("M5", "마마마", "을당"), ("M6", "바바바", "병당")]
    for mid, nm, p in members:
        con.execute("INSERT INTO members(member_id,name,current_party) VALUES(?,?,?)", (mid, nm, p))
        con.execute("INSERT INTO member_terms VALUES(?,?,?,?,?,?)", (mid, "2024-05-30", "총선", None, None, "test"))
        con.execute("INSERT INTO party_affiliations VALUES(?,?,?,?,?)", (mid, p, "2024-05-30", None, "test"))
    # M3 은 2025-03-01 에 병당으로 옮김
    con.execute("UPDATE party_affiliations SET end_date='2025-03-01' WHERE member_id='M3'")
    con.execute("INSERT INTO party_affiliations VALUES('M3','병당','2025-03-01',NULL,'test')")
    # M5 는 2025-06-01 의원직 상실, M7 이 보궐로 들어옴
    con.execute("UPDATE member_terms SET end_date='2025-06-01', end_reason='의원직 상실' WHERE member_id='M5'")
    con.execute("UPDATE party_affiliations SET end_date='2025-06-01' WHERE member_id='M5'")
    con.execute("INSERT INTO members(member_id,name,current_party) VALUES('M7','사사사','갑당')")
    con.execute("INSERT INTO member_terms VALUES('M7','2025-10-01','보궐',NULL,NULL,'test')")
    con.execute("INSERT INTO party_affiliations VALUES('M7','갑당','2025-10-01',NULL,'test')")

    bills = [
        ("B1", "가법 일부개정", "가위원회", "2024-07-01", "2024-09-01", "원안가결"),
        ("B2", "나법 일부개정", "가위원회", "2024-07-10", None, None),
        ("B3", "다법 일부개정", "나위원회", "2024-08-01", "2024-08-20", "대안반영폐기"),
        ("B4", "라법 제정", "가위원회", "2024-08-05", "2024-12-05", "수정가결"),
    ]
    for bid, nm, cmt, pd, pl, res in bills:
        con.execute("INSERT INTO bills(bill_id,bill_name,committee,propose_dt,plenary_dt,proc_result) VALUES(?,?,?,?,?,?)",
                    (bid, nm, cmt, pd, pl, res))
    con.execute("UPDATE bills SET cmt_proc_dt='2024-09-01', law_submit_dt='2024-09-02' WHERE bill_id='B2'")
    for bid, mid, role in [("B1", "M1", "lead"), ("B1", "M2", "co"), ("B1", "M4", "co"),
                           ("B2", "M1", "lead"), ("B2", "M4", "co"), ("B4", "M2", "lead"), ("B4", "M1", "co")]:
        con.execute("INSERT INTO bill_sponsors VALUES(?,?,?,?)", (bid, mid, mid, role))
    votes = {  # B1: 갑당 다수 찬성, M3 반대(이탈), 을당 반대
        "B1": [("M1", "갑당", "찬성"), ("M2", "갑당", "찬성"), ("M3", "갑당", "반대"),
               ("M4", "을당", "반대"), ("M5", "을당", "반대"), ("M6", "병당", "불참")],
        "B4": [("M1", "갑당", "찬성"), ("M2", "갑당", "불참"), ("M3", "갑당", "찬성"),
               ("M4", "을당", "찬성"), ("M5", "을당", "반대"), ("M6", "병당", "찬성")],
    }
    dates = {"B1": "2024-09-01", "B4": "2024-12-05"}
    for bid, vs in votes.items():
        for mid, p, v in vs:
            con.execute("INSERT INTO member_votes VALUES(?,?,?,?,?,?)", (bid, mid, mid, p, v, dates[bid]))
    con.commit()
    return con
