WATCH — Task5/FE041의 핵심 제어 흐름은 적합합니다. 차단급 결함은 발견하지 않았으며, 아래 문구·검증 공백이 남습니다.

범위: 기준 `c5f0ce9`, `041-input.json`의 5개 파일. SHA-256 모두 일치했습니다.

```text
SettingsModal.tsx
b6206ebc8374a2883d1e4c30ecdc0d12c443a8c3f44386e09dcd10bcdb5519bc
env/route.ts
6cc3b644e07b51554e7c192541ff3f5fe8e9ce8483fb07425ec3623c299147b6
SettingsModal.notification.test.tsx
9d2162b2989a551506cfaa3d5ba6c870b65940956a89ffb9ee8164b162ada560
env/route.test.ts
e8fefbce3b066d013d5b508236574b7d4c9bdf7e89b1ab242091ce6dfc5dda1f
2026-09-09-notification-settings.md
433e97e8b8adfc24c8b34685300b1d5123ccceb6c01cda812182d1039b347f4f
```

확인 결과:

- `SettingsModal.tsx:291–303`: 저장 HTTP 성공과 JSON `status: 'ok'`를 모두 요구합니다. 실패는 발송 전에 반환하며 `:338`의 `finally`가 실행됩니다.
- `SettingsModal.tsx:312–336`: 발송도 HTTP 성공과 `status: 'success'`를 모두 요구합니다. `null`·원시값·배열·상태 누락·잘못된 JSON은 성공으로 처리되지 않습니다.
- `env/route.ts:44–65`: upstream fetch와 본문 읽기 예외를 고정 JSON 502, `no-store`로 변환합니다. 인증 판정은 기존 그대로입니다.
- Task4 기존 코드 `common_update_routes.py:257–264`는 정상 키를 부분 반영해도 거부가 있으면 400을 반환합니다. 따라서 후속 발송 차단과 일치합니다.

심각도별 권고:

- **높음/중간: 없음.**
- **낮음 — `SettingsModal.tsx:301`:** 일부 설정이 저장된 400 응답에도 “설정을 저장하지 못해”라고 표시합니다. “설정 저장을 확인하지 못해 테스트 발송을 중단했습니다. 일부 설정은 반영되었을 수 있습니다.”처럼 안내를 보완하면 정확합니다.
- **낮음 — `SettingsModal.notification.test.tsx:60`, `:78`:** unknown JSON 형태별 검사, 발송 네트워크·JSON 실패, 실패 후 버튼 재활성화 검사가 없습니다. 코드상 방어는 확인했지만 해당 회귀 증거는 부족합니다.
- **낮음 — `env/route.test.ts:67–82`:** 고정 JSON 본문 자체를 비교하지 않습니다. 정확한 응답 객체 검증과 POST 본문 읽기 실패 사례 보강을 권고합니다.

강한 반대 근거도 검토했습니다. UI의 순차 실행은 두 서버 요청을 원자적으로 묶지 않으므로, 저장 실패 표시가 이미 반영된 설정을 되돌리지는 않습니다. 이번 변경이 보장하는 것은 **저장 성공을 확인하지 못한 해당 UI 실행에서 후속 send를 호출하지 않는 것**입니다.

실제 수행은 읽기 전용 diff/status/rg/cat/SHA 대조이며, `git diff --check c5f0ce9`는 통과했습니다. 기존 증거에서 targeted 26, pytest 2220+3 skipped, Vitest 389/58파일, typecheck 종료 0, lint 오류 0·경고 204를 확인했습니다. 재실행하지 않았습니다. 브라우저 QA 문서는 필수 행이 미실행·정리 pending이므로, 이 판정은 아키텍처 검토 결과이며 FE041 전체 완료 판정은 아닙니다.
