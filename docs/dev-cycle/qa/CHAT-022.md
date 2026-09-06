# [CHAT-022] 메모리 전체 동기화가 다른 워커가 저장한 행을 지운다 — QA 시나리오

- 대상: API 하네스 `POST http://localhost:5501/api/kr/chatbot` (gunicorn 워커 2개) + 화면
  http://localhost:3500/chatbot, http://localhost:3500/dashboard/kr
- 구성 근거: `/qa-only` 리포트 (`.gstack/qa-reports/qa-report-localhost-3500-2026-09-07.md`)
  + 이번 사이클의 변경 두 파일(`chatbot/storage_memory_manager.py`, `chatbot/storage_sqlite_memory.py`)
- 구성 2026-09-07 06:52 | 실행 2026-09-07 06:55
- QA 엔진(engine): Claude Code `/qa-only` → `/qa`
- 단계(phase): 시나리오 구성 완료 | 실행 완료
- 반복(iteration): 1회
- baseline 상태: 기준값 수집 완료 (아래 「기준값」)
- 필수 여부(required): 예
- 결과: 통과 (필수 5 / 5)
- 증거: 아래 시나리오별 기록의 접근 로그·응답·DB 조회 발췌. `/qa-only` 관찰은
  `.gstack/qa-reports/qa-report-localhost-3500-2026-09-07.md`
- 정리(cleanup): 시험 신원의 세션 1건과 메모리 1행을 `/clear all` 로 제거해 DB 가 기준값(공용 2행)으로
  돌아옴. QA 를 위해 띄운 gunicorn(마스터 16692)과 Next dev(96887)는 마감 뒤 종료. 잔여물: 시험 신원
  `qa-chat022@example.test` 의 무료 사용량 카운터 10/10, `logs/gunicorn-access.log`(git 추적 밖)

## 화면이 아니라 API 하네스를 검사 대상으로 삼는 이유

바뀐 것은 `MemoryManager` 의 재적재와 저장 폴백이며, 그 경로는 `/memory` 슬래시 명령과 채팅
프롬프트 조립에서만 실행된다. `/qa-only` 관찰에서 `/chatbot` 초기 로드는
`/api/kr/chatbot/models`·`/sessions`·`/api/kr/user/quota` 만 부르고 메모리 경로에 닿지 않았다.
브라우저에서 슬래시 명령을 보내면 실제 사용자 신원의 무료 사용량이 차감되고 히스토리에 남으므로
(`AGENTS.md` 「되돌릴 수 없는 조작」), 전용 시험 신원으로 API 를 직접 부른다.
`/memory` 명령은 LLM 을 부르지 않는다(`_execute_command` 가 프롬프트 조립 전에 응답을 돌려준다).

**하네스 규약**

- 헤더: `X-User-Email: qa-chat022@example.test`, `X-Session-Id: qa-chat022-session`,
  `Accept: text/event-stream`, `Content-Type: application/json`
- 본문: `{"message": "<명령>", "session_id": <첫 응답이 돌려준 session_id, 첫 호출은 생략>}`
- 응답: SSE. `data:` 이벤트의 `chunk` 가 명령 응답 문자열이다.
- 어느 워커가 처리했는지는 `logs/gunicorn-access.log` 의 첫 열 `<PID>` 로 읽는다
  (`--access-logformat '%(p)s ...'`). 이번 QA 를 위해 gunicorn 을 이 옵션으로 기동했고, 나머지
  옵션은 `restart_all.sh` 와 같다(`--workers 2 --threads 8 --timeout 120`).
- 시험 신원의 무료 사용량 상한은 10회이며 `/memory` 명령마다 1회 차감된다(`[CHAT-008]` 의 알려진
  동작). 시나리오 전체가 10회 안에 끝나도록 짰다. 재시도가 필요하면 두 번째 신원
  `qa-chat022-b@example.test` 로 같은 절차를 처음부터 다시 한다.
