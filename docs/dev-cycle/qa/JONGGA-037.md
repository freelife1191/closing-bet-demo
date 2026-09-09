# UltraQA Report — JONGGA-037

- engine: ultraqa | lifecycle: app-adapted | phase: planning | iteration: 1 | same_failure_count: 0
- 목표: 종가 업데이트 완료 시 버튼 복구·최신 결과 갱신, 완료/시간 제한/화면 이탈 후 폴링 종료.
- 범위: closing-bet/page.tsx 폴링과 회귀 테스트. JONGGA-014의 필수 S-3 재검증과 공유한다.
- browser_applicability: required | browser_driver: agent-browser
- 호출부: 종가 화면 확인 모달 → runUpdate → run POST → status GET → onRefresh.
- 기준: b503549 이후 공유 폴링 수정 커밋을 첫 실행 전에 확정한다.
- baseline: 회귀15통과(3파일), pytest2281통과/2skip, Vitest429통과(60파일), type-check0, lint0오류/200기존경고. evidence/jongga-polling-20260909/static-results.json.
- 안전: 원본3500/5501/live/.env/data 쓰기 금지. 실제 Next UI와 합성 HTTP/Phase 경계, 외부 연결 차단.
- 대상: 소유권 확인 후 http://127.0.0.1:57361/dashboard/kr/closing-bet.
- namespace/session: jongga-polling-20260909 / qa
- 상한: QA5회·동일 실패3회, 명령 최대60초(긴 테스트는 상태 확인), 소유 환경만 정리.
- UltraQA Report: [JONGGA-037.md](JONGGA-037.md)

| ID | 의도/모델 | Setup/command | 기대 | 실제 | 수정 | 증거 | cleanup | 필수 |
|---|---|---|---|---|---|---|---|---|
| S-1 | 정상 완료·사용자 | 실제 UI 실행 확인, 합성 run200/status완료 | 버튼 재활성화, 결과 재조회, 추가 polling 없음 | 미실행 | 예정 | ../evidence/jongga-polling-20260909/ | 대기 | 예 |
| S-2 | 이미 실행 중·재시도 | 실제 UI run409 → 진행 → 완료 | 진행 표시 후 버튼 복구, polling 종료 | 미실행 | 예정 | 같은 경로 | 대기 | 예 |
| S-3 | 실패·오인성공 | 실제 UI run500/Phase1 TypeError | 성공으로 표시하지 않음, 버튼 복구, Phase1 단일 호출 | 미실행 | 기존 pipeline 유지 | 같은 경로 | 대기 | 예 |
| S-4 | 이탈·늦은 응답 | 진행 중 실제 UI 다른 화면 이동, 회귀 deferred 응답 | 이탈 이후 새 polling/refresh 없음, 타이머 해제 | 미실행 | 예정 | 같은 경로 | 대기 | 예 |
| S-5 | 시간 제한·동시 요청 | fake timer 350초 및 느린 응답 회귀 | 제한 뒤 버튼 복구, 늦은 응답 무효, 타이머0 | 미실행 | 예정 | 같은 경로 | 대기 | 예 |
| S-6 | 격리·숨은 실패 | source SHA·원본 사용자파일 hash·오류·PID 확인 | 실제 수정 소스 검증, 비밀/외부효과0, owned 환경 정리 | 미실행 | 없음 | 같은 경로 | 대기 | 예 |

신규 JSON/문자열 파서 및 지시 실행 표면 없음: Unicode·경로 이탈·prompt injection은 적용하지 않는다.
필수 통과 0/6. 아직 실행하지 않았으며 완료로 판정하지 않는다.
