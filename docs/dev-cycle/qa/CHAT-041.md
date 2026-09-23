# [CHAT-041] 삭제한 대화가 레거시 JSON 스냅샷에 남는 창 — QA 시나리오

- 대상: `git archive` 로 만든 코드 사본 두 개. 기준은 `ee6acc3`(변경 전), 검증은 첫 커밋(아래 「검증 기준 커밋」)이다. 사본마다 scratchpad 의 하네스 `chat041/qa_harness.py` 를 실행한다
- 구성 근거: 승인 범위(TODO `[CHAT-041]` 「설계 승인」「승인 범위」)와 코드 리뷰 반영분. 하네스는 `app/routes/kr_market_user_data_routes.py` 의 `delete_user_data` 를 실제 `HistoryManager` 로 부르고, 챗봇 메모리·모의투자·사용량은 참을 돌려주는 가짜로 둔다. 워커 둘은 같은 디렉터리를 보는 `HistoryManager` 인스턴스 둘로, 겹친 스냅샷 쓰기는 스레드 둘로 흉내 낸다. 모든 자료는 `tempfile` 아래에 만들어 원본 `data/` 를 읽지 않는다
- 브라우저 적용 여부(browser_applicability): not-applicable(정책상 차단). 사용자 진입은 계정 설정의 「내 기록 삭제」로 되돌릴 수 없는 삭제 계열 조작이고, 결함 조건(디스크 쓰기 실패, 워커 사이 경합)은 브라우저에서 만들 수 없다. `closing-bet-verify` 의 서비스 하네스 등급으로 라우트 함수를 직접 부른다
- QA 엔진(engine): Claude Code, 서비스 하네스. 원본 3500/5501·live 주소·원본 `.env`·원본 `data/` 는 쓰지 않는다
- 금지 조작: 원본 데이터 삭제, 서버 기동, 원본 파일 쓰기
- 검증 기준 커밋:
- 구성 2026-09-23(첫 커밋 전) | 실행:
- 단계(phase): 시나리오 구성 완료 | 실행 대기
- 반복(iteration): 0
- 결과:
- 증거:
- 정리(cleanup):
- 필수 여부(required): 예
- 읽은 정본: `.claude/skills/closing-bet-python/SKILL.md`, `.claude/skills/closing-bet-verify/SKILL.md`

## 시나리오

### S-1. 사본 정리에 실패한 삭제를 다른 워커의 재시도가 정리한다 (핵심)
- 조작: alice·bob 세션과 사본이 있는 상태에서 스냅샷 쓰기와 `unlink` 가 모두 실패하게 하고 `delete_user_data` 를 부른다. 쓰기를 되돌린 뒤, 간격이 아직 차지 않은 다른 워커 인스턴스로 같은 삭제를 다시 부르고 JSON 의 소유자 목록을 읽는다.
- 기대: 두 사본 모두 첫 호출은 `500`·`failed=['chat_sessions']`. 검증 사본의 재시도는 `200`·`chat_sessions=0` 이고 JSON 소유자는 `['bob@example.test']`. 기준 사본은 재시도가 `200`·0 인데 JSON 에 alice 가 남아 결함이 재현된다.
- 필수 여부(required): 예
- 실제:
- 결과:

### S-2. 다른 워커의 낡은 메모리가 지운 세션을 JSON 에 되살리지 않는다 (핵심)
- 조작: 워커 B 를 먼저 만든 뒤 워커 A 로 alice 를 지우고, B 가 재적재 없이 bob 세션을 저장하게 한다(간격이 찬 상태).
- 기대: 검증 사본은 `b_save=True`, JSON 소유자 `['bob@example.test']`. 기준 사본은 JSON 에 alice 가 되살아난다.
- 필수 여부(required): 예
- 실제:
- 결과:

### S-3. 기동 때 사본 쓰기가 실패해도 생성된다 (경계)
- 조작: 스냅샷 쓰기가 `OSError(28)` 를 내게 하고 `HistoryManager` 를 새로 만든다.
- 기대: 검증 사본은 `('ok', 1)`. 기준 사본은 `('error', 'OSError')`.
- 필수 여부(required): 예
- 실제:
- 결과:

### S-4. 겹친 스냅샷 쓰기가 직렬화된다 (경계)
- 조작: 첫 쓰기가 정본을 읽는 중에 멈춰 있는 동안 두 번째 쓰기를 시작한다.
- 기대: 검증 사본은 `second_blocked=True`, 최종 파일 `{'fresh': {}}`. 기준 사본은 `sync` 가 콜백을 받지 않아 `TypeError` 로 끝난다(인터페이스 변경 확인용이며 기준의 결함 재현은 S-2 가 맡는다).
- 필수 여부(required): 예
- 실제:
- 결과:

### S-5. 장애가 없으면 변경 전과 같다 (회귀)
- 조작: 장애 없이 alice 를 지운다.
- 기대: 두 사본의 응답 dict·남은 소유자·JSON 소유자가 같다.
- 필수 여부(required): 예
- 실제:
- 결과:

### S-6. 정리 (인접)
- 조작: 사본 경로의 프로세스를 조회하고 사본과 `qa-chat041-*` 임시 디렉터리를 지운다. 원본 `data/`·`logs/` 에서 수정 시각이 바뀐 파일을 센다.
- 기대: 남은 프로세스 0, 사본·임시 디렉터리 삭제, 원본 변화 0, 작업 트리 변화 없음.
- 필수 여부(required): 예
- 실제:
- 결과:
