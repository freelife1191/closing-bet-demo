# HistoryManager 책임 분리 설계

대상: CHAT-035 · 기준 커밋: d24c2156 · 설계일: 2026-09-23

## 승인과 현재 단계

사용자는 2026-09-23 대화에서 다음 항목으로 「CHAT-035 (Recommended)」를, 접근안으로
「A. 부품 세 개로 조립 (Recommended)」를, 테스트 처리로 「테스트의 접근 경로만 고침
(Recommended)」을 골랐다. 이어서 채팅으로 제시한 설계 1절(부품과 경계)·2절(동작 보존·
검증·절차)에 「승인 (Recommended)」로 응답했다(17:39 확인). 이 문서는 그 승인 내용을 옮긴
것이며, 문서 자체의 검토 승인을 받기 전에는 구현 계획을 쓰지 않는다. 제품 코드는 아직
변경하지 않았다.

## 목표와 범위

`chatbot/storage.py` 의 `HistoryManager`(575줄)가 진 책임 가운데 세 가지를 상태를 가진 작은
클래스로 떼어 낸다. 레거시 JSON 스냅샷, 읽기 캐시(LRU 둘과 목록 버전), 델타 장부다. 저장소
서명 계산은 상태가 없으므로 같은 모듈의 함수로 뺀다. `HistoryManager` 에는 적재·저장·재적재의
조율과 세션·메시지 CRUD 만 남긴다.

범위 밖: SQLite 함수(`chatbot/storage_sqlite_*.py`), `MemoryManager`, 잠금 구조 변경, 외부
호출자가 비공개 메서드를 부르는 방식의 정리, 동작 변경. 근거가 된 `[CHAT-033]` 의 결함은
이미 고쳐졌으므로 이 항목은 결함 수정이 아니라 구조 정리다.

## 확인한 현재 구조

- 상태 필드 12개가 한 클래스에 있다. 스냅샷(`_legacy_snapshot_interval_seconds`,
  `_last_legacy_snapshot_monotonic`, `_sync_snapshot_on_load`), 캐시(`_sanitized_messages_cache`,
  `_session_list_cache`, `_session_list_version`), 서명(`_last_reload_signature`), 장부
  (`_pending_changed_session_ids`, `_pending_deleted_session_ids`, `_pending_clear_all`), 그리고
  `sessions`·`_reload_failed` 다.
- 잠금은 `threading.RLock` 하나이며 `@locked` 로 공개 메서드와 `_save`·`_reload_sessions`·
  `_invalidate_*`·`_mark_session_changed` 를 감싼다. `_mark_session_deleted`·`_mark_clear_all`
  은 잠금 안에서만 불린다.
- 외부 호출자가 비공개 메서드를 부른다. `chatbot/command_service.py:31-38`·`:103-107` 과
  `chatbot/session_access.py:30-37` 은 `hasattr` 로 확인한 뒤 `_mark_session_changed`·
  `_invalidate_message_cache`·`_invalidate_session_list_cache`·`_save` 를 부른다. 이름이 바뀌면
  예외 없이 저장만 빠진다.
- `chatbot/core.py:83` 의 하위 클래스는 `sessions`·`create_session`·`add_message`·
  `get_messages` 만 쓴다.
- `tests/chatbot/test_history_manager_sync.py` 가 내부 상태를 직접 읽거나 바꾼다.
  `_sanitized_messages_cache`(194-197행), `_session_list_cache`(265-268행),
  `_legacy_snapshot_interval_seconds`·`_last_legacy_snapshot_monotonic`(363-364행 등),
  `_atomic_write` 몽키패치(317·349·367·390행 부근), `_reload_failed`(474·479행),
  `_load`·`_save`(105·206·351행).
- `_backup_corrupt_history` 는 어디에서도 부르지 않는다. 손상 파일 백업은
  `load_history_sessions` 가 헬퍼를 직접 부른다.

## 구조

새 모듈 `chatbot/storage_history_parts.py` 에 다음을 둔다. 세 클래스 모두 자기 잠금을 갖지
않는다. `HistoryManager` 의 `RLock` 을 쥔 상태에서만 불리므로, 잠금을 하나로 유지해 `[CHAT-033]`
과 같은 상태 경합이 부품 사이에서 새로 생기지 않게 한다.

- `LegacySnapshot(file_path, interval_seconds)`
  - 상태: `interval_seconds`, `last_monotonic`
  - `from_env(file_path)`: `CHATBOT_HISTORY_LEGACY_SNAPSHOT_INTERVAL_SECONDS` 를 읽는다.
    기본 15, 음수는 0, 해석 실패는 15 로 지금과 같다.
  - `write(data)`: `atomic_write_json` 호출. 테스트가 이 메서드를 몽키패치한다.
  - `sync(data, force=False) -> bool`: 간격 판정 뒤 `write` 를 부르고 시각을 기록한다.
