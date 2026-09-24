# [INFRA-102] 데이터 상태 화면의 업데이트 시작 실패를 화면에 보이고 409 뒤 진행 상황을 폴링한다 — QA 기록

- 대상: `frontend/src/app/dashboard/data-status/page.tsx` 의 `handleUpdate`·`handleUpdateAll`(공용 `showStartUpdateError`: 409 면 「업데이트 중복」 모달과 `startPolling()`, 그 밖은 「업데이트 오류」 모달)
- 단계(phase): 완료 | 시나리오 구성 완료 | 실행 완료
- 구성 2026-09-25 06:25 | 실행 2026-09-25 06:24:31 시작(수정 전), 06:25:32 시작(수정 뒤)
- 검증 기준 커밋: `f8fea11`(이 문서를 담은 첫 커밋). 대조는 수정 전 커밋 `7a39468`. 사본은 각 커밋의 `git archive` 다
- 구성 근거: 설계 승인(대화 06:20), 호출 경로(카드 「업데이트」·「전체 데이터 업데이트」 → `fetchAPI('/api/system/start-update')` → Next rewrite → Flask `require_admin` → `api_start_update`), 관리자 판정(`useAdmin` 은 마운트 때 `/api/admin/check` 를 한 번 부른다. 화면을 연 뒤 사본 Flask 만 다른 `ADMIN_EMAILS` 로 재기동하면 화면은 관리자인 채로 시작 요청만 `require_admin` 에서 403 을 받는다), 폴링 규칙(`update-status` 는 상태 파일을 읽기만 한다)
- QA 엔진(engine): Claude Code. browser_applicability: required(browser_driver: agent-browser). 사용자가 보는 것은 모달과 진행 표시다
- 격리: `[INFRA-100]` 과 같다. 각 커밋의 `git archive` 사본에서 `secrets/`·`data/`·`.env` 를 지우고 빈 `data/` 를 만든다. 사본 Flask 는 gunicorn 1 worker·`SCHEDULER_ENABLED=false`, 사본 Next 는 `API_URL` 을 사본 Flask 로 둔다. 더미 `NEXTAUTH_SECRET`·`INTERNAL_IDENTITY_SECRET`·`ADMIN_EMAILS=qa-admin@example.com` 을 환경 변수로만 주고, 같은 더미 비밀로 `next-auth/jwt` 의 `encode` 가 만든 세션 토큰을 `next-auth.session-token` 쿠키로 넣는다. `node_modules` 는 `cp -Rc` 로 사본 안에 둔다. 원본 3500·5501·`data/`·`.env`·운영 주소는 쓰지 않는다
- 안전: 모든 시작 클릭은 사본 상태 파일이 `isRunning: true` 일 때만 한다. 403 경로는 `require_admin` 이 본문보다 먼저 거부하고, 관리자 판정이 뜻밖에 통과해도 409 로 거부되므로 수집·LLM·KRX 로그인이 일어나지 않는다. 5xx 경로는 사본 Flask 를 멈춘 상태라 요청이 백엔드에 닿지 않는다. 각 클릭 전에 상태 파일을 다시 읽어 확인한다
- 금지: 상태 파일이 실행 중이 아닐 때의 시작 클릭, 중지 버튼, 메시지 발송, 설정 저장, Refresh, AI 재분석, 챗봇 전송, 모의 매수
- 필수 여부(required): S-1~S-4 예
- 실행: 세션 스크래치의 `infra102qa_run.sh <사본> <표식>`(agent-browser `--namespace infra102qa`, 사본 gunicorn 58101·Next dev 58102, 두 사본을 차례로). 사본 Flask 는 스크립트가 시나리오마다 멈추고 다시 띄운다
- 반복(iteration): 1회
- 결과: 통과 (필수 4/4)
- 증거: 아래 「실제」 줄(스크립트 출력 원문), scratchpad `qa-infra102-{old,new}-{flask,next}.log`, 스크린샷 `infra102qa-new-s1.png`·`infra102qa-new-s3a.png`(열어 확인)과 나머지 `infra102qa-{old,new}-s{1,2,3a,3b}.png`(세션 임시)
- 기대값에서 뺀 경우(리뷰 L-1): `[INFRA-099]` 의 「이 워커에서 중단된 앞 실행」 때문에 상태 파일이 실행 중이 아닌데도 409 가 나는 경우는 폴링이 한 번 돌고 멈춰 진행 표시가 없다. 종전과 같은 동작이며 이 QA 는 상태 파일이 실행 중인 409 만 본다

## 시나리오

