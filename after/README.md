# 애프터 (AFTER) · 1단계 MVP

성형 후 예상 얼굴을 **약·중·강 세 버전**으로 AI 생성하고, 그 얼굴로 찍은 인스타용 인생샷을 만들어 **친구 투표 링크**로 공유하는 웹앱.
Next.js 16 App Router · TypeScript · Tailwind v4 · Supabase · fal.ai · Vercel.

**셀링 포인트**: 챗지피티로도 얼굴 편집은 됩니다. 이 앱은 (1) 같은 조건으로 약·중·강을 나란히 비교하고, (2) 링크 하나로 친구들이 로그인 없이 "어디까지 할까"에 투표하고, (3) 그 결과를 스토리 카드로 바로 올릴 수 있다는 점이 다릅니다. 유저는 검색이 아니라 친구의 투표 링크로 들어옵니다.

> 모든 결과물은 AI 시뮬레이션이며 실제 의료 결과가 아닙니다. 특정 병원·의사·시술 가격 정보는 어디에도 넣지 않습니다.

---

## 1. 실행 방법

### 키 없이 바로 돌려 보기 (개발 모드)

```bash
cd after
npm install
cp .env.example .env.local     # 비워 둔 채로 두면 로컬 저장소 + 목 프로바이더로 동작
npm run dev                     # http://localhost:3000
```

- Supabase 키가 없으면 `.local-data/` 폴더에 JSON과 파일로 저장하는 **로컬 저장소**가 켜진다.
- `FAL_KEY` 가 없으면 **목 프로바이더**가 켜져서 입력 사진을 그대로 "생성 결과"로 돌려준다. 워터마크, 공유 카드, OG, 삭제, 크레딧, 분당 제한은 전부 실제와 같은 코드가 돈다.
- `/api/health` 로 지금 어떤 저장소·프로바이더가 쓰이는지 확인할 수 있다.

### 실제 모델과 DB로 돌리기

1. **fal.ai**: https://fal.ai 에서 API 키 발급 → `.env.local` 의 `FAL_KEY`.
2. **Supabase 프로젝트 생성** 후
   - Project Settings → API 에서 `NEXT_PUBLIC_SUPABASE_URL`, `NEXT_PUBLIC_SUPABASE_ANON_KEY`, `SUPABASE_SERVICE_ROLE_KEY` 복사.
   - Authentication → Sign In / Providers → **Anonymous sign-ins 켜기** (익명 세션에 필수).
   - SQL Editor 에서 `supabase/migrations/0001_init.sql` 실행 (테이블, 함수, 버킷 생성).
   - Database → Extensions 에서 `pg_cron`, `pg_net` 켜기.
   - `supabase/migrations/0002_cron.sql` 의 `__CLEANUP_URL__`, `__CRON_SECRET__` 을 바꾼 뒤 실행 (30분마다 만료 데이터 삭제).
3. `CRON_SECRET` 에 긴 랜덤 문자열.
4. `npm run dev` → 셀카로 처음부터 끝까지 한 번 돌려 본다.

### 검증용 스크립트

```bash
npm run lint && npx tsc --noEmit && npm run build

# API 스모크 테스트 (dev 서버를 띄운 뒤, 키 없이 목으로 전 구간)
node scripts/make-test-face.mjs                      # 가짜 얼굴 이미지 생성 (브라우저 얼굴 감지는 통과 못 함, API 전용)
CRON_SECRET=<.env.local 값> bash scripts/smoke-flow.sh   # 단일 모드: 세션→업로드→얼굴→402→인생샷→공유→OG→분당제한→크론→삭제
bash scripts/smoke-compare-vote.sh                    # 비교 모드: 약·중·강 3장→선택→인생샷→공유→투표 2명→집계
```

---

## 2. 배포 방법 (Vercel)

