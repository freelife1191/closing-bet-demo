# [INFRA-100] 데이터 상태 화면의 중복 시작을 409 「업데이트 중복」으로 맞춘다 — QA 기록

- 대상: `app/routes/common_update_routes.py` 의 `api_start_update`(중복 시작 400 → 409), `frontend/src/app/dashboard/data-status/page.tsx` 의 `handleUpdateAll`(409 면 「업데이트 중복」 모달, 개별 업데이트와 상수 `DUPLICATE_UPDATE_MODAL` 공용)
- 단계(phase): 시나리오 구성 완료 | 실행 대기
- 구성 2026-09-24 23:36
- 검증 기준 커밋: 이 문서를 담은 첫 커밋. 대조는 수정 전 커밋 `8c59e59`. 사본은 각 커밋의 `git archive` 다
- 구성 근거: 설계 승인(대화 23:28), 호출 경로(데이터 상태 화면의 「업데이트」·「전체 데이터 업데이트」 → `fetchAPI('/api/system/start-update')` → Next rewrite → Flask `api_start_update`), 화면 폴링 규칙(마운트 때 `update-status` 를 한 번 읽고 실행 중일 때만 폴링하므로, 화면을 연 뒤 상태 파일을 실행 중으로 바꾸면 버튼이 활성인 채로 중복 시작을 보낼 수 있다)
- QA 엔진(engine): Claude Code. browser_applicability: required(browser_driver: agent-browser). 사용자가 보는 것은 모달이다
- 격리: 각 커밋의 `git archive` 사본에서 `secrets/`·`data/`·`.env` 를 지우고 빈 `data/` 를 만든다. 사본 Flask 는 gunicorn 1 worker·`SCHEDULER_ENABLED=false`, 사본 Next 는 `API_URL` 을 사본 Flask 로 둔다. 관리자 화면은 `[VCP-031]`·`[VCP-046]` 과 같이 더미 `NEXTAUTH_SECRET`·`INTERNAL_IDENTITY_SECRET`·`ADMIN_EMAILS=qa-admin@example.com` 을 환경 변수로만 주고, 같은 더미 비밀로 `next-auth/jwt` 의 `encode` 가 만든 세션 토큰을 `next-auth.session-token` 쿠키로 넣는다. 원본 3500·5501·`data/`·`.env`·운영 주소는 쓰지 않는다
- 안전: 시작 요청은 상태 파일이 `isRunning: true` 일 때만 보낸다. 그러면 라우트가 `start_update` 와 스레드 기동 전에 409 로 거부하므로 수집·LLM·KRX 로그인이 일어나지 않는다. 각 클릭 전에 상태 파일이 실행 중인지 다시 읽어 확인한다
- 금지: 상태 파일이 실행 중이 아닐 때의 업데이트 클릭, 중지 버튼, 메시지 발송, 설정 저장, Refresh, AI 재분석, 챗봇 전송, 모의 매수
- 필수 여부(required): S-1~S-3 예
- 이전 기록과의 관계: `qa/INFRA-099.md`·`docs/superpowers/plans/2026-09-24-infra-099-reject-local-restart.md` 의 「400 "Already running"」은 그 시점 기록이며, 이 항목에서 409 로 바뀌었다(리뷰 L-1)

## 시나리오

### S-1. 개별 「업데이트」의 중복 시작이 「업데이트 중복」 모달로 보인다 (브라우저, 필수)
- 조작: 관리자 세션으로 `/dashboard/data-status` 를 연다(상태 파일 `isRunning: false`). 사본 상태 파일을 `isRunning: true` 로 바꾼 뒤 첫 카드의 「업데이트」를 누른다
- 기대: 수정 뒤는 `POST /api/system/start-update` 409, 모달 제목 「업데이트 중복」과 본문 「이미 다른 업데이트가 진행 중입니다」. 수정 전(`8c59e59`)은 400 이고 모달이 뜨지 않는다(콘솔 오류만)
- 실제:

### S-2. 「전체 데이터 업데이트」의 중복 시작이 영어 문구 대신 「업데이트 중복」 모달로 보인다 (브라우저, 필수)
- 조작: S-1 모달을 「확인」으로 닫고, 상태 파일이 여전히 실행 중인지 확인한 뒤 「전체 데이터 업데이트」를 누른다
- 기대: 수정 뒤는 409, 모달 「업데이트 중복」, 화면에 「Already running」·「업데이트 오류」 없음, 버튼이 다시 「전체 데이터 업데이트」로 돌아옴. 수정 전은 400, 모달 「업데이트 오류」·본문 「Already running」
- 실제:

### S-3. 거부된 시작은 상태와 자료를 바꾸지 않는다 (필수)
- 조작: S-1·S-2 뒤 사본 상태 파일과 `data/` 목록, 사본 Flask 로그를 읽는다
- 기대: 상태 파일은 QA 가 쓴 내용 그대로(`startTime`·`items` 불변), `data/` 에 수집 산출물 없음, 로그에 파이프라인 시작 줄 없음
- 실제:

## 정리
- 실제:
