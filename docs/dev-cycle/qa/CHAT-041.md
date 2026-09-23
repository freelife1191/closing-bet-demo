# [CHAT-041] 삭제한 대화가 레거시 JSON 스냅샷에 남는 창 — QA 시나리오

- 대상: `git archive` 로 만든 코드 사본 두 개. 기준은 `ee6acc3`(변경 전), 검증은 첫 커밋(아래 「검증 기준 커밋」)이다. 사본마다 scratchpad 의 하네스 `chat041/qa_harness.py` 를 실행한다
- 구성 근거: 승인 범위(TODO `[CHAT-041]` 「설계 승인」「승인 범위」)와 코드 리뷰 반영분. 하네스는 `app/routes/kr_market_user_data_routes.py` 의 `delete_user_data` 를 실제 `HistoryManager` 로 부르고, 챗봇 메모리·모의투자·사용량은 참을 돌려주는 가짜로 둔다. 워커 둘은 같은 디렉터리를 보는 `HistoryManager` 인스턴스 둘로, 겹친 스냅샷 쓰기는 스레드 둘로 흉내 낸다. 모든 자료는 `tempfile` 아래에 만들어 원본 `data/` 를 읽지 않는다
- 브라우저 적용 여부(browser_applicability): not-applicable(정책상 차단). 사용자 진입은 계정 설정의 「내 기록 삭제」로 되돌릴 수 없는 삭제 계열 조작이고, 결함 조건(디스크 쓰기 실패, 워커 사이 경합)은 브라우저에서 만들 수 없다. `closing-bet-verify` 의 서비스 하네스 등급으로 라우트 함수를 직접 부른다
- QA 엔진(engine): Claude Code, 서비스 하네스. 원본 3500/5501·live 주소·원본 `.env`·원본 `data/` 는 쓰지 않는다
- 금지 조작: 원본 데이터 삭제, 서버 기동, 원본 파일 쓰기
- 검증 기준 커밋: `a3bdbee`(첫 커밋, 사본은 `git archive a3bdbeee`). 사본의 `chatbot/storage.py`·`chatbot/storage_history_parts.py` 가 원본 작업 트리와 바이트 단위로 같음을 `cmp` 로 확인했다. 하네스는 원본 `venv/bin/python` 을 `env -i` 로 실행했다
- 구성 2026-09-23(첫 커밋 전) | 실행 21:10(기준·검증 사본, 하네스 수정 두 번 뒤 세 번째 실행이 증거)·21:11(정리)
- 단계(phase): 시나리오 구성 완료 | 실행 완료
- 반복(iteration): 1(제품 코드 수정 없음). 하네스만 두 번 고쳤다: S-4 가 기준 사본의 `FileNotFoundError` 를 잡지 못해 `except Exception` 으로 넓혔고, S-1 의 재시도 워커를 첫 삭제 뒤에 새로 만들면 기동 시 `_load` 의 강제 스냅샷이 JSON 을 다시 써 결함 조건을 지우므로 첫 삭제 전에 떠 있던 워커로 바꿨다
- 결과: 통과 (필수 6/6)
- 증거: 각 시나리오의 「실제」 줄(하네스 표준 출력 원문), 하네스 scratchpad `chat041/qa_harness.py`
- 정리(cleanup): 사본 경로 프로세스 0, `qa-chat041/`(두 사본) 삭제, `qa-chat041-*` 임시 디렉터리 삭제 후 0개(`env -i` 로 TMPDIR 이 없어 `/tmp` 아래에 생겼다), 원본 `data/`·`logs/` 에서 20:59(설계 승인) 이후 수정된 파일 0개, 작업 트리 변화 없음. 서버를 띄우지 않았다
- 필수 여부(required): 예
- 읽은 정본: `.claude/skills/closing-bet-python/SKILL.md`, `.claude/skills/closing-bet-verify/SKILL.md`

## 시나리오

