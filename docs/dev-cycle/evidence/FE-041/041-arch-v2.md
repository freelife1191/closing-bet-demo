**CLEAR — 제한 v2 재검토에서 v1 WATCH 3항목은 모두 해소됐습니다. 신규 테스트 결함은 발견하지 못했습니다.**

범위는 기준 `c5f0ce9`, 계획 Task5/FE-041입니다. `041-input-v2.json`의 5개 SHA-256이 현재 파일과 모두 일치합니다.

```text
SettingsModal.tsx
e6d071638fe77a3e3f209506a2157b4e0c2a3c4ba908bb12b6836a012f868bd1
env/route.ts
6cc3b644e07b51554e7c192541ff3f5fe8e9ce8483fb07425ec3623c299147b6
SettingsModal.notification.test.tsx
ea873327815c45aa2f5ebb45cbc958a91a713c18806618277a43fcd8737d9489
env/route.test.ts
84c81d5dc527d8a9b9c942adf056f062177fff735316b8740428408bb42020d3
2026-09-09-notification-settings.md
433e97e8b8adfc24c8b34685300b1d5123ccceb6c01cda812182d1039b347f4f
```

수정 반영 증거:

- `SettingsModal.tsx:301`: 저장 **확인 실패**와 **부분 반영 가능성**을 명시했습니다. Task4의 부분 저장 후 400 반환과 일치합니다.
- `SettingsModal.notification.test.tsx:68,78,106,113`: 저장·발송 각각 unknown JSON 6종, 발송 network/invalid JSON, 오류값 비노출, 버튼 재활성화를 검사합니다. 저장 실패 후 실제 재시도에서 `save → save → send`도 확인합니다.
- `env/route.test.ts:67,76`: GET/POST 모두 upstream fetch 및 `response.text()` 실패에 대해 **502·no-store·고정 JSON 전체 객체**를 대조합니다. inbound `Request.text()`로 범위를 확장하지 않았습니다.

**심각도별 미해결 사항: 높음·중간·낮음 모두 없음. 추가 수정 권고 없음.**

실제 검사는 읽기 전용 status/diff/rg/cat/SHA 대조이며, diff 공백 오류 출력도 없습니다. 기존 `vitest-041-v2.log`에서 **42 passed / 4 files**를 확인했습니다. 테스트·HTTP·브라우저는 실행하지 않았습니다.

검증 한계: 발송 오류 후에는 재활성화까지 검사하고 재클릭 성공까지는 검사하지 않습니다. 이번 세 지적의 해소를 막는 결함은 아닙니다. 또한 후속 send 차단은 이미 반영된 설정의 롤백을 보장하지 않습니다. 이 판정은 제한 재검토 결과이며 FE-041 전체 QA 완료 판정은 아닙니다.
