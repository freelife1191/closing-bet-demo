# 독립 아키텍처 최초 BLOCK 원문

아키텍처 검토 중 구체적 BLOCK 후보 1건: `chatbot/storage.py:271-285`가 title 문자열 `"새로운 대화"` 자체를 미설정 sentinel로 쓰고, 이전 일반질문 존재 여부를 현재 보존된 `messages[:-1]`에서만 복원합니다. `add_message`는 그 뒤 50개로 절단(`:470-472`). 따라서 첫 일반질문 자체가 정확히 `"새로운 대화"`여서 제목 값이 sentinel과 같고, 그 질문이 50개 창 밖으로 밀린 뒤 다음 일반질문이 오면 제목이 덮어써져 '첫 질문 후 유지' 계약을 위반합니다. 현재 테스트는 default-equal(`tests/chatbot/test_storage_sqlite.py:117-130`)과 50절단(`:133-149`)을 분리해 이 조합을 놓칩니다. 지속 상태(예: auto-title-set 플래그) 없이는 bounded history와 동명 제목을 동시에 완전 판정할 수 없습니다. 스키마/과거자료 무변경 제약과 충돌하므로 최소 대안은 세션 레코드의 선택적 메타 필드(마이그레이션 없이 신규/변경 세션만) 또는 제목 sentinel 분리입니다.

부모 결과: target-red-sentinel에서재현. 신규title빈값으로미설정구분하고,SQLite기존TEXT열에보존하며목록에만표시문구반환. 명령기록/기존제목보존. 구조추가없이메시지스캔제거. target-sentinel-fixed93passed. 최종판정은 architect-review.md.
