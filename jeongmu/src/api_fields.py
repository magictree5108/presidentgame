"""열린국회정보 API 서비스 코드와 출력 필드 대응표.

status:
  "확인됨"   - check_apis.py 실행 결과(docs/api_samples/)로 필드를 직접 확인함
  "미검증"   - 공개된 제3자 프로젝트 문서에서 찾은 코드. 포털/실호출로 확인 전
check_apis.py 를 키와 함께 실행하면 아래 expected 필드가 실제 응답에 있는지 검사해서
docs/apis.md 의 상태 표를 갱신한다. 필드명이 다르면 이 파일의 fields만 고치면 된다.
"""

SERVICES = {
    "members": {
        "code": "nwvrqwxyaytdsfvhu",
        "name": "국회의원 인적사항",
        "params": {},
        "status": "확인됨(2026-10-28 실호출)",
        "fields": {
            "member_id": "MONA_CD", "name": "HG_NM", "name_hanja": "HJ_NM",
            "name_eng": "ENG_NM", "party": "POLY_NM", "district": "ORIG_NM",
            "elect_type": "ELECT_GBN_NM", "reelection": "REELE_GBN_NM",
            "units": "UNITS", "committees": "CMITS", "homepage": "HOMEPAGE",
        },
    },
    "bills": {
        "code": "nzmimeepazxkubdpn",
        "name": "국회의원 발의법률안",
        "params": {"AGE": "22"},
        "status": "확인됨(2026-10-28 실호출)",
        "fields": {
            "bill_id": "BILL_ID", "bill_no": "BILL_NO", "bill_name": "BILL_NAME",
            "committee": "COMMITTEE", "committee_id": "COMMITTEE_ID",
            "propose_dt": "PROPOSE_DT", "proc_result": "PROC_RESULT",
            "proposer": "PROPOSER", "lead": "RST_PROPOSER", "co": "PUBL_PROPOSER",
            "lead_id": "RST_MONA_CD", "co_ids": "PUBL_MONA_CD",
            "cmt_present_dt": "CMT_PRESENT_DT", "cmt_proc_dt": "CMT_PROC_DT",
            "cmt_result": "CMT_PROC_RESULT_CD", "law_submit_dt": "LAW_SUBMIT_DT",
            "law_proc_dt": "LAW_PROC_DT", "law_result": "LAW_PROC_RESULT_CD",
            "plenary_dt": "PROC_DT", "detail_link": "DETAIL_LINK",
        },
    },
    "bill_votes": {
        "code": "ncocpgfiaoituanbr",
        "name": "의안별 표결현황",
        "params": {"AGE": "22"},
        "status": "확인됨(2026-10-28 실호출)",
        "fields": {
            "bill_id": "BILL_ID", "bill_no": "BILL_NO", "bill_name": "BILL_NAME",
            "vote_date": "PROC_DT", "member_tcnt": "MEMBER_TCNT",
            "vote_tcnt": "VOTE_TCNT", "yes": "YES_TCNT", "no": "NO_TCNT",
            "abstain": "BLANK_TCNT", "result": "PROC_RESULT_CD",
        },
    },
    "member_votes": {
        "code": "nojepdqqaweusdfbi",
        "name": "국회의원 본회의 표결정보",
        "params": {"AGE": "22"},   # BILL_ID 를 추가로 넣어 의안별로 부른다
        "status": "확인됨(2026-10-28 실호출)",
        "fields": {
            "bill_id": "BILL_ID", "member_id": "MONA_CD", "name": "HG_NM",
            "party": "POLY_NM", "vote": "RESULT_VOTE_MOD", "vote_date": "VOTE_DATE",
        },
    },
    "all_bills": {
        "code": "TVBPMBILL11",
        "name": "의안검색(위원장 대안·정부안 포함)",
        "params": {"AGE": "22"},
        "status": "확인됨(2026-10-28 실호출)",
        "fields": {
            "bill_id": "BILL_ID", "bill_no": "BILL_NO", "bill_name": "BILL_NAME",
            "proposer": "PROPOSER", "proposer_kind": "PROPOSER_KIND", "lead": "RST_PROPOSER", "lead_id": "RST_MONA_CD",
            "committee": "CURR_COMMITTEE", "committee_id": "CURR_COMMITTEE_ID", "propose_dt": "PROPOSE_DT",
            "proc_result": "PROC_RESULT_CD", "cmt_present_dt": "CMT_PRESENT_DT", "cmt_proc_dt": "CMT_PROC_DT",
            "cmt_result": "CMT_PROC_RESULT_CD", "law_submit_dt": "LAW_SUBMIT_DT", "law_proc_dt": "LAW_PROC_DT",
            "law_result": "LAW_PROC_RESULT_CD", "plenary_dt": "PROC_DT", "detail_link": "LINK_URL",
        },
    },
    "api_list": {
        "code": "OPENSRVAPI",
        "name": "열린국회정보 OpenAPI 목록",
        "params": {},
        "status": "확인됨(2026-10-28 실호출)",
        "fields": {},
    },
}