1. Vercel 에서 이 저장소를 Import.
2. **Root Directory 를 `after` 로 지정** (저장소 루트에는 다른 프로젝트가 있다).
3. Environment Variables 에 `.env.example` 의 항목을 넣는다. `NEXT_PUBLIC_APP_URL` 은 최종 도메인(예: `https://after.example.com`)으로. 비워 두면 Vercel 프로덕션 URL 을 자동으로 쓴다.
4. 배포 후 Supabase 크론의 `__CLEANUP_URL__` 을 `https://<도메인>/api/cron/cleanup` 으로 맞춘다.
5. 배포 확인: `https://<도메인>/api/health` 가 `"store":"supabase","provider":"fal"` 을 돌려주면 정상.

Supabase pg_cron 대신 Vercel Cron 을 쓰고 싶으면 `vercel.json` 에 아래를 추가하고 Vercel 의 `CRON_SECRET` 환경변수를 그대로 쓰면 된다 (Vercel 이 자동으로 Bearer 헤더를 붙인다).

```json
{ "crons": [{ "path": "/api/cron/cleanup", "schedule": "*/30 * * * *" }] }
```

---

## 3. 모델 교체 방법

모든 모델 호출은 `src/lib/providers/types.ts` 의 `ImageEditProvider` 인터페이스(submit / status / result)를 통해서만 이루어진다.

| 바꾸고 싶은 것 | 할 일 |
|---|---|
| fal 안에서 다른 모델로 | `.env` 의 `FACE_MODEL_ID` / `PHOTO_MODEL_ID` 만 변경. 입력 스키마가 다르면 `src/lib/providers/fal.ts` 의 `MODEL_ADAPTERS` 에 한 줄 추가 |
| fal 이 아닌 다른 API 회사로 | `ImageEditProvider` 를 구현한 파일을 `src/lib/providers/` 에 추가하고 `index.ts` 의 `switch` 에 등록 |
| 목으로 강제 | `IMAGE_PROVIDER=mock` |

현재 기본값 (2026-09 기준 fal.ai 에서 유효한 ID):

| 용도 | 모델 ID | 입력 | 비고 |
|---|---|---|---|
| 성형 후 얼굴 | `fal-ai/flux-pro/kontext` | `image_url` 1장 + prompt | 장당 약 $0.04 |
| 인생샷 | `fal-ai/nano-banana-pro/edit` | `image_urls` 여러 장 + prompt, `num_images` | 장당 약 $0.15, 레퍼런스 최대 14장 |
| 인생샷 저가 대안 | `fal-ai/nano-banana-2/edit` | 동일 | 장당 약 $0.08, 속도 우선 |

무료 세션 1회의 원가는 약 $0.04 + $0.60 = **$0.64** 다. 비용이 부담되면 `PHOTO_MODEL_ID=fal-ai/nano-banana-2/edit` 로 내린다.

### 프롬프트

`prompts/` 폴더에 있다. 코드가 아닌 문장만 고치면 된다.

- `prompts/surgery.ts` — 부위(코·눈·턱선·이마·입술) × 강도(약·중·강) 문장표, 보존 지시 블록, 프리셋 정의. 조합이 어떻게 문장으로 바뀌는지 파일 상단 주석에 설명.
- `prompts/lifeshot.ts` — 장소 6종 × 분위기 3종 문장, 얼굴 동일성 최우선 블록, 품질 블록.

---

## 4. 구조

