# [CHAT-040] 스냅샷 쓰기 실패와 대화 삭제 — QA 시나리오

- 대상: `git archive` 로 만든 코드 사본 두 개. 기준은 `caa4d7a`(변경 전)이고, 검증 대상은 첫 커밋(아래 「검증 기준 커밋」)이다. 사본마다 scratchpad 의 하네스 `chat040/qa_harness.py` 를 `env -i` 로 실행한다
- 구성 근거: 승인 범위(TODO `[CHAT-040]` 「설계 승인」「승인 범위 변경」)와 코드 리뷰 low1 반영. 하네스는 `app/routes/kr_market_user_data_routes.py` 의 `delete_user_data` 를 실제 `HistoryManager` 로 부르고, 챗봇 메모리·모의투자·사용량은 참을 돌려주는 가짜로 둔다. 모든 자료는 `tempfile` 아래에 만들므로 원본 `data/` 를 읽지 않는다
- 브라우저 적용 여부(browser_applicability): not-applicable(정책상 차단). 이 흐름의 사용자 진입은 계정 설정의 「내 기록 삭제」인데 되돌릴 수 없는 삭제 계열 조작이고, 결함 조건(디스크 쓰기 실패)은 브라우저에서 만들 수 없다. 그래서 `closing-bet-verify` 의 서비스 하네스 등급으로 라우트 함수를 직접 부른다
- QA 엔진(engine): Claude Code, 서비스 하네스. 원본 3500/5501·live 주소·원본 `.env`·원본 `data/` 는 쓰지 않는다
- 금지 조작: 원본 데이터 삭제, 서버 기동, 원본 파일 쓰기
- 검증 기준 커밋: `2fed790`(첫 커밋, 사본은 `git archive 2fed7907`). 사본의 `chatbot/storage.py` 가 원본 작업 트리와 바이트 단위로 같음을 `cmp` 로 확인했다
- 구성 2026-09-23(첫 커밋 전) | 실행 20:52(기준·검증 사본)·20:53(정리)
- 단계(phase): 시나리오 구성 완료 | 실행 완료
- 반복(iteration): 1
- 결과: 통과 (필수 5/5)
- 증거: 각 시나리오의 「실제」 줄(하네스 표준 출력 원문), 하네스 scratchpad `chat040/qa_harness.py`
- 정리(cleanup): 사본 경로 프로세스 0, `qa-chat040/`(두 사본) 삭제, `qa-chat040-*` 임시 디렉터리 0개, 원본 `data/`·`logs/` 에서 20:40(설계 승인) 이후 수정된 파일 0개, 작업 트리 변화 없음. 서버를 띄우지 않았다. 사본에 venv 가 없어 `TMPDIR` 준비 명령이 실패했으므로 하네스의 `tempfile` 은 기본 임시 경로를 썼고, 정리 검사는 그 경로까지 포함했다
- 필수 여부(required): 예
- 읽은 정본: `.claude/skills/closing-bet-python/SKILL.md`, `.claude/skills/closing-bet-verify/SKILL.md`

## 시나리오

### S-1. 스냅샷 쓰기가 실패해도 삭제는 성공하고 되살아나지 않는다 (핵심)
- 조작: 소유자의 세션이 유일한 상태에서 스냅샷 쓰기가 `OSError(28)` 를 내게 하고 `delete_user_data` 를 부른다. 이어서 새 `HistoryManager` 로 그 소유자의 세션 수를 센다.
- 기대: 검증 사본은 `200`, `chat_sessions=1`, JSON 삭제, 새 인스턴스에서 0. 기준 사본은 `500`·`failed=['chat_sessions']` 이고 새 인스턴스에서 1 로 되살아나 결함이 재현된다.
- 필수 여부(required): 예
- 실제: 검증 `200 chat_sessions=1 failed=None json_exists=False fresh_alice=0`. 기준 `500 failed=['chat_sessions'] json_exists=True fresh_alice=1` 로, 삭제가 실패로 보고되고 새 인스턴스에서 되살아나는 결함이 재현되었다
- 결과: 통과

### S-2. 낡은 JSON 도 지우지 못하면 실패를 보고하고, 복구 뒤 재시도가 지운다 (경계)
- 조작: S-1 에 더해 `unlink` 도 실패하게 한다. 다른 워커 역할의 새 인스턴스가 읽은 뒤, 쓰기를 되돌리고 같은 삭제를 다시 부른다.
- 기대: 첫 호출은 두 사본 모두 `500`. 검증 사본은 재시도가 `200`·`chat_sessions=1` 이고 마지막 새 인스턴스에서 0 이다.
- 필수 여부(required): 예
- 실제: 두 사본 모두 첫 호출 `(500, ['chat_sessions'])`, 다른 워커 역할의 새 인스턴스가 낡은 JSON 을 이관해 `fresh_alice_after_fail=1`, 재시도 `200 chat_sessions=1`, `final_fresh_alice=0`. 검증 사본은 이 갈래에서 장부를 비우고 서명을 None 으로 둔다(단위 테스트 `test_delete_reports_failure_when_stale_snapshot_cannot_be_removed` 가 단언)
- 결과: 통과

### S-3. 삭제가 없는 저장은 스냅샷 실패에도 성공이고 사본을 지우지 않는다 (경계)
- 조작: 메시지를 더한 뒤 스냅샷 쓰기가 실패하는 상태에서 `_save()` 를 부른다.
- 기대: 검증 사본은 `True`, 새 인스턴스의 메시지 2건, JSON 유지. 기준 사본은 `False` 를 돌려준다.
- 필수 여부(required): 예
- 실제: 검증 `save=True fresh_messages=2 json_exists=True`. 기준 `save=False` 로 SQLite 에 저장됐는데도 실패를 돌려준다
- 결과: 통과

### S-4. 장애가 없으면 변경 전과 같다 (회귀)
- 조작: 두 소유자의 세션이 있는 상태에서 장애 없이 한 소유자를 지운다.
- 기대: 두 사본의 응답 dict·남은 소유자 목록·JSON 존재 여부가 같다.
- 필수 여부(required): 예
- 실제: 두 사본 모두 `200 {'status': 'deleted', 'deleted': {'chat_sessions': 1, 'chat_memories': True, 'paper_trading': True, 'usage': True}} owners=['bob@example.test'] fresh_alice=0 json_exists=True` 로 같다
- 결과: 통과

### S-5. 정리 (인접)
- 조작: 사본 경로의 프로세스를 조회하고 사본과 `qa-chat040-*` 임시 디렉터리를 지운다. 원본 `data/`·`logs/` 에서 수정 시각이 바뀐 파일을 센다.
- 기대: 남은 프로세스 0, 사본·임시 디렉터리 삭제, 원본 변화 0.
- 필수 여부(required): 예
- 실제: `pgrep -f qa-chat040` 0건, 사본 삭제, `find /private/tmp /private/var/folders -name 'qa-chat040-*'` 0건, `find data logs -newermt '2026-09-23 20:40' -type f` 0건, `git status --short` 는 비어 있음
- 결과: 통과