SERVICES["committee_members"] = {
    "code": "nktulghcadyhmiqxi",
    "name": "위원회 위원 명단",
    "params": {},
    "status": "확인됨(2026-10-28 실호출, 코드는 포털 명세서에서 확인)",
    # 연락처·보좌진 칸은 받아도 저장하지 않는다(실존 인물 보호)
    "fields": {"committee_id": "DEPT_CD", "committee": "DEPT_NM", "role": "JOB_RES_NM",
               "name": "HG_NM", "party": "POLY_NM", "member_id": "MONA_CD"},
}
SERVICES["committees"] = {
    "code": "nxrvzonlafugpqjuh",
    "name": "위원회 현황 정보",
    "params": {},
    "status": "확인됨(2026-10-28 실호출, 코드는 포털 명세서에서 확인)",
    "fields": {"committee_id": "HR_DEPT_CD", "name": "COMMITTEE_NAME", "kind": "CMT_DIV_NM",
               "chair": "HG_NM", "secretaries": "HG_NM_LIST", "limit": "LIMIT_CNT", "current": "CURR_CNT"},
}

SERVICES["member_history"] = {
    "code": "nexgtxtmaamffofof", "name": "국회의원 의원이력(현직)", "params": {},
    "status": "확인됨(2026-10-28 실호출, 코드는 포털 명세서)",
    "fields": {"member_id": "MONA_CD", "name": "HG_NM", "period": "FRTO_DATE", "profile": "PROFILE_SJ"},
}
SERVICES["former_member_history"] = {
    "code": "nfzegpkvaclgtscxt", "name": "역대 국회의원 의원이력(전직)", "params": {"PROFILE_UNIT_CD": "100022"},
    "status": "확인됨(2026-10-28 실호출, 22대 전직 22명)",
    "fields": {"member_id": "MONA_CD", "name": "HG_NM", "period": "FRTO_DATE", "profile": "PROFILE_SJ"},
}
SERVICES["former_members"] = {
    "code": "npffdutiapkzbfyvr", "name": "역대 국회의원 인적사항", "params": {"UNIT_CD": "100022"},
    "status": "확인됨(2026-10-28 실호출)",
    "fields": {"member_id": "MONA_CD", "name": "HG_NM", "party": "POLY_NM", "district": "ORIG_NM"},
}
SERVICES["seat_status"] = {
    "code": "nepjpxkkabqiqpbvk", "name": "정당 및 교섭단체 의석수 현황(공식)", "params": {},
    "status": "확인됨(2026-10-28 실호출)",
    "fields": {"party": "POLY_NM", "district": "N1", "proportional": "N2", "total": "N3", "pct": "N4"},
}

# 아직 서비스 코드를 찾지 못해 check_apis.py 가 OPENSRVAPI 목록에서 이름으로 찾아야 하는 것
TO_DISCOVER = {
    "bill_review": ["의안 심사정보", "심사정보"],
    "minutes": ["회의록"],
    "former_members": ["역대 국회의원 인적사항", "역대국회의원"],
}


def pick(row: dict, service: str, field: str, default=None):
    col = SERVICES[service]["fields"].get(field)
    if not col:
        return default
    v = row.get(col)
    if v in (None, ""):
        return default
    return str(v).strip()
