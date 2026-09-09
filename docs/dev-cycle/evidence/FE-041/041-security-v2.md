# FE-041 Task 5 독립 보안 재검토 — v2 delta

## 최종 판정

**APPROVE**

- 입력 manifest: `041-input-v2.json`
- manifest SHA-256: `22ff12f6fb38b1aa1bbf56985a69ff1a663d24c4542388f49b904777e884c287`
- 파일 SHA-256: manifest 5개와 현재 checkout **5/5 일치**
- v1 제품 보안 판정: 유지
- 미해결 이슈: CRITICAL 0 / HIGH 0 / MEDIUM 0 / LOW 0

## Delta 검토

- 제품 보안 로직은 v1과 동일합니다. `frontend/src/app/api/system/env/route.ts`, 승인 계획의 SHA는 바뀌지 않았습니다.
- `SettingsModal.tsx`의 변경은 저장 실패 문구 한 줄입니다. `Some settings were rejected; accepted settings were saved.`라는 backend 계약과 맞게 “저장 확인 불가”와 “일부 설정은 반영되었을 수 있음”을 알립니다. 실패를 전체 롤백으로 잘못 단정하지 않으며 발송 중단 동작은 그대로입니다.
- 문구는 고정 문자열이고 React 텍스트 노드에 렌더링되므로 시크릿 반사나 XSS 표면을 추가하지 않습니다.
- 설정 응답의 `null`, 숫자, boolean, 문자열 `ok`, 배열, 빈 객체는 모두 성공으로 오인하지 않고 발송 0건으로 끝납니다.
- 발송 응답의 비객체·거짓 성공 JSON도 실패로 표시합니다. network/invalid JSON의 canary는 UI에 나타나지 않으며 raw 예외 console 출력도 없습니다.
- 저장·발송 실패와 early return 뒤 `finally`가 버튼을 재활성화합니다. 저장 실패 후 설정을 고쳐 재시도하면 순서가 `save → save → send`로 유지되어 실패 상태를 우회하거나 성공 상태를 고착하지 않습니다.
- Next route의 upstream body-read 오류 검사가 GET과 POST 모두로 확장됐고, 두 경우 고정 JSON 502와 `Cache-Control: no-store`를 정확히 대조합니다. 내부 token·예외 원문은 응답에 포함되지 않습니다.

## 실제 실행·확인

- `041-input-v2.json` 5개 SHA-256 대조: 모두 일치
- `SettingsModal.notification.test.tsx` + `api/system/env/route.test.ts`: **35 passed**, test files 2 passed
- 제공된 v2 관련 대상 검사: **42 passed**, exit 0
- `git diff --check`: 통과
- 정적 검색: HTML 직접 주입과 private/saved/data raw console logging 없음
- backend 제품·검사는 변경되지 않았으며 기존 전체 pytest **2220 passed / 3 skipped** 증거의 범위를 그대로 유지

## 유지되는 v1 보안 판정

- 저장 HTTP `ok` + JSON `status: ok` 전에는 발송하지 않습니다.
- 발송 HTTP `ok` + JSON `status: success`만 성공입니다.
- 익명·비관리자는 upstream fetch 전에 no-store 403으로 차단됩니다.
- `X-Admin-Token`은 server-only `API_URL` 대상 upstream 요청에만 붙고 브라우저 응답에 노출되지 않습니다.
- upstream fetch/body 오류는 고정 no-store 502이며 raw 예외를 로그·응답에 넣지 않습니다.
- 실패 메시지는 React 텍스트로 렌더링되어 markup으로 실행되지 않습니다.

## 실행하지 않은 검사

- MCP LSP·ast-grep: `Transport closed`가 확정되어 재시도하지 않았습니다.
- 전체 pytest/Vitest/typecheck/lint와 제품 전 범위는 delta 리뷰에서 반복하지 않았습니다.
- 실제 `.env`, `data`, `logs`, 원본·격리 HTTP 서버, 3500/5501, live URL, LLM·외부 발송·설정 쓰기·삭제는 실행하지 않았습니다.
- 실제 브라우저·header·cache·bundle/log canary 검증은 후속 격리 QA의 별도 완료 조건이며 이 리뷰가 대신하지 않습니다.

## Recommendation

**APPROVE.** v2 문구·테스트 delta는 v1 보안 경계를 약화하지 않고, 부분 반영 고지와 비정상 JSON·오류·재시도 증거를 보강합니다.
