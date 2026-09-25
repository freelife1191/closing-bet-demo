# [INFRA-103] 데이터 상태 화면의 진행 폴링이 조회 오류에도 멈추지 않는 문제 — QA 기록

- 대상: `frontend/src/app/dashboard/data-status/page.tsx` 의 `pollUpdateStatus`(연속 3회 실패 시 interval 정지·진행 표시 해제·「업데이트 오류」 모달, 성공 시 실패 횟수 초기화, 앞선 조회가 끝나지 않았으면 tick 건너뜀)
- 단계(phase): 완료 | 시나리오 구성 완료 | 실행 완료
- 구성 2026-09-25 09:34 | 실행 2026-09-25 09:38:21~09:39:27(수정 전), 09:39:47~09:40:54(수정 뒤)
- 검증 기준 커밋: `4a4779bc`(이 문서를 담은 첫 커밋). 대조는 수정 전 커밋 `9375762f`. 사본은 각 커밋의 `git archive` 다
- 구성 근거: 설계 승인(대화 09:32), 호출 경로(마운트 `pollUpdateStatus()` 1회 → 실행 중이면 `startPolling()` 500ms interval → `fetchAPI('/api/system/update-status', 30초)` → Next rewrite → Flask `get_update_status`(상태 파일 읽기만))
- QA 엔진(engine): Claude Code. browser_applicability: required(browser_driver: agent-browser). 사용자가 보는 것은 진행 표시와 모달이고, 요청 수는 agent-browser 네트워크 기록으로 센다
- 격리: `[INFRA-102]` 와 같다. 각 커밋의 `git archive` 사본에서 `secrets/`·`data/`·`.env` 를 지우고 빈 `data/` 를 만든다. 사본 Flask 는 gunicorn 1 worker·`SCHEDULER_ENABLED=false`(58101), 사본 Next dev(58102)는 `API_URL` 을 사본 Flask 로 둔다. 더미 `NEXTAUTH_SECRET`·`INTERNAL_IDENTITY_SECRET`·`ADMIN_EMAILS=qa-admin@example.com` 을 환경 변수로만 주고 같은 더미 비밀로 만든 세션 토큰을 쿠키로 넣는다. 원본 3500·5501·`data/`·`.env`·운영 주소는 쓰지 않는다
- 안전: 실행 중 표시는 사본 상태 파일에 `isRunning: true` 를 써서 만든다. S-3 의 「업데이트」 클릭은 상태 파일이 실행 중일 때만 하므로 409 로 거부되어 수집·LLM·KRX 로그인이 일어나지 않는다
- 금지: 상태 파일이 실행 중이 아닐 때의 시작 클릭, 중지 버튼, 메시지 발송, 설정 저장, Refresh, AI 재분석, 챗봇 전송, 모의 매수
- 필수 여부(required): S-1~S-4 예
- 실행: 세션 스크래치의 `infra103qa_run.sh <사본> <표식>`(agent-browser `--namespace infra103qa`, 사본 gunicorn 58101·Next dev 58102, 두 사본을 차례로). 사본 `page.tsx` 의 `INFRA-103` 표시는 수정 전 0건·수정 뒤 3건으로 서로 다른 커밋임을 확인
- 반복(iteration): 1회(수정 전 사본의 첫 시도 09:37:07 은 세션 토큰 파일이 없어 비관리자로 돌았고 S-2 계수가 끝나지 않은 요청을 세지 못해 무효. 토큰을 같은 더미 비밀로 다시 만들고 S-2 를 페이지 `fetch` 호출 계수로 바꿔 다시 실행했다. 수정 뒤 사본은 고친 스크립트로만 실행)
- 결과: 통과 (필수 4/4)
- 증거: 아래 「실제」 줄(스크립트 출력 원문, scratchpad `qa-infra103-{old,new}-run.txt`), 스크린샷 `infra103qa-new-s1.png`(열어 확인: 「업데이트 오류」 모달과 멈춤 문구)과 `infra103qa-{old,new}-s{1,3}.png`(세션 임시), 두 실행 모두 스크립트 exit 0

## 시나리오