- `HistoryReadCache()`
  - 상태: 정제 메시지 LRU(최대 2,048), 세션 목록 LRU(최대 256), 목록 버전
  - `get_messages(session_id, fingerprint)` 는 적중 시 복제본을, 아니면 `None` 을 돌려준다.
    `put_messages(session_id, fingerprint, sanitized)` 는 저장 후 정리한다.
  - `get_session_list(owner_id)`·`put_session_list(owner_id, sessions)` 는 버전이 같을 때만
    적중하고 복사본을 돌려준다.
  - `invalidate_messages(session_id=None)`, `invalidate_session_list()`(버전 증가)
- `SessionDeltaLedger()`
  - 상태: `changed`, `deleted`, `clear_all`
  - `mark_changed`(빈 id 무시, `deleted` 에서 제거, `clear_all` 을 False 로 내림: 지금 동작
    유지), `mark_deleted`(빈 id 무시, `changed` 에서 제거), `mark_clear_all`, `has_delta`,
    `reset()`
- `storage_signature(db_path, file_path)`: db·wal·shm 서명을 돌려주고 셋 다 없으면 JSON
  파일의 서명을 돌려준다. `stat` 실패 로그도 지금과 같다.

`HistoryManager` 는 `_snapshot`·`_cache`·`_delta` 를 조립하고 `sessions`, `_reload_failed`,
`_last_reload_signature`, `_sync_snapshot_on_load`, `_lock` 을 계속 가진다. `_load`,
`_restore_lost_messages_from_snapshot`, `_save`, `_reload_sessions`, 레코드 생성 함수, 공개
메서드는 이 클래스에 남는다. 외부가 부르는 `_mark_session_changed`·`_invalidate_message_cache`·
`_invalidate_session_list_cache`·`_save` 는 이름과 `@locked` 를 유지한 한 줄 위임이다.
`_backup_corrupt_history` 는 호출자가 없으므로 지운다.

## 동작 보존

동작 변화는 0 이다. 다음을 한 글자도 바꾸지 않고 옮긴다.

- `_save`: 재적재 실패 시 쓰기 거부, 델타가 없으면 SQLite 를 부르지 않음, 스냅샷 강제 조건
  (SQLite 실패·전체 삭제·세션 삭제), 실패하면 서명을 비움, 끝에 장부 초기화, 예외는 로그 후
  False.
- `_reload_sessions`: 서명이 같으면 건너뜀, 재적재 중 스냅샷 쓰기 생략, 실패 시 서명을 비움,
  성공 시 두 캐시 무효화.
- `_load`·`_restore_lost_messages_from_snapshot`: 호출 순서와 반환값 그대로.
- 캐시 적중 조건(메시지는 `updated_at`·메시지 수 지문, 목록은 버전)과 복제 방식 그대로.

## 검증

- `tests/chatbot/` 전체와 원본 트리 전체 pytest 가 통과한다(`[INFRA-083]` 의 세션 끝 검사 포함).
- `test_history_manager_sync.py` 는 내부 접근 경로만 새 위치로 바꾼다. 예:
  `manager._session_list_cache` → `manager._cache.session_list`,
  `monkeypatch.setattr(manager, "_atomic_write", …)` → `monkeypatch.setattr(manager._snapshot,
  "write", …)`. 단언하는 값과 기대값은 바꾸지 않는다. 하위호환 별칭 속성은 만들지 않는다.
- 새 파일 `tests/chatbot/test_storage_history_parts_refactor.py` 에 부품마다 분기 검사 하나를
  둔다. 장부 상태 전이(changed↔deleted, clear_all), 스냅샷 간격 판정(0 이하·첫 호출·간격 전후),
  LRU 정리와 목록 버전 무효화다.
- QA: 격리 사본(원본 3500·5501 이 아닌 포트, `SCHEDULER_ENABLED=false`)에서 LLM 을 가짜
  클라이언트로 바꾼 뒤 브라우저로 /chatbot 에 들어가 대화 생성 → 메시지 송수신 → 메시지·대화
  삭제 → 새로고침을 수행한다. 목록과 본문이 조작한 대로 남아야 한다. 실제 LLM 호출과 원본
  서버 조작은 하지 않는다.

## 절차와 티어

TODO 에 적힌 T3 를 유지한다(`chatbot/storage.py` 는 `tier-rules.md` §2 위험 경로 목록에 없지만
대화 영구 저장의 조율부이며, 티어는 낮추지 않는다). 순서는 이 문서의 검토 승인 → 구현 계획
(`docs/superpowers/plans/2026-09-23-chat-035-history-manager-split.md`) → critic 검토 → 구현
(RED→GREEN) → `/ponytail-review` → `closing-bet-reviewer` → `/review` → QA → 아카이브다.
