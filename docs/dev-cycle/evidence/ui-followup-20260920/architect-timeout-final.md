## 요약

Architectural Status: CLEAR

fetchAPI의 timeout이 이제 headers 도착 시점이 아니라 JSON 본문 수신·파싱 완료까지 유지됩니다. 조기 clearTimeout을 제거하고 return await response.json()으로 finally가 본문 처리 뒤 실행되도록 한 구조가 정확합니다(api.ts:18).

200 응답 본문 정체는 Request timed out, 500 응답 본문 정체는 제한 시간 안에 상태 기반 API Error: 500으로 종료됩니다. 두 경우 모두 signal abort와 timer 정리를 검증합니다(api.body-timeout.test.ts:9).

현재 두 파일 SHA는 QA manifest와 일치합니다. 최신 격리 검증도 Vitest595/81, build3/3, lint0errors, typecheck성공입니다. 이 timeout delta에서 새 BLOCK/WATCH는 없습니다.