### S-1. 실행 중에 백엔드가 멈추면 폴링이 멈추고 「업데이트 오류」 모달이 보인다 (브라우저, 필수)
- 조작: 상태 파일을 실행 중으로 두고 화면을 연다. 진행 표시 「Daily Prices 업데이트 중...」을 확인한 뒤 사본 Flask 를 멈춘다. 4초 뒤와 그 뒤 3초 동안의 `update-status` 요청 수를 센다
- 기대: 수정 뒤 모달 「업데이트 오류」와 「진행 상황을 확인하지 못해 자동 확인을 멈췄습니다」 문구, 진행 표시 없음, 이후 3초 동안 요청 증가 0. 수정 전은 모달 없이 진행 표시가 남고 요청이 계속 는다(결함 재현)
- 실제: 수정 뒤(09:40:17) 진행표시 1 → Flask 정지 4초 뒤 진행표시 0·「업데이트 오류」 1·멈춤 문구 1, 요청 기록 2건, 이후 3초 증가 0. 콘솔의 폴링 실패 3건. 수정 전(09:38:51) 4초 뒤에도 진행표시 1·오류 0, 요청 8건에서 3초 뒤 14건(증가 6, 결함 재현). 통과

### S-2. 백엔드가 응답하지 않는 동안 조회가 겹쳐 쌓이지 않는다 (브라우저, 필수)
- 조작: 실행 중 상태에서 사본 gunicorn 에 SIGSTOP 을 보내 응답을 멈춘다. 5초 동안 보낸 `update-status` 요청 수를 센 뒤 SIGCONT 로 되살린다
- 기대: 수정 뒤 5초 동안 새 요청 1건 이하. 수정 전은 500ms 마다 새 요청이 나가 약 10건(결함 재현)
- 실제: 수정 뒤 SIGSTOP 5초 동안 `update-status` fetch 호출 1건. 수정 전 같은 조작에서 10건(결함 재현). 두 사본 모두 SIGCONT 뒤 상태를 실행 중 아님으로 바꾸자 진행표시 0. 통과

### S-3. 폴링이 멈춘 뒤 백엔드가 살아나면 시작이 409 로 거부되고 진행 표시가 다시 붙는다 (브라우저, 필수)
- 조작: S-1 뒤 모달을 닫고 사본 Flask 를 다시 띄워 상태 파일을 실행 중으로 쓴다. 카드의 「업데이트」를 누른다
- 기대: 「업데이트 중복」 모달, 닫은 뒤 진행 표시 「Daily Prices 업데이트 중...」이 다시 보인다(`[INFRA-102]` 경로). 시작 요청은 409
- 실제: 수정 뒤 모달을 닫고 Flask 를 다시 띄워 상태 파일을 실행 중으로 쓴 뒤 「업데이트」 클릭 → 「업데이트 중복」 1, `POST /api/system/start-update` 409 한 건, 닫은 뒤 진행표시 1(폴링이 다시 붙음). 수정 전도 같은 결과(폴링이 멈추지 않았으므로). 통과

### S-4. 이 QA 가 상태와 자료를 바꾸지 않는다 (필수)
- 기대: 사본 `data/` 에 하네스가 쓴 상태 파일 말고 새 자료가 없고, Flask 로그에 수집·KRX 로그인 줄이 없다. 원본 `data/`·3500·5501 은 건드리지 않는다
- 실제: 두 사본 모두 상태 파일 해시가 클릭 전후 `5ab555f066dd` 로 같고, 사본 `data/` 에는 서버 기동이 만든 `runtime_cache.db`·`scheduler_runtime_status.json`·`v2_screener_status.json`·`vcp_status.json` 과 하네스의 `update_status.json` 만 있다. Flask 로그의 수집·`init_data`·KRX 로그인 줄 0. 통과

## 정리
- 실제: agent-browser 세션 둘 닫음, 사본 Next·gunicorn 정지 뒤 58101·58102 수신 0, 사본 둘(`q103old`·`q103new`) 리터럴 경로로 삭제 뒤 없음 확인, 사본 경로 프로세스 0. 원본 `data/kr_ai_analysis.json`(1788316016)·`signals_log.csv`(1789994506)·`update_status.json`(1777948277) 수정 시각 그대로. 원본 3500·5501·운영 주소 사용 없음. 결과: 필수 4/4 통과
