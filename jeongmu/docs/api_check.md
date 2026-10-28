# 열린국회정보 API 실호출 확인 (2026-10-28 01:03)

| 용도 | 서비스 코드 | 결과 | 전체 건수 | 응답에 없는 예상 필드 |
|---|---|---|---|---|
| 국회의원 인적사항 | `nwvrqwxyaytdsfvhu` | 확인됨 | 299 | - |
|  ↳ 실제 필드 | | | | ASSEM_ADDR, BTH_DATE, BTH_GBN_NM, CMITS, CMIT_NM, ELECT_GBN_NM, ENG_NM, E_MAIL, HG_NM, HJ_NM, HOMEPAGE, JOB_RES_NM, MEM_TITLE, MONA_CD, ORIG_NM, POLY_NM, REELE_GBN_NM, SECRETARY, SECRETARY2, SEX_GBN_NM, STAFF, TEL_NO, UNITS |
| 국회의원 발의법률안 | `nzmimeepazxkubdpn` | 확인됨 | 20168 | - |
|  ↳ 실제 필드 | | | | AGE, BILL_ID, BILL_NAME, BILL_NO, CMT_PRESENT_DT, CMT_PROC_DT, CMT_PROC_RESULT_CD, COMMITTEE, COMMITTEE_DT, COMMITTEE_ID, DETAIL_LINK, LAW_PRESENT_DT, LAW_PROC_DT, LAW_PROC_RESULT_CD, LAW_SUBMIT_DT, MEMBER_LIST, PROC_DT, PROC_RESULT, PROPOSER, PROPOSE_DT, PUBL_MONA_CD, PUBL_PROPOSER, RST_MONA_CD, RST_PROPOSER |
| 의안별 표결현황 | `ncocpgfiaoituanbr` | 확인됨 | 1911 | - |
|  ↳ 실제 필드 | | | | AGE, BILL_ID, BILL_KIND_CD, BILL_NAME, BILL_NO, BLANK_TCNT, CURR_COMMITTEE, CURR_COMMITTEE_ID, LINK_URL, MEMBER_TCNT, NO_TCNT, PROC_DT, PROC_RESULT_CD, VOTE_TCNT, YES_TCNT |
| 국회의원 본회의 표결정보 | `nojepdqqaweusdfbi` | 확인됨 | 299 | - |
|  ↳ 실제 필드 | | | | AGE, BILL_ID, BILL_NAME, BILL_NAME_URL, BILL_NO, BILL_URL, CURRENTS_CD, CURR_COMMITTEE, CURR_COMMITTEE_ID, DEPT_CD, DISP_ORDER, HG_NM, HJ_NM, LAW_TITLE, MEMBER_NO, MONA_CD, ORIG_CD, ORIG_NM, POLY_CD, POLY_NM, RESULT_VOTE_MOD, SESSION_CD, VOTE_DATE |
| 의안검색(위원장 대안·정부안 포함) | `TVBPMBILL11` | 확인됨 | 21582 | - |
|  ↳ 실제 필드 | | | | AGE, BILL_ID, BILL_NAME, BILL_NO, CMT_PRESENT_DT, CMT_PROC_DT, CMT_PROC_RESULT_CD, COMMITTEE_DT, COMMITTEE_PROC_DT, CURR_COMMITTEE, CURR_COMMITTEE_ID, LAW_PRESENT_DT, LAW_PROC_DT, LAW_PROC_RESULT_CD, LAW_SUBMIT_DT, LINK_URL, PASS_GUBUN, PROC_DT, PROC_RESULT_CD, PROPOSER, PROPOSER_KIND, PROPOSE_DT, RST_MONA_CD, RST_PROPOSER |
| 열린국회정보 OpenAPI 목록 | `OPENSRVAPI` | 확인됨 | 280 | - |
|  ↳ 실제 필드 | | | | CATE_NM, CCL_NM, DDC_URL, INF_EXP, INF_ID, INF_NM, LOAD_CONT, LOAD_DTTM, LOAD_NM, OPEN_DTTM, ORG_NM, SRC_EXP, SRV_URL |