### S-1. 사본 정리에 실패한 삭제를 다른 워커의 재시도가 정리한다 (핵심)
- 조작: alice·bob 세션과 사본이 있는 상태에서 스냅샷 쓰기와 `unlink` 가 모두 실패하게 하고 `delete_user_data` 를 부른다. 쓰기를 되돌린 뒤, 간격이 아직 차지 않은 다른 워커 인스턴스로 같은 삭제를 다시 부르고 JSON 의 소유자 목록을 읽는다.
- 기대: 두 사본 모두 첫 호출은 `500`·`failed=['chat_sessions']`. 검증 사본의 재시도는 `200`·`chat_sessions=0` 이고 JSON 소유자는 `['bob@example.test']`. 기준 사본은 재시도가 `200`·0 인데 JSON 에 alice 가 남아 결함이 재현된다.
- 필수 여부(required): 예
- 실제: 검증 `first=500 ['chat_sessions'] retry=200 0 json_owners=['bob@example.test']`. 기준 `first=500 ['chat_sessions'] retry=200 0 json_owners=['alice@example.test', 'bob@example.test']` 로, 재시도가 성공을 돌려준 뒤에도 지운 대화가 JSON 에 남는 결함이 재현되었다
- 결과: 통과

### S-2. 다른 워커의 낡은 메모리가 지운 세션을 JSON 에 되살리지 않는다 (핵심)
- 조작: 워커 B 를 먼저 만든 뒤 워커 A 로 alice 를 지우고, B 가 재적재 없이 bob 세션을 저장하게 한다(간격이 찬 상태).
- 기대: 검증 사본은 `b_save=True`, JSON 소유자 `['bob@example.test']`. 기준 사본은 JSON 에 alice 가 되살아난다.
- 필수 여부(required): 예
- 실제: 검증 `delete=200 b_save=True json_owners=['bob@example.test']`. 기준 `delete=200 b_save=True json_owners=['alice@example.test', 'bob@example.test']` 로 지운 세션이 JSON 에 되살아났다
- 결과: 통과

### S-3. 기동 때 사본 쓰기가 실패해도 생성된다 (경계)
- 조작: 스냅샷 쓰기가 `OSError(28)` 를 내게 하고 `HistoryManager` 를 새로 만든다.
- 기대: 검증 사본은 `('ok', 1)`. 기준 사본은 `('error', 'OSError')`.
- 필수 여부(required): 예
- 실제: 검증 `('ok', 1)`. 기준 `('error', 'OSError')`
- 결과: 통과

### S-4. 겹친 스냅샷 쓰기가 직렬화된다 (경계)
- 조작: 첫 쓰기가 정본을 읽는 중에 멈춰 있는 동안 두 번째 쓰기를 시작한다.
- 기대: 검증 사본은 `second_blocked=True`, 최종 파일 `{'fresh': {}}`. 기준 사본은 `sync` 가 콜백을 받지 않아 `TypeError` 로 끝난다(인터페이스 변경 확인용이며 기준의 결함 재현은 S-2 가 맡는다).
- 필수 여부(required): 예
- 실제: 검증 `second_blocked=True final={'fresh': {}}`. 기준은 스레드 안에서 `TypeError: Object of type function is not JSON serializable` 뒤 `error=FileNotFoundError`(콜백을 받지 않는 종전 인터페이스)
- 결과: 통과

### S-5. 장애가 없으면 변경 전과 같다 (회귀)
- 조작: 장애 없이 alice 를 지운다.
- 기대: 두 사본의 응답 dict·남은 소유자·JSON 소유자가 같다.
- 필수 여부(required): 예
- 실제: 두 사본 모두 `200 {'status': 'deleted', 'deleted': {'chat_sessions': 1, 'chat_memories': True, 'paper_trading': True, 'usage': True}} owners=['bob@example.test'] json_owners=['bob@example.test']` 로 같다
- 결과: 통과

### S-6. 정리 (인접)
- 조작: 사본 경로의 프로세스를 조회하고 사본과 `qa-chat041-*` 임시 디렉터리를 지운다. 원본 `data/`·`logs/` 에서 수정 시각이 바뀐 파일을 센다.
- 기대: 남은 프로세스 0, 사본·임시 디렉터리 삭제, 원본 변화 0, 작업 트리 변화 없음.
- 필수 여부(required): 예
- 실제: `pgrep -f qa-chat041` 0건, 사본 삭제, `find /tmp/ /private/tmp/ /private/var/folders -maxdepth 4 -name 'qa-chat041-*'` 삭제 후 0건, `find data logs -newermt '2026-09-23 20:59' -type f` 0건, `git status --short` 는 비어 있음
- 결과: 통과