```
after/
├─ prompts/                 프롬프트 템플릿 (surgery.ts, lifeshot.ts)
├─ content/legal/           미성년자 차단·얼굴 데이터 동의·고지 문구 (여기만 고치면 됨)
├─ supabase/migrations/     스키마, 크레딧·분당제한 함수, 버킷, 크론
├─ src/
│  ├─ app/                  페이지: / → /upload → /select → /face → /photos, 공개 공유 /s/[id]
│  │  └─ api/               session, upload, generate/{face,photos,face/choose}, generations/[id], share, share/[id]/{story,vote}, delete, waitlist, cron/cleanup
│  ├─ app/privacy           사진 처리 안내 페이지 · app/opengraph-image.tsx 랜딩 OG
├─ scripts/                 스모크 테스트 (make-test-face.mjs, smoke-flow.sh, smoke-compare-vote.sh)
│  ├─ components/           슬라이더, 로딩 문장, 페이월 모달, 삭제 버튼, 투표 패널·집계
│  ├─ lib/vote.ts           투표 질문·선택지 정의 (서버·클라이언트 공용)
│  ├─ lib/
│  │  ├─ brand.ts           브랜드명·강조색·워터마크 문구 상수
│  │  ├─ config.ts          무료 크레딧, 보관 기간, 분당 제한
│  │  ├─ providers/         ImageEditProvider 인터페이스, fal 구현, mock 구현
│  │  ├─ store/             Store 인터페이스, Supabase 구현, 로컬 파일 구현
│  │  ├─ image/             정규화, 워터마크, 공유 카드·OG 합성 (sharp + satori)
│  │  ├─ generation.ts      생성 시작·폴링·결과 처리 (크레딧, 분당 제한 포함)
│  │  └─ session.ts         익명 세션 (Supabase anonymous auth / 로컬 쿠키)
│  └─ assets/fonts/         Pretendard (서버 텍스트 렌더링용)
└─ public/mediapipe/        얼굴 감지 모델 (BlazeFace short-range)
```

### 데이터 흐름

1. 랜딩에서 두 체크박스 → `POST /api/session` → Supabase 익명 로그인(쿠키) + 무료 크레딧 지급.
2. 업로드: 브라우저에서 MediaPipe 로 얼굴 수 검사(0명·2명 이상 거부) → 서버에서 EXIF 제거·리사이즈 → **private 버킷**.
3. 얼굴 생성: 분당 제한 → 크레딧 차감 → 20분짜리 서명 URL 로 모델에 전달 → 큐에 제출. **비교 모드(기본)** 는 켜진 부위를 약·중·강으로 각각 3번 제출하고 크레딧은 1회만 쓴다. 브라우저가 `GET /api/generations/[id]` 를 2.5초마다 폴링하고, 완료되면 그 요청 안에서 결과를 내려받아 **워터마크를 굽고 public 버킷**에 저장한다. 워터마크 없는 사본은 private 에만 둔다(인생샷 레퍼런스·공유 카드 합성용).
4. 강도 선택: 결과 화면에서 세 장 중 하나를 고르면 `POST /api/generate/face/choose`. 인생샷과 공유 OG 는 이 선택을 쓴다. 기본은 "중".
5. 인생샷: 레퍼런스 순서 = 선택한 성형 후 얼굴(깨끗한 사본) → 원본 정면 → 원본 측면. 4장 한 세트.
6. 공유: OG 1200×630(선택한 얼굴 + 인생샷 4장) 은 public. 스토리 1080×1920 은 private 에 저장하고 본인만 서명 URL 로 내려받는다: 약·중·강 비교 슬라이드(비교 모드) + 비포/애프터(원본 포함) + 인생샷 4장. 공유 페이지 `/s/[id]` 는 public 파일만 참조한다.
7. 투표: 공유 페이지에서 로그인 없이 한 표 (`after_voter` 쿠키로 브라우저당 1표, 변경 가능). 비교 모드는 약/중/강/안 하는 게 나아, 단일 모드는 해!/좀 더 고민. 투표한 사람과 주인에게만 집계가 보인다. 주인은 결과 화면과 `/api/session` 에서 집계를 본다.
8. 삭제: "내 데이터 즉시 삭제" 버튼 → 원본·생성물·공유·투표 전부 삭제. 크론은 30분마다 만료분 삭제.
9. 퍼널 이벤트: `events` 테이블에 서버가 기록. session_started → upload_done → face_started → face_done → face_chosen → photos_started → photos_done → share_created → share_view → vote_cast, 그리고 waitlist_joined, data_deleted, *_failed. SQL 한 줄로 단계별 이탈률을 볼 수 있다.