## OPENSRVAPI 목록에서 찾은 후보

### committee_members (위원회 위원 명단 / 위원명단)
- {"INF_ID": "OCAJQ4001000LI18751", "INF_NM": "위원회 위원 명단", "INF_EXP": "국회상임위원회 및 특별위원회 위원 명단 및 연락처 정보를 제공합니다. ", "CATE_NM": "의정활동별 공개", "OPEN_DTTM": "2019-11-05", "ORG_NM": "국회사무처", "LOAD_DTTM": "2026-10-28", "SRC_EXP": "국회상임위원회 및 특별위원회", "DDC_URL": "https://open.assembly.go.kr/portal/data/openapi/dow

### committees (위원회 현황)
- {"INF_ID": "O2Q4ZT001004PV11014", "INF_NM": "위원회 현황 정보", "INF_EXP": "위원회별 위원장, 간사, 위원정수, 현원, 정당별 위원수 정보를 제공합니다. ", "CATE_NM": "의정활동별 공개", "OPEN_DTTM": "2019-11-07", "ORG_NM": "국회사무처", "LOAD_DTTM": "2026-10-28", "SRC_EXP": "국회상임위원회 및 특별위원회", "DDC_URL": "https://open.assembly.go.kr/portal/data/openapi

### bill_review (의안 심사정보 / 심사정보)
- {"INF_ID": "OOWY4R001216HX11542", "INF_NM": "소위 심사정보(법률안)", "INF_EXP": "소위 심사정보(법률안) 정보를 제공합니다.", "CATE_NM": "주제별 공개>정책", "OPEN_DTTM": "2026-07-07", "ORG_NM": "국회사무처", "LOAD_DTTM": "2026-09-24", "SRC_EXP": "의안정보시스템", "DDC_URL": "https://open.assembly.go.kr/portal/data/openapi/downloadOpenApiSpec.do?
- {"INF_ID": "OOWY4R001216HX11462", "INF_NM": "의안 심사정보(예ㆍ결산 제외)", "INF_EXP": "의안 심사정보(예ㆍ결산 제외) 정보를 제공합니다.", "CATE_NM": "주제별 공개>정책", "OPEN_DTTM": "2023-12-01", "ORG_NM": "국회사무처", "LOAD_DTTM": "2026-10-28", "SRC_EXP": "국회홈페이지", "DDC_URL": "https://open.assembly.go.kr/portal/data/openapi/downloadOpenApiS
- {"INF_ID": "OOWY4R001216HX11468", "INF_NM": "예결산 심사정보", "INF_EXP": "예결산 심사정보를 제공합니다.", "CATE_NM": "주제별 공개>정책", "OPEN_DTTM": "2023-12-01", "ORG_NM": "국회 특별위원회", "LOAD_DTTM": "2026-10-28", "SRC_EXP": "국회홈페이지", "DDC_URL": "https://open.assembly.go.kr/portal/data/openapi/downloadOpenApiSpec.do?infId=OOW
- {"INF_ID": "OOWY4R001216HX11490", "INF_NM": "청원 심사정보", "INF_EXP": "청원 심사정보를 제공합니다.", "CATE_NM": "주제별 공개>국민참여>국회 민원", "OPEN_DTTM": "2023-12-01", "ORG_NM": "국회사무처", "LOAD_DTTM": "2026-10-28", "SRC_EXP": "국회홈페이지", "DDC_URL": "https://open.assembly.go.kr/portal/data/openapi/downloadOpenApiSpec.do?infId=
- {"INF_ID": "OOWY4R001216HX11494", "INF_NM": "예결산 예비심사 정보 조회", "INF_EXP": "예결산 예비심사 정보를 제공합니다.", "CATE_NM": "주제별 공개>정책", "OPEN_DTTM": "2023-12-01", "ORG_NM": "국회 특별위원회", "LOAD_DTTM": "2026-10-28", "SRC_EXP": "국회홈페이지", "DDC_URL": "https://open.assembly.go.kr/portal/data/openapi/downloadOpenApiSpec.do?

### minutes (회의록)
- {"INF_ID": "OO1X9P001017YF13038", "INF_NM": "본회의 회의록", "INF_EXP": "본회의 회의록 정보를 제공합니다. ", "CATE_NM": "의정활동별 공개", "OPEN_DTTM": "2019-11-15", "ORG_NM": "국회사무처", "LOAD_DTTM": "2026-09-24", "SRC_EXP": "회의록시스템", "DDC_URL": "https://open.assembly.go.kr/portal/data/openapi/downloadOpenApiSpec.do?infId=OO1X9
- {"INF_ID": "OR137O001023MZ19321", "INF_NM": "위원회 회의록", "INF_EXP": "국회상임위원회 및 특별위원회별 회의록 정보를 제공합니다. ", "CATE_NM": "의정활동별 공개>위원회 정보", "OPEN_DTTM": "2019-11-18", "ORG_NM": "국회사무처", "LOAD_DTTM": "2026-09-24", "SRC_EXP": "회의록시스템", "DDC_URL": "https://open.assembly.go.kr/portal/data/openapi/downloadOpenAp
- {"INF_ID": "O8WI650012155G10023", "INF_NM": "전원위원회 회의록", "INF_EXP": "전원위원회 회의록 정보를 제공합니다.", "CATE_NM": "의정활동별 공개", "OPEN_DTTM": "2023-06-02", "ORG_NM": "국회사무처", "LOAD_DTTM": "2026-09-24", "SRC_EXP": "회의록시스템", "DDC_URL": "https://open.assembly.go.kr/portal/data/openapi/downloadOpenApiSpec.do?infId=O8
- {"INF_ID": "OVW2NU000937WK15521", "INF_NM": "국회의원 상임위 활동", "INF_EXP": "국회의원 상임위별 회의 안건 정보를 제공합니다. ", "CATE_NM": "국회의원>국회의원 현황 정보", "OPEN_DTTM": "2019-11-04", "ORG_NM": "국회사무처", "LOAD_DTTM": "2026-09-24", "SRC_EXP": "회의록시스템", "DDC_URL": "https://open.assembly.go.kr/portal/data/openapi/downloadOpenApi
- {"INF_ID": "OZY6M30010164K11655", "INF_NM": "국회의원 기자회견", "INF_EXP": "국회의원 기자회견과 관련된 영상자료 정보를 제공합니다. ", "CATE_NM": "국회의원>국회의원 현황 정보", "OPEN_DTTM": "2019-11-13", "ORG_NM": "국회사무처", "LOAD_DTTM": "2026-10-28", "SRC_EXP": "영상회의록시스템", "DDC_URL": "https://open.assembly.go.kr/portal/data/openapi/downloadOpe
- {"INF_ID": "O3VTTM0010223D15681", "INF_NM": "국회의원 영상회의록(발언영상)", "INF_EXP": "국회의원별 발언영상 정보를 제공합니다. ", "CATE_NM": "주제별 공개>언론·미디어·국회일정", "OPEN_DTTM": "2019-11-18", "ORG_NM": "국회사무처", "LOAD_DTTM": "2026-10-28", "SRC_EXP": "영상회의록시스템", "DDC_URL": "https://open.assembly.go.kr/portal/data/openapi/downloadOp
- {"INF_ID": "OOWY4R001216HX11518", "INF_NM": "공청회 회의록", "INF_EXP": "공청회 회의록 정보를 제공합니다.", "CATE_NM": "의정활동별 공개", "OPEN_DTTM": "2024-03-01", "ORG_NM": "국회사무처", "LOAD_DTTM": "2026-10-28", "SRC_EXP": "국회홈페이지", "DDC_URL": "https://open.assembly.go.kr/portal/data/openapi/downloadOpenApiSpec.do?infId=OOWY4R
- {"INF_ID": "OOWY4R001216HX11519", "INF_NM": "소위원회 회의록", "INF_EXP": "소위원회 회의록 정보를 제공합니다.", "CATE_NM": "의정활동별 공개", "OPEN_DTTM": "2024-03-01", "ORG_NM": "국회 상임위원회", "LOAD_DTTM": "2026-10-28", "SRC_EXP": "국회홈페이지", "DDC_URL": "https://open.assembly.go.kr/portal/data/openapi/downloadOpenApiSpec.do?infId=O
- {"INF_ID": "OOWY4R001216HX11520", "INF_NM": "회의록별 상세정보", "INF_EXP": "회의록별 상세정보를 제공합니다.", "CATE_NM": "의정활동별 공개", "OPEN_DTTM": "2024-03-01", "ORG_NM": "국회사무처", "LOAD_DTTM": "2026-10-28", "SRC_EXP": "국회홈페이지", "DDC_URL": "https://open.assembly.go.kr/portal/data/openapi/downloadOpenApiSpec.do?infId=OOWY4
- {"INF_ID": "OOWY4R001216HX11526", "INF_NM": "의안별 회의록 목록", "INF_EXP": "의안별 회의록 목록 정보를 제공합니다.", "CATE_NM": "의정활동별 공개", "OPEN_DTTM": "2024-03-01", "ORG_NM": "국회사무처", "LOAD_DTTM": "2026-10-28", "SRC_EXP": "국회홈페이지", "DDC_URL": "https://open.assembly.go.kr/portal/data/openapi/downloadOpenApiSpec.do?infId=

### former_members (역대 국회의원 인적사항 / 역대국회의원)
- {"INF_ID": "OBL7NF0011935G18076", "INF_NM": "역대 국회의원 인적사항", "INF_EXP": "역대 국회의원별 소속정당, 위원회, 재선여부, 당선대수 등 인적정보를 제공합니다. ", "CATE_NM": "국회의원>역대 국회 정보", "OPEN_DTTM": "2021-01-08", "ORG_NM": "국회사무처", "LOAD_DTTM": "2026-09-24", "SRC_EXP": "인적자원시스템", "DDC_URL": "https://open.assembly.go.kr/portal/data/open
- {"INF_ID": "OXJNQM001195IT17281", "INF_NM": "역대 국회의원 위원회 경력", "INF_EXP": "역대 국회의원별 위원회 경력 정보를 제공합니다.", "CATE_NM": "국회의원>역대 국회 정보", "OPEN_DTTM": "2021-01-08", "ORG_NM": "국회사무처", "LOAD_DTTM": "2026-09-24", "SRC_EXP": "인적자원시스템", "DDC_URL": "https://open.assembly.go.kr/portal/data/openapi/downloadOpenAp
- {"INF_ID": "OQG5IZ0011449610187", "INF_NM": "역대 국회의원 현황", "INF_EXP": "헌정회에서 제공하는 역대 국회의원 목록과 학력/경력, 소속정당 정보 등을 제공합니다. ", "CATE_NM": "국회의원>역대 국회 정보", "OPEN_DTTM": "2019-12-26", "ORG_NM": "국회사무처", "LOAD_DTTM": "2026-10-28", "SRC_EXP": "헌정회", "DDC_URL": "https://open.assembly.go.kr/portal/data/openapi/
- {"INF_ID": "OKDE3A001150P113085", "INF_NM": "역대 국회의원 재선 현황", "INF_EXP": "역대 국회의 국회의원별 당선횟수와 비율 정보를 제공합니다.", "CATE_NM": "국회의원>역대 국회 정보", "OPEN_DTTM": "2020-01-16", "ORG_NM": "국회사무처", "LOAD_DTTM": "2024-10-08", "SRC_EXP": null, "DDC_URL": "https://open.assembly.go.kr/portal/data/openapi/downloadOpenAp
- {"INF_ID": "OD21030011944P19666", "INF_NM": "역대 국회의원 의원이력", "INF_EXP": "역대 국회의원별 국회의원 이력 정보를 제공합니다.(재직자 미포함)", "CATE_NM": "국회의원>역대 국회 정보", "OPEN_DTTM": "2021-01-08", "ORG_NM": "국회사무처", "LOAD_DTTM": "2026-09-24", "SRC_EXP": "인적자원시스템", "DDC_URL": "https://open.assembly.go.kr/portal/data/openapi/downlo