### S-1. 개별 「업데이트」가 403 을 받으면 「업데이트 오류」 모달에 사유가 보인다 (브라우저, 필수)
- 조작: 관리자 세션으로 `/dashboard/data-status` 를 연다. 사본 Flask 를 `ADMIN_EMAILS=other-admin@example.com` 으로 재기동하고, 상태 파일을 실행 중으로 바꾼 뒤 첫 카드의 「업데이트」를 누른다
- 기대: 수정 뒤는 `POST /api/system/start-update` 403, 「업데이트 오류」 모달과 Flask 가 준 사유 문구. 수정 전(`7a39468`)은 같은 403 에 모달이 없고 콘솔 오류만 남는다
- 실제: 두 사본 모두 관리자 화면 확인(「전체 데이터 업데이트」 1, 「관리자 전용」 0), 클릭 전후 상태 파일이 실행 중. 수정 전(`7a39468`): `POST http://localhost:58102/api/system/start-update (Fetch) 403`, 「업데이트 오류」 0·「업데이트 중복」 0, 「확인」 버튼 없음(`no modal`), 콘솔 `Update failed for Daily Prices: {status: 403 … message: "Forbidden"}`(결함 재현). 수정 뒤: 같은 요청 403, 「업데이트 오류」 1·본문 「Forbidden」, 스크린샷에서 「업데이트 오류 / Forbidden」 모달 확인. 통과. 본문이 영어 「Forbidden」인 것은 `require_admin` 이 주는 문구 그대로이며 전체 업데이트와 같은 표시 방식이다

### S-2. 백엔드가 멈춘 상태에서 개별 「업데이트」가 실패하면 「업데이트 오류」 모달이 보인다 (브라우저, 필수)
- 조작: S-1 모달을 닫고 사본 Flask 를 멈춘 뒤 「업데이트」를 누른다
- 기대: 수정 뒤는 5xx 응답과 「업데이트 오류」 모달. 수정 전은 모달이 없다
- 실제: 사본 Flask 리스너 0 확인. 수정 전: 요청 `500`, 「업데이트 오류」 0, `no modal`(결함 재현). 수정 뒤: 요청 `500`, 「업데이트 오류」 1·본문 「API Error: 500」. 통과

### S-3. 409 로 거부되면 중복 모달을 닫은 뒤 진행 중인 실행의 진행 표시가 보인다 (브라우저, 필수)
- 조작: 사본 Flask 를 원래 `ADMIN_EMAILS` 로 다시 띄우고 화면을 새로 연다(상태 파일 실행 중 아님). 상태 파일을 `currentItem: "Daily Prices"` 인 실행 중으로 바꾼 뒤 (a) 첫 카드의 「업데이트」를 누르고 모달을 닫는다. 상태 파일을 실행 중 아님으로 돌려 폴링이 멈추는 것을 본 뒤 화면을 새로 열고, 다시 실행 중으로 바꿔 (b) 「전체 데이터 업데이트」를 누르고 모달을 닫는다
- 기대: 수정 뒤는 (a)(b) 모두 409, 「업데이트 중복」 모달, 모달을 닫으면 「Daily Prices 업데이트 중...」 진행 표시와 「중지」 버튼이 보이고 `update-status` 요청이 이어진다. (a) 뒤 상태 파일을 실행 중 아님으로 돌리면 진행 표시가 사라진다. 수정 전은 모달만 뜨고 진행 표시가 없으며 `update-status` 요청이 이어지지 않는다
- 실제: 수정 전: (a)(b) 모두 409·「업데이트 중복」 1, 모달을 닫은 뒤 진행 표시 0·「중지」 0, `update-status` 요청 0(폴링 없음, 결함 재현). 수정 뒤: (a)(b) 모두 409·「업데이트 중복」 1, 모달을 닫은 2초 뒤 「Daily Prices 업데이트 중」 1·「중지」 1, `update-status` 요청 각 7건, 스크린샷에서 헤더의 「Daily Prices 업데이트 중...」·「업데이트 중...」·「중지」 확인. (a) 뒤 상태 파일을 실행 중 아님으로 돌리자 진행 표시 0·「전체 데이터 업데이트」 1 로 돌아옴(폴링이 스스로 멈춤). 통과

### S-4. 거부된 시작은 상태와 자료를 바꾸지 않는다 (필수)
- 조작: 각 클릭 전후 사본 상태 파일 해시, `data/` 목록, 사본 Flask 로그를 읽는다
- 기대: 상태 파일은 QA 가 쓴 내용 그대로, `data/` 에 수집 산출물 없음, 로그에 파이프라인 시작 줄(`Background Update`·`init_data`·`KRX 로그인`) 없음
- 실제: 두 사본 모두 각 시나리오 클릭 전후 상태 파일 SHA-256 앞 12자리 `6f685892b0f8` 로 같음, `data/` 는 기동 때 생긴 `runtime_cache.db`·`scheduler_runtime_status.json`·`update_status.json`·`v2_screener_status.json`·`vcp_status.json` 뿐, Flask 로그의 `Background Update`·`init_data`·`KRX 로그인` 줄 0. 통과

## 정리
- 실제: agent-browser 두 세션 닫음, 사본 gunicorn(58101)·Next dev(58102) 종료 뒤 58101·58102·3500·5501 리스너 0·사본 경로 프로세스 0. 사본 둘(`q102old`·`q102new`)과 더미 세션 토큰 파일을 리터럴 경로로 지우고 없음 확인. 원본 `data/update_status.json` 수정 시각(1777948277) 그대로, 저장소 루트 `node_modules` 없음. 원본 `.env` 는 읽지 않았고 더미 비밀은 사본 프로세스 환경 변수로만 줬다. 결과: 필수 4/4 통과
