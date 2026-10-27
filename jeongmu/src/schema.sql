-- 정무상황실 국회 DB (data/assembly.sqlite)
-- 날짜는 모두 'YYYY-MM-DD' 문자열. source 칸에는 어떤 API/문서에서 왔는지 적는다.

CREATE TABLE IF NOT EXISTS members (
    member_id     TEXT PRIMARY KEY,   -- 국회 의원코드(MONA_CD)
    name          TEXT NOT NULL,
    name_hanja    TEXT,
    name_eng      TEXT,
    district      TEXT,               -- 선거구(비례대표면 '비례대표')
    elect_type    TEXT,               -- 지역구/비례대표
    reelection    TEXT,               -- 초선/재선...
    units         TEXT,               -- 당선 대수
    current_party TEXT,
    committees    TEXT,               -- API가 주는 소속위원회 문자열 그대로
    homepage      TEXT,
    raw_json      TEXT,
    updated_at    TEXT
);

-- 의원직 보유 기간. 보궐 당선, 의원직 상실, 사퇴, 사망 등을 날짜와 함께 남긴다.
CREATE TABLE IF NOT EXISTS member_terms (
    member_id    TEXT NOT NULL,
    start_date   TEXT NOT NULL,
    start_reason TEXT,               -- 총선 당선 / 보궐선거 당선 / 비례 승계
    end_date     TEXT,               -- NULL이면 현직
    end_reason   TEXT,               -- 의원직 상실 / 사퇴 / 사망 / 임기만료
    source       TEXT,
    PRIMARY KEY (member_id, start_date)
);

-- 당적 이력. end_date NULL이면 현재 소속.
CREATE TABLE IF NOT EXISTS party_affiliations (
    member_id  TEXT NOT NULL,
    party      TEXT NOT NULL,
    start_date TEXT NOT NULL,
    end_date   TEXT,
    source     TEXT,
    PRIMARY KEY (member_id, start_date)
);

CREATE TABLE IF NOT EXISTS committees (
    committee_id TEXT PRIMARY KEY,
    name         TEXT NOT NULL,
    kind         TEXT,               -- 상임위원회/특별위원회
    raw_json     TEXT
);

CREATE TABLE IF NOT EXISTS committee_roles (
    committee_id TEXT,
    committee    TEXT NOT NULL,
    member_id    TEXT,
    name         TEXT,
    role         TEXT NOT NULL,      -- 위원장/간사/위원
    party        TEXT,
    start_date   TEXT,
    end_date     TEXT,
    source       TEXT
);
CREATE INDEX IF NOT EXISTS idx_cr_cmt ON committee_roles(committee);

CREATE TABLE IF NOT EXISTS bills (
    bill_id        TEXT PRIMARY KEY,  -- BILL_ID
    bill_no        TEXT,
    bill_name      TEXT NOT NULL,
    proposer_kind  TEXT,              -- 의원/위원장/정부
    proposer       TEXT,              -- "홍길동의원 등 10인"
    propose_dt     TEXT,
    committee      TEXT,
    committee_id   TEXT,
    cmt_present_dt TEXT,              -- 소관위 회부일
    cmt_proc_dt    TEXT,              -- 소관위 처리일
    cmt_result     TEXT,
    law_submit_dt  TEXT,              -- 법사위 회부일
    law_proc_dt    TEXT,              -- 법사위 처리일
    law_result     TEXT,
    plenary_dt     TEXT,              -- 본회의 의결일
    proc_result    TEXT,              -- 원안가결/수정가결/대안반영폐기/부결/철회/임기만료폐기 ...
    stage          TEXT,              -- 계산된 진행 단계(접수/소관위/법사위/본회의/정부이송/공포/폐기)
    detail_link    TEXT,
    raw_json       TEXT,
    updated_at     TEXT
);
CREATE INDEX IF NOT EXISTS idx_bills_cmt ON bills(committee);
CREATE INDEX IF NOT EXISTS idx_bills_dt ON bills(propose_dt);

CREATE TABLE IF NOT EXISTS bill_sponsors (
    bill_id   TEXT NOT NULL,
    member_id TEXT,                   -- 이름만 있고 코드가 없으면 NULL (이름으로 매칭 시도)
    name      TEXT NOT NULL,
    role      TEXT NOT NULL,          -- lead(대표발의)/co(공동발의)
    PRIMARY KEY (bill_id, name, role)
);
CREATE INDEX IF NOT EXISTS idx_bs_member ON bill_sponsors(member_id);

-- 본회의 표결(의안별 집계)
CREATE TABLE IF NOT EXISTS votes (
    bill_id   TEXT PRIMARY KEY,
    bill_no   TEXT,
    bill_name TEXT,
    vote_date TEXT,
    member_tcnt INTEGER,              -- 재적
    vote_tcnt INTEGER,                -- 투표 참여
    yes       INTEGER,
    no        INTEGER,
    abstain   INTEGER,
    result    TEXT,
    raw_json  TEXT
);

-- 의원별 표결
CREATE TABLE IF NOT EXISTS member_votes (
    bill_id   TEXT NOT NULL,
    member_id TEXT,
    name      TEXT NOT NULL,
    party     TEXT,                   -- 표결 당시 소속(API 제공값)
    vote      TEXT NOT NULL,          -- 찬성/반대/기권/불참
    vote_date TEXT,
    PRIMARY KEY (bill_id, name, member_id)
);
CREATE INDEX IF NOT EXISTS idx_mv_member ON member_votes(member_id);

-- 정부 재의요구(거부권) 이력: 공식 API가 확인되기 전까지 수동 입력(data/vetoes.csv)
CREATE TABLE IF NOT EXISTS vetoes (
    bill_id     TEXT,
    bill_name   TEXT NOT NULL,
    request_dt  TEXT NOT NULL,
    revote_dt   TEXT,
    revote_result TEXT,
    source      TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS meta (
    key   TEXT PRIMARY KEY,
    value TEXT
);
