# Task 1 구현 보고 — 설정 입력과 공용 이름

## 결과

- `apiKeyFieldProps`를 `storedEnvFieldProps`로 바꾸고 모든 참조와 회귀 검사를 새 이름으로 통일했다.
- API 키 2개, 알림 환경값 8개, Google 검색 엔진 ID 입력이 같은 표시 경로를 사용한다. 서버가 `*`를 포함해 돌려준 값은 입력값에 넣지 않고 `저장되어 있습니다. 바꾸려면 새 값을 입력하세요`라는 고정 placeholder로 표시한다.
- 기존 라벨 문구를 유지하면서 각 환경값 라벨의 `htmlFor`와 입력의 `id`를 연결했다.
- API 키 삭제 버튼은 각각 `OPENAI_API_KEY 삭제`, `PERPLEXITY_API_KEY 삭제`라는 이름을 갖는다.
- Sidebar의 `+` 버튼은 `무료 사용량 5회 충전 (하루 1회)`라는 이름을 갖는다.
- 사용자가 새 값을 입력하면 해당 키만 상태에서 교체된다. 손대지 않은 마스킹 값은 기존 상태와 저장 payload에 남아 서버의 기존 보존 계약을 따른다. 마스킹 판정이나 서버 정책은 추가하지 않았다.

## TDD 증거

- 부모 격리 RED: `11 failed / 13 passed`. 실패 원인은 `storedEnvFieldProps` 미정의 6건, 라벨·마스킹·검색 ID·삭제/충전 이름 누락 5건이었다.
- 부모 격리 GREEN: `24 passed`, 종료 코드 0.
- 기존 API 키의 빈 입력값, 마스킹 문자열 비노출, localStorage 비저장 검사는 유지했다.
- ModalShell의 body portal 변경을 고려해 기존 `container.querySelector` 범위는 `baseElement`로만 옮겼고 행동 assertion은 삭제하지 않았다.

## 변경 파일

- `frontend/src/app/components/SettingsModal.tsx`
- `frontend/src/app/components/settingsEnv.ts`
- `frontend/src/app/components/Sidebar.tsx`
- `frontend/src/app/components/SettingsModal.apikeys.test.tsx`
- `frontend/src/app/components/SettingsModal.env-fields.test.tsx`
- `frontend/src/app/components/settingsEnv.test.ts`
- `frontend/src/app/components/Sidebar.session.test.tsx`

## 범위 확인

- Header와 ChatWidget은 기존 이름을 유지하며 수정하지 않았다.
- 실제 `.env`, `data/`, 인증, 알림 발송, LLM, 수집, 거래, 삭제, 원본 3500/5501 및 live HTTP를 건드리지 않았다.
- 새 의존성, 타입 억제, lint 억제를 추가하지 않았다.