- 금융 앱의 비용·상태 변경 조작은 하지 않는다. LLM 호출 없음, 실제 사용자 데이터 변경 없음.

## 기준값 (2026-09-07 06:47, `data/chatbot_storage.db` 읽기 전용 조회)

- `chatbot_memories`: 소유자 1개(공용 `''`), 총 2행. 시험 신원 행 0.
- `chatbot_sessions`: 시험 신원 소유 세션 0.
- gunicorn: 마스터 16692 (06:51:17 기동, 접근 로그 옵션 포함). 리뷰 반영 뒤 06:54:22 에 `kill -HUP` 으로
  워커를 54161·54173 으로 다시 띄웠다(코드 최종 수정 시각 06:54 이전 → 이후 기동 확인).

## 시나리오

### S-1. 한 워커에서 저장한 메모리가 두 워커 모두의 조회에 보인다 (회귀)
- 조작: `/memory add 보유종목 삼성전자` 를 1회 보낸다. 이어서 `/memory view` 를 2개씩 동시에
  4묶음, 총 8회 보낸다. 접근 로그에서 각 요청을 처리한 워커 PID 를 읽는다.
- 기대: add 응답 `✅ 메모리 저장: 보유종목 = 삼성전자`. view 응답 8건 모두에
  `` - `보유종목`: 삼성전자 `` 가 있다. view 를 처리한 워커 PID 집합에 54161 과 54173 이 모두
  들어 있고, add 를 처리한 워커가 아닌 워커의 view 응답에도 같은 값이 있다. 종전 코드라면
  add 를 처리하지 않은 워커의 응답이 `📭 저장된 메모리가 없습니다.` 였다.
- 필수 여부(required): 예
- PID 집합에 한 워커만 있으면 판정할 수 없으므로 두 번째 신원으로 S-1 을 다시 한다.
- 실제: add 응답 `✅ 메모리 저장: 보유종목 = 삼성전자`, 처리 워커 54161. view 8건 모두
  `🧠 **저장된 메모리**\n- \`보유종목\`: 삼성전자`. 처리 워커는 54161 이 4건, 54173 이 4건이다.
  두 번째 신원은 필요하지 않았다.
- 결과: 통과
- 증거: `logs/gunicorn-access.log` 06:55:37 의 `POST /api/kr/chatbot` 9줄 (`<54161>` 5줄 = add 1 +
  view 4, `<54173>` 4줄 = view 4, 전부 200). 하네스 출력 `view1a`~`view4b` 각 `보유종목` 1회 일치.
- 정리(cleanup): S-3 에서 함께 정리

### S-2. 시험 신원의 저장이 공용 메모리 행을 지우지 않는다 (회귀)
- 조작: S-1 이 끝난 뒤 `data/chatbot_storage.db` 를 읽기 전용으로 열어 `chatbot_memories` 를
  소유자별로 센다.
- 기대: 공용 `''` 2행이 기준값과 같은 키로 그대로 있고, `qa-chat022@example.test` 1행
  (`보유종목`) 이 추가되어 총 3행이다. 종전 코드에서는 단건 upsert 실패 시 폴백이 스냅샷 밖의
  행을 지웠으므로, 이 검사는 실패 폴백이 사라졌다는 사실이 아니라 정상 경로에서 다른 소유자
  행이 보존된다는 사실을 고정한다. 실패 폴백 자체는 pytest
  `test_failed_single_save_does_not_delete_other_workers_rows` 가 검사한다.
- 필수 여부(required): 예
- 실제: 총 3행. 공용 `''` 키 `daily_suggestions_default_empty`·`interest` 2행 그대로, 시험 신원
  `보유종목` 1행. 다른 소유자 없음. 시험 신원 세션 1건.
- 결과: 통과
- 증거: `sqlite3.connect("file:data/chatbot_storage.db?mode=ro", uri=True)` 읽기 전용 조회 출력
  (`total rows: 3 | public keys: ['daily_suggestions_default_empty', 'interest'] | qa keys: ['보유종목']`)
