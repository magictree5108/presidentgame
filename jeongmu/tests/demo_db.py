"""화면 확인용 가상 DB 생성기. 이름·정당·지역·법안·표결이 모두 가짜다(실제 데이터 아님).

사용: JEONGMU_DB_DIR=/tmp/demo python tests/demo_db.py && JEONGMU_DB_DIR=/tmp/demo python run.py
"""
import os
import random
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

import config
from db import connect
from metrics import compute, save

assert os.environ.get("JEONGMU_DB_DIR"), "실제 DB를 덮지 않도록 JEONGMU_DB_DIR 를 지정하세요"
rng = random.Random(1)
Path(config.ASSEMBLY_DB).parent.mkdir(parents=True, exist_ok=True)
if Path(config.ASSEMBLY_DB).exists():
    Path(config.ASSEMBLY_DB).unlink()
con = connect(config.ASSEMBLY_DB)
parties = [("가상A당", 165), ("가상B당", 105), ("가상C당", 12), ("가상D당", 8), ("무소속", 8)]
regions = ["가도", "나도", "다시", "라시", "마도"]
cmts = ["가상제1위원회", "가상제2위원회", "가상제3위원회", "가상법사위원회"]
mid = 0
for p, n in parties:
    for _ in range(n):
        mid += 1
        m = f"D{mid:03d}"
        cm = rng.choice(cmts[:3]) + ("," + cmts[3] if rng.random() < 0.06 else "")
        con.execute("INSERT INTO members(member_id,name,current_party,district,committees,updated_at) VALUES(?,?,?,?,?,date('now'))",
                    (m, f"가상의원{mid:03d}", p, f"{rng.choice(regions)} 가상{rng.randint(1,9)}구", cm))
        con.execute("INSERT INTO member_terms VALUES(?,?,?,?,?,?)", (m, "2024-05-30", "가상", None, None, "가상"))
        con.execute("INSERT INTO party_affiliations VALUES(?,?,?,?,?)", (m, p, "2024-05-30", None, "가상"))
ids = [f"D{i:03d}" for i in range(1, mid + 1)]
party_of = {r[0]: r[1] for r in con.execute("SELECT member_id, current_party FROM members")}
for b in range(1, 401):
    cm = rng.choice(cmts[:3])
    pd = f"2024-{rng.randint(6,12):02d}-{rng.randint(1,28):02d}"
    res = rng.choice([None, None, "원안가결", "수정가결", "대안반영폐기"])
    pl = f"2025-{rng.randint(1,12):02d}-{rng.randint(1,28):02d}" if res else None
    con.execute("INSERT INTO bills(bill_id,bill_name,committee,propose_dt,plenary_dt,proc_result,stage,proposer) VALUES(?,?,?,?,?,?,?,?)",
                (f"DB{b}", f"가상법{b % 40}법 일부개정법률안", cm, pd, pl, res, res or "소관위 심사", "가상"))
    lead = rng.choice(ids)
    same = [i for i in ids if party_of[i] == party_of[lead]]
    co = rng.sample(same, min(9, len(same))) + (rng.sample(ids, 2) if rng.random() < .3 else [])
    con.execute("INSERT OR IGNORE INTO bill_sponsors VALUES(?,?,?,?)", (f"DB{b}", lead, lead, "lead"))
    for c in co:
        con.execute("INSERT OR IGNORE INTO bill_sponsors VALUES(?,?,?,?)", (f"DB{b}", c, c, "co"))
    if res and "가결" in res:
        for i in ids:
            v = rng.choices(["찬성", "반대", "기권", "불참"], [8, 1, .3, .8] if party_of[i] == "가상A당" else [3, 5, .5, 1])[0]
            con.execute("INSERT INTO member_votes VALUES(?,?,?,?,?,?)", (f"DB{b}", i, i, party_of[i], v, pl))
con.execute("INSERT OR REPLACE INTO meta VALUES('last_update','가상 데이터')")
con.commit()
save(compute(con, "2026-10-27"))
print("가상 DB 생성:", config.ASSEMBLY_DB)