---

## 5. 내가 내린 결정 (README 기록 요청 사항)

- **코드 위치**: 저장소의 `after/` 하위 폴더. Vercel Root Directory 를 `after` 로.
- **무료 크레딧**: 얼굴 1회, 인생샷 4장(= 한 세트). 명세의 "3장"은 4장 세트와 충돌해 4장으로 확정.
- **보관 기간**: 원본 24시간, 생성물·공유 카드·공유 링크 7일. `src/lib/config.ts` 에서 변경.
- **프리셋 기본값**: 자연스럽게 = 눈·코·턱선 약, 확실하게 = 눈·코·턱선·입술 중, 이마는 둘 다 끔. 프리셋과 별개로 다섯 부위 각각 켜고 끄고 강도 선택이 항상 가능하며, 손대면 자동으로 "내가 고르기"가 된다.
- **익명 세션**: Supabase Anonymous Sign-in. 서버가 로그인하고 `@supabase/ssr` 이 httpOnly 쿠키를 관리. 브라우저는 DB 에 직접 접근하지 않는다(RLS 정책 없음 = 전부 차단, 서버는 service role).
- **얼굴 감지**: MediaPipe Tasks Vision Face Detector. 모델 파일은 `public/`, wasm 은 jsDelivr CDN(버전 고정).
- **워터마크·합성**: sharp + satori. satori 가 글자를 path 로 바꾸므로 서버에 한글 폰트가 없어도 된다. Pretendard 를 번들에 포함.
- **분당 제한**: Postgres 함수(고정 윈도우) 로 세션당 분당 5회. 서버리스라 메모리 카운터는 못 쓴다. 로컬 저장소에서는 프로세스 메모리.
- **긴 작업 처리**: 서버는 절대 모델 완료를 기다리지 않는다(Vercel 함수 시간 제한 회피). 제출만 하고 폴링 요청이 결과를 처리한다. 폴링이 끊기면 다음 폴링에서 이어서 처리된다.
- **공유 카드 중 비포/애프터 슬라이드**: 원본이 들어가므로 공개 페이지에는 절대 올리지 않고 본인 다운로드용으로만 제공한다. 공개 OG 는 애프터 얼굴 + 인생샷으로만 구성.
- **실패 시 크레딧**: 모델 실패나 결과 처리 실패 시 자동 환불.
- **Kontext safety_tolerance**: 기본 2 대신 3. 얼굴 편집이 과하게 차단되면 `FACE_SAFETY_TOLERANCE` 로 조정.
- **크론**: `storage.objects` 행을 직접 지우면 실제 파일이 남으므로 pg_cron → pg_net → `/api/cron/cleanup` 호출 구조.
- **비교 모드 기본 ON**: 강도 비교가 핵심 가치라 기본값으로 켰다. 끄면 사용자가 고른 강도 한 장만 만든다. 비교 모드에서는 부위별로 고른 강도는 무시되고 켜짐 여부만 쓴다.
- **투표는 익명·쿠키 기반**: 로그인 장벽을 없애는 대신 쿠키를 지우면 재투표가 가능하다. 바이럴 테스트 단계에서는 감수한다.
- **집계 공개 시점**: 편향을 줄이려고 투표하기 전에는 집계를 숨긴다. 주인은 항상 본다.
- **랜딩 OG**: `src/app/opengraph-image.tsx` 로 빌드 시 정적 생성. 문구는 `brand.ts`.
- **개인정보 안내 페이지** `/privacy`: `content/legal/` 문구를 모아 보여준다. 법률 검토 전 임시본.

---

## 6. 나중에 손봐야 할 항목

