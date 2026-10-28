# 사용하는 API 정리

## 확인 상태

2026-10-28 인증키로 **실제 호출해서 확인**했습니다(`python src/check_apis.py` → `docs/api_check.md`).
- 처음에 이 환경에서 접속이 안 됐던 원인: 서버가 브라우저 식별 헤더(User-Agent) 없는 요청을 "Bad Request."로 거절함. 수집기에 헤더를 넣어 해결.
- 위원회 위원 명단·위원회 현황 코드는 포털의 공식 API 명세서(엑셀) 안 '요청주소'에서 확인.

## 열린국회정보 (open.assembly.go.kr)

공통 요청: `https://open.assembly.go.kr/portal/openapi/<서비스코드>?KEY=<키>&Type=json&pIndex=<페이지>&pSize=<건수>`
공통 응답: `{"<코드>": [{"head": [{"list_total_count": N}, {"RESULT": {"CODE": "INFO-000"}}]}, {"row": [...]}]}`
(공통 인자 KEY/Type/pIndex/pSize 는 포털 서비스 상세 페이지에서 확인함 — 웹 조회 도구로 열람)

| 용도 | API 이름 | 서비스 코드 | 필수 인자 | 주요 필드(예상) | 상태 | 찾은 곳 |
|---|---|---|---|---|---|---|
| 의원 인적사항·소속위원회 | 국회의원 인적사항 | `nwvrqwxyaytdsfvhu` | — | MONA_CD, HG_NM, HJ_NM, POLY_NM, ORIG_NM, ELECT_GBN_NM, REELE_GBN_NM, UNITS, CMITS | 확인됨 (299명) | nureongso README |
| 발의 법률안(대표·공동발의) | 국회의원 발의법률안 | `nzmimeepazxkubdpn` | AGE | BILL_ID, BILL_NO, BILL_NAME, COMMITTEE, PROPOSE_DT, PROC_RESULT, RST_PROPOSER, PUBL_PROPOSER, CMT_PROC_DT, LAW_PROC_DT, PROC_DT, DETAIL_LINK | 확인됨 (22대 20,168건) | velog 의안 API 문서, nureongso |
| 본회의 표결 결과(의안별 집계) | 의안별 표결현황 | `ncocpgfiaoituanbr` | AGE | BILL_ID, PROC_DT, MEMBER_TCNT, VOTE_TCNT, YES_TCNT, NO_TCNT, BLANK_TCNT | 확인됨 (1,911건) | velog 문서, nureongso |
| 의원별 표결 | 국회의원 본회의 표결정보 | `nojepdqqaweusdfbi` | AGE, BILL_ID | MONA_CD, HG_NM, POLY_NM, RESULT_VOTE_MOD, VOTE_DATE | 확인됨 (표결당 299명) | nureongso, PyPI `kna` |
| 위원장 대안·정부안 포함 의안 | 의안검색 | `TVBPMBILL11` | — | — | 확인됨 (22대 21,582건) | velog, nureongso |
| 처리 의안 | 처리의안 | `nzpltgfqabtcpsmai` | AGE | — | 미검증 | velog |
| 계류 의안 | 계류의안 | `nwbqublzajtcqpdae` | — | — | 미검증 | velog |
| 심사 진행 | 심사정보(예·결산 제외) | `BILLJUDGE` | — | — | 미검증 | velog |
| 법사위 회의 | 법사위 회의정보 | `BILLLWJUDGECONF` | BILL_ID | — | 미검증 | velog |
| 제안자 | 제안자정보 | `BILLINFOPPSR` | BILL_ID | — | 미검증 | velog |
| 역대 의원 | 역대 국회의원 인적사항 | `ALLNAMEMBER` | — | — | 미검증 | nureongso |
| API 목록 | 열린국회정보 OpenAPI 목록 | `OPENSRVAPI` | — | — | 확인됨 (280개) | nureongso |
| 위원회 위원(위원장·간사·위원) | 위원회 위원 명단 | `nktulghcadyhmiqxi` | — | DEPT_CD, DEPT_NM, JOB_RES_NM, HG_NM, POLY_NM, MONA_CD (연락처·보좌진 칸은 저장 안 함) | 확인됨 (474명, 위원회 중복 포함) | 포털 API 명세서 |
| 위원회 현황 | 위원회 현황 정보 | `nxrvzonlafugpqjuh` | — | HR_DEPT_CD, COMMITTEE_NAME, CMT_DIV_NM, HG_NM(위원장), HG_NM_LIST(간사), LIMIT_CNT, CURR_CNT | 확인됨 (359건) | 포털 API 명세서 |
| 회의록 목록 | 본회의 회의록 / 위원회 회의록 / 의안별 회의록 목록 | (명세서에서 확인 예정) | — | — | 목록에서 찾음, 코드 미확인 | OPENSRVAPI |

참고한 문서
- velog "OpenAPI - '의안' 관련 사용 참고 문서": https://velog.io/@assembly101/OpenAPI-의안-관련-사용-참고-문서-작성-진행중
- GitHub teiresias22/nureongso README 데이터 출처 표: https://github.com/teiresias22/nureongso
- PyPI `kna` 패키지(표결 서비스 코드 언급)

## 법제처 국가법령정보 공동활용 (확인됨, 실제 사용 중)

| 용도 | 요청 | 비고 |
|---|---|---|
| 법령 검색 | `https://www.law.go.kr/DRF/lawSearch.do?OC=<OC>&target=law&type=JSON&query=<법령명>` | 현행 법령의 법령일련번호(MST) 확인 |
| 법령 본문 | `https://www.law.go.kr/DRF/lawService.do?OC=<OC>&target=law&type=JSON&MST=<일련번호>` | 조문단위 → 항 → 호 → 목 |

2026-10-27 실제 호출로 대한민국헌법, 국회법(법률 제21883호, 2026.10.2 시행), 정부조직법(법률 제21491호, 2026.10.2 시행), 국정감사 및 조사에 관한 법률 원문을 받아 규칙집 20개를 대조했습니다.

## 네이버 뉴스 검색

`GET https://openapi.naver.com/v1/search/news.json?query=&display=&start=&sort=date`
헤더 `X-Naver-Client-Id`, `X-Naver-Client-Secret`. 응답 items: title, originallink, link, description, pubDate.
(키 발급 후 첫 실행에서 확인 필요)

## Anthropic

모델 `claude-opus-5-5`, Messages API(스트리밍), JSON 스키마 출력(`output_config.format`), 거절 시 서버측 대체(`fallbacks: "default"`).
가격 입력 $4 / 출력 $20 (100만 토큰당). 2026-10 Anthropic 공식 SDK 문서 기준.