- 정리(cleanup): S-3 에서 함께 정리

### S-3. `/clear all` 이 시험 신원의 메모리와 대화만 지운다 (인접·정리)
- 조작: `/clear all` 을 1회 보낸다. 접근 로그에서 처리한 워커 PID 를 읽는다. DB 를 읽기 전용으로
  다시 센다.
- 기대: 응답 `🧹 내 대화 1건과 메모리, 데이터 캐시를 초기화했습니다.` (세션 id 를 이어 썼으므로
  대화는 1건). `chatbot_memories` 는 공용 2행만 남아 기준값과 같고, `chatbot_sessions` 에 시험
  신원 소유 세션이 0. 시험 신원의 무료 사용량 카운터(10회 중 10회 사용)는 남는다. 이 값은 API 로
  되돌릴 수 없으며 시험 신원에만 속하므로 잔여물로 기록한다.
- 필수 여부(required): 예
- 실제: 응답 `🧹 내 대화 1건과 메모리, 데이터 캐시를 초기화했습니다.`, 처리 워커 54173 (add 를
  처리한 54161 이 아닌 워커). 조회 결과 총 2행(공용 2행, 키 동일), 시험 신원 세션 0.
- 결과: 통과
- 증거: `logs/gunicorn-access.log` 06:55:55 `<54173> "POST /api/kr/chatbot" 200`, 읽기 전용 조회 출력
  (`after clear total rows: 2 | owners: [''] | qa sessions after clear: 0`)
- 정리(cleanup): 이 시나리오가 정리 자체다. 시험 신원의 세션·메모리 0. 무료 사용량 카운터 10/10 은 잔여

### S-4. 백엔드 로그에 메모리 저장·적재 실패가 없다 (인접)
- 조작: S-1 부터 S-3 까지 마친 뒤 `logs/backend.log` 에서 `Failed to load chatbot memories`,
  `Failed to save chatbot memories`, `SQLite single memory upsert failed`,
  `SQLite memory delete failed`, `SQLite memory clear failed` 를 찾는다.
- 기대: 다섯 문구 모두 0건. `[QUOTA]` 로그의 `usage_key=qa-chat022@example.test` 줄은 명령
  수(10)만큼 있다.
- 필수 여부(required): 예
- 실제: 다섯 문구 모두 0건. `usage_key=qa-chat022@example.test` 10줄. 06:55 이후 ERROR 레벨 0줄.
- 결과: 통과
- 증거: `grep -c` 출력 (`logs/backend.log`)
- 정리(cleanup): 이 시나리오가 소유한 임시 자료 없음

### S-5. 화면 두 곳이 콘솔 오류 없이 뜬다 (리포트)
- 조작: 콘솔 버퍼를 비운 뒤 `/chatbot` 을 열어 헤딩과 콘솔을 읽고, `/dashboard/kr` 을 열어
  콘솔을 읽는다. 아무 버튼도 누르지 않는다.
- 기대: `/chatbot` 헤딩 `안녕하세요, 흑기사님`, 두 화면 모두 콘솔 오류 0건. `/qa-only` 관찰과
  같다.
- 필수 여부(required): 예
- 실제: `/chatbot` 200, `h1` `안녕하세요, 흑기사님`, 콘솔 오류 0건. `/dashboard/kr` 200, 콘솔 오류 0건.
- 결과: 통과
- 증거: browse `console --errors` 출력 `(no console errors)` 두 화면. 스크린샷
  `.gstack/qa-reports/screenshots/chat022-chatbot-initial.png`, `chat022-dashboard.png`
- 정리(cleanup): 이 시나리오가 소유한 임시 자료 없음

## 실행 결과

- 필수 시나리오: 통과 5 / 전체 5
- 미통과 필수: 없음
- 재개 판정: 완료 가능
- 시나리오 밖에서 새로 발견: 없음
- 검사한 커밋: `d990650`
- `/qa` 가 만든 수정 커밋: 없음 (소스 코드를 한 줄도 바꾸지 않음)
