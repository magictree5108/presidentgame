# API 키 발급과 설치 안내 (복사해서 따라 하기)

> 화면 이름은 사이트 개편으로 조금 다를 수 있습니다. 비슷한 이름의 메뉴를 찾으면 됩니다.
> 키는 **`.env` 파일에만** 넣습니다. 이 파일은 git에 올라가지 않습니다.

## 0. 준비 (한 번만)

1. Python 3.11 이상 설치: https://www.python.org/downloads/ → 설치 화면에서 **"Add python.exe to PATH" 체크** (Windows)
2. 이 저장소를 내려받은 폴더에서 터미널(Windows: PowerShell, Mac: 터미널)을 열고 한 줄씩 붙여넣기:

```
cd jeongmu
python -m pip install -r requirements.txt
```

3. 키 파일 만들기
   - Windows: `copy .env.example .env`
   - Mac: `cp .env.example .env`
4. `.env` 를 메모장(또는 텍스트 편집기)으로 열어 아래에서 받은 키를 `=` 뒤에 붙여넣고 저장합니다.

## 1. 열린국회정보 Open API 키 → `ASSEMBLY_API_KEY`

1. https://open.assembly.go.kr 접속 → 오른쪽 위 **회원가입** → 가입 후 **로그인**
2. **마이페이지** → **인증키 발급**(또는 "OPEN API 인증키 신청")
3. 활용 용도에 "국회 의정활동 분석 도구(개인 연구)" 정도로 적고 신청 → 화면에 나온 인증키 복사
4. `.env` 의 `ASSEMBLY_API_KEY=` 뒤에 붙여넣기
5. 확인: `python src/check_apis.py` → `docs/api_check.md` 에 서비스별 "확인됨"이 나오면 성공

## 2. 네이버 뉴스 검색 키 → `NAVER_CLIENT_ID`, `NAVER_CLIENT_SECRET`

2026년부터 네이버 검색 API는 **네이버 클라우드의 NAVER API HUB**에서 새로 발급합니다(네이버 개발자센터 목록에는 '검색'이 없을 수 있음). 하루 25,000회 한도.

1. https://www.ncloud.com 접속 → 네이버 아이디로 로그인(처음이면 회원가입·결제수단 등록 요구가 있을 수 있음)
2. 오른쪽 위 **콘솔** → 왼쪽 위 **Menu** → **All Services → Application Services → NAVER API HUB**
3. 왼쪽 **Application** → **[Application 등록]** → 사용할 API에서 **검색** 선택 → **[다음]** → 이름 `정무상황실` → **[완료]**
4. 만든 Application 선택 → **API 관리 → [인증 정보]** → **Client ID**, **Client Secret** 복사
5. `.env` 의 `NAVER_CLIENT_ID=`, `NAVER_CLIENT_SECRET=` 뒤에 붙여넣기

예전에 네이버 개발자센터(developers.naver.com)에서 받은 검색 키가 있다면 그 키도 같은 칸에 넣으면 그대로 작동합니다(프로그램이 두 방식을 자동으로 시도).

## 3. Anthropic API 키 → `ANTHROPIC_API_KEY`

1. https://platform.claude.com 접속 → 가입·로그인
2. **Settings → Billing** 에서 결제 수단 등록·크레딧 충전 (실측: 판단 1회 70~110원, 워게임 1판 130~170원, 기사 1건 추출 약 0.2원. 실제 비용은 화면 '적중 기록 → AI 비용'에 기록됨)
3. **API Keys → Create Key** → 이름 `jeongmu` → 만들어진 키(`sk-ant-...`)를 바로 복사 (다시 볼 수 없음)
4. `.env` 의 `ANTHROPIC_API_KEY=` 뒤에 붙여넣기

## 4. (선택) 법제처 국가법령정보 OC → `LAW_OC`

규칙집 조문 대조에 씁니다. 지금은 공개 테스트값으로도 동작하지만, 정식 사용은 신청을 권장합니다.
1. https://open.law.go.kr → 회원가입 → **OPEN API 신청**
2. 가입한 이메일의 `@` 앞부분이 OC 값입니다 → `.env` 의 `LAW_OC=` 뒤에 적기

## 5. 처음 실행 순서

```
python src/check_apis.py
python src/update_assembly.py
python src/metrics.py
python src/verify_data.py
python run.py
```

마지막 줄을 실행한 뒤 브라우저에서 http://127.0.0.1:8000 을 엽니다. 끌 때는 터미널에서 `Ctrl + C`.

## 6. 매일 새벽 자동 갱신

### Windows (작업 스케줄러)
1. 시작 메뉴 → **작업 스케줄러** → 오른쪽 **기본 작업 만들기**
2. 이름 `정무상황실 갱신` → 트리거 **매일**, 시각 **오전 4:17**
3. 동작 **프로그램 시작** → 프로그램: `python` / 인수: `daily.py` / 시작 위치: `jeongmu` 폴더 전체 경로
4. 컴퓨터가 켜져 있어야 실행됩니다. ("작업 → 속성 → 조건"에서 "작업을 실행하기 위해 절전 모드 종료" 체크 권장)

### Mac
터미널에서 `crontab -e` 를 열고 아래 한 줄 추가(경로는 본인 것으로):
```
17 4 * * * cd /Users/내이름/presidentgame/jeongmu && /usr/bin/python3 daily.py >> data/logs/daily.log 2>&1
```

### 서버에 올릴 경우
같은 cron 줄을 서버에 넣으면 됩니다. 서버 배포를 원하면 말씀해 주세요(별도 단계).
