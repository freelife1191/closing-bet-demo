## Code Review Summary

**Files Reviewed:** 6
**Total Issues:** 3

### By Severity

- CRITICAL: 0
- HIGH: 2
- MEDIUM: 1
- LOW: 0

### Issues

[HIGH, 확신도 높음] 합성 환영 메시지 때문에 서버 삭제 인덱스가 어긋납니다.
File: `frontend/src/app/dashboard/kr/vcp/page.tsx:424`
Issue: 첫 대화 화면은 `welcome + user + assistant`지만 서버에는 `user + model`만 저장됩니다. UI 인덱스를 그대로 `index` 쿼리에 보내므로 질문 삭제가 서버의 답변을 삭제합니다. 실제 실측에서도 `DELETE index=1` 뒤 질문이 남고 모델 답변만 사라졌습니다. 기존 테스트는 서버 이력으로 시작해 합성 환영 메시지를 포함하지 않아 결함을 놓쳤습니다.
Evidence: `preflight-history-before.json`, `preflight-history-after.json`, `preflight-confirm-tree.txt`
Fix: 합성 메시지를 서버 인덱스에서 제외하는 명시적 매핑을 두거나 첫 전송 때 합성 환영 메시지를 제거하십시오. `세션 없음 → 환영 메시지 → 첫 전송 → 질문 삭제` 회귀 검사를 유지해야 합니다.

[HIGH, 확신도 높음] 표시 중인 이력과 삭제 대상 종목·세션이 결속되지 않아 다른 종목의 메시지를 삭제할 수 있습니다.
File: `frontend/src/app/dashboard/kr/vcp/page.tsx:462`
Issue: 종목 전환 시 기존 `chatHistory`를 지우거나 소유 ticker/session을 기록하지 않습니다. 새 이력 GET이 끝나기 전에도 이전 종목 메시지와 삭제 버튼이 표시되지만, 확인 시점에는 현재 `selectedStock`의 세션을 대상으로 잡습니다(`:442`, `:449`). 따라서 화면의 알파 메시지를 선택하고 베타 세션의 같은 인덱스를 삭제할 수 있습니다. 또한 스트림 시작 직후 `chatLoading`을 해제하고(`:1131`), 이후 청크가 현재 화면의 마지막 메시지를 무조건 갱신해(`:1165-1235`) 종목 전환이나 삭제 후 늦은 응답이 새 화면을 오염시킬 수 있습니다.
Fix: 이력 상태를 ticker/session/generation과 함께 저장하고 전환 중 이전 이력을 숨기거나 삭제를 막으십시오. 확인 모달에는 렌더링된 메시지의 target과 서버 인덱스를 함께 캡처하고, GET·SSE 응답에도 동일 target/generation 검사를 적용하십시오.

[MEDIUM, 확신도 높음] 중복 삭제 방지가 세 삭제 경로에 공통 적용되지 않고 모달 소유권도 구분하지 않습니다.
File: `frontend/src/app/dashboard/kr/vcp/page.tsx:437`
Issue: pending ref는 확인 모달 경로에만 적용되며 `/clear`는 `:1080-1083`에서 직접 삭제 함수를 호출합니다. 요청 중에도 입력과 삭제 버튼이 다시 활성화될 수 있어 중복 DELETE가 가능합니다. 요청 중 취소·Escape·배경 클릭으로 모달을 닫고 새 확인창을 열면, 첫 요청의 `finally`가 새 확인창까지 닫을 수 있습니다.
Fix: pending 제어를 공통 삭제 함수 또는 target별 작업 토큰으로 옮기고 `/clear`에도 적용하십시오. 요청 중 모달 취소·확인을 비활성화하거나, 완료 시 자신이 시작한 확인창만 닫도록 작업 ID를 대조하십시오.

### 검증

- 초기 `review-input.json`의 6개 SHA를 대조했습니다.
- 해당 SHA 기준 Vitest 69파일/471테스트, typecheck, build, pytest 2,296개 통과 증거와 lint 0 errors/190 warnings를 확인했습니다.
- 변경 파일 6개에 LSP diagnostics를 실행해 오류 0건을 확인했습니다.
- 검토 중 VCP 회귀 테스트 SHA가 `ed5159…`에서 `475c62…`로 바뀌어 기존 검증 증거는 최신 테스트 파일을 포함하지 않습니다. 새 SHA의 LSP 재확인은 도구 transport 종료로 수행되지 않았습니다.
- 하드코딩 시크릿, 새 빈 catch, 오류를 숨기는 광범위한 fallback은 발견하지 못했습니다. 404 후 GET 재조회는 서버 계약을 구분하기 위한 제한된 복구 경로로 적절합니다.
- 낮은 확신도 관찰: 신규 회귀 테스트에서 다수의 React `act(...)` 경고가 발생합니다. 기능 결함의 직접 증거는 아니지만 비동기 상태 전이 검사의 신뢰도를 낮추므로 정리하는 편이 좋습니다.
- 아키텍처 판정은 별도 lane 범위입니다.

### Recommendation

**REQUEST CHANGES**