**출시 전 필수**
- [ ] `FAL_KEY`, Supabase 키를 넣고 **본인 셀카로 전 구간 실행**. 이 환경에는 키가 없어 실제 모델 호출은 코드 리뷰만 됐고 목으로만 검증했다.
- [ ] 실제 결과를 보고 `prompts/surgery.ts` 의 강도별 문장과 `FACE_GUIDANCE_SCALE`(기본 3.5) 튜닝. Kontext 가 정체성을 무너뜨리면 guidance 를 낮추고, 변화가 약하면 문장을 세게. 비교 모드에서 약·중·강이 눈에 띄게 달라야 투표가 의미 있다. 같은 시드(`seed`)를 세 장에 쓰도록 `fal.ts` 에서 조정하면 차이가 강도에서만 나온다.
- [ ] 인생샷 얼굴 동일성이 약하면 `prompts/lifeshot.ts` 의 IDENTITY_BLOCK 을 조정하거나 측면 사진 업로드를 강하게 권장.
- [ ] `content/legal/*.ts` 의 동의 문구를 법률 검토 후 확정. 개인정보 처리방침 페이지 추가.
- [ ] Supabase 대시보드에서 익명 가입 남용 방지(Captcha 또는 rate limit) 설정. 지금은 새 시크릿 창마다 무료 크레딧을 다시 받을 수 있다.
- [ ] 도메인 확정 후 `NEXT_PUBLIC_APP_URL`, 크론 URL 갱신. 카카오톡·인스타 미리보기가 OG 를 제대로 읽는지 실제 링크로 확인.

**곧 필요**
- [ ] 결제 연동. 크레딧 테이블·차감 함수는 이미 있으니 결제 성공 웹훅에서 `refund_credits` 와 같은 방식으로 충전만 붙이면 된다. 페이월 모달(`src/components/PaywallModal.tsx`)을 결제 버튼으로 교체.
- [ ] 대기 리스트(`waitlist` 테이블) 이메일 발송 툴 연결.
- [ ] 익명 auth 유저 정리: 세션 행은 남기고 파일만 지우는 구조라 `auth.users` 가 쌓인다. 30일 이상 된 익명 유저 삭제 크론 추가.
- [ ] 퍼널 대시보드. 이벤트는 이미 `events` 테이블에 쌓이니 Supabase SQL 로 `select name, count(distinct session_id) from events group by name` 부터 시작.
- [ ] 투표 알림: 주인이 페이지를 떠난 뒤에는 결과를 볼 방법이 세션 쿠키뿐이다. 이메일(대기 리스트와 같은 입력)로 "투표 N표 모였어요" 알림을 보내면 재방문 훅이 된다.

**품질**
- [ ] Nano Banana Pro 가 `num_images=4` 에서 4장을 안 주는 경우 대비: `fal.ts` 의 `maxImagesPerCall` 을 1 로 낮추고 `SHOT_VARIATIONS` 를 장별로 붙이는 옵션.
- [ ] 결과 이미지 로딩 스켈레톤, 공유 페이지에 인생샷 확대 보기.
- [ ] MediaPipe wasm 을 CDN 이 아닌 자체 호스팅으로(약 22MB 라 저장소에 넣지 않았다).
- [ ] 폰트 서브셋(Pretendard 3MB → 수백 KB)으로 콜드 스타트 단축.
- [ ] 워터마크 위치·크기가 결과 구도를 가릴 때 대비해 상단/하단 자동 선택.

---

## 7. 완료 기준 체크

| 기준 | 상태 |
|---|---|
| 셀카 → 성형 후 얼굴 (약·중·강 3장) | 코드 완성, 목으로 전 구간 확인. 실제 모델은 키 투입 후 확인 필요 |
| 인생샷 4장 | 동일 |
| 공유 링크가 OG 이미지와 함께 열림 | 로컬에서 OG 메타·이미지 확인 완료. 실제 도메인에서 재확인 필요 |
| 친구 투표 (추가) | 로컬에서 방문자 2명 투표·변경·집계·삭제 연동 확인 완료 |
