# UltraQA Report — JONGGA-032

- engine: ultraqa | lifecycle: app-adapted | phase: complete | iteration: 2 | same_failure_count: 0
- 목표: 종가 업데이트 완료 시 버튼 복구·최신 결과 갱신, 완료/시간 제한/화면 이탈 후 폴링 종료.
- 범위: closing-bet/page.tsx 폴링과 회귀 테스트. JONGGA-014의 필수 S-3 재검증과 공유한다.
- browser_applicability: required | browser_driver: agent-browser
- 호출부: 종가 화면 확인 모달 → runUpdate → run POST → status GET → onRefresh.
- 기준: b50854c. qa-source-verification.json으로 실행 checkout과 리뷰 source SHA 일치 확인.
- baseline: 회귀15통과(3파일), pytest2281통과/2skip, Vitest429통과(60파일), type-check0, lint0오류/200기존경고. evidence/jongga-polling-20260909/static-results.json.
- 안전: 원본3500/5501/live/.env/data 쓰기 금지. 실제 Next UI와 합성 HTTP/Phase 경계, 외부 연결 차단.
- 대상: 소유권 확인 후 http://127.0.0.1:57361/dashboard/kr/closing-bet.
- namespace/session: jongga-polling-20260909 / qa
- 상한: QA5회·동일 실패3회, 명령 최대60초(긴 테스트는 상태 확인), 소유 환경만 정리.
- UltraQA Report: [JONGGA-032.md](JONGGA-032.md)

| ID | 의도/모델 | Setup/command | 기대 | 실제 | 수정 | 증거 | cleanup | 필수 |
|---|---|---|---|---|---|---|---|---|
| S-1 | 정상 완료·사용자 | 실제 UI 실행 확인, 합성 run200/status완료 | 버튼 재활성화, 결과 재조회, 추가 polling 없음 | 통과: POST200·status2회·latest1회, UPDATED 및 버튼활성, 이후 polling 없음 | 반영 완료 | ../evidence/jongga-polling-20260909/ | 완료 | 예 |
| S-2 | 이미 실행 중·재시도 | 실제 UI run409 → 진행 → 완료 | 진행 표시 후 버튼 복구, polling 종료 | 통과: POST409·진행문구·status2회·latest1회, UPDATED 및 버튼활성 | 반영 완료 | 같은 경로 | 완료 | 예 |
| S-3 | 실패·오인성공 | 실제 UI run500/Phase1 TypeError | 성공으로 표시하지 않음, 버튼 복구, Phase1 단일 호출 | 통과: POST500·예상 console 오류·추가 status/latest0회, 기존리포트 유지 및 버튼활성, 같은 예외/Phase1 1회 | 기존 pipeline 유지 | 같은 경로 | 완료 | 예 |
| S-4 | 이탈·늦은 응답 | 진행 중 실제 UI 다른 화면 이동, 회귀 deferred 응답 | 이탈 이후 새 polling/refresh 없음, 타이머 해제 | 통과: 실제 홈 이동 뒤 status13회→13회 고정, 회귀에서 late status/run 뒤 요청·refresh 없음 | 반영 완료 | 같은 경로 | 완료 | 예 |
| S-5 | 시간 제한·동시 요청 | fake timer 350초 및 느린 응답 회귀 | 제한 뒤 버튼 복구, 늦은 응답 무효, 타이머0 | 통과: 회귀 350초 뒤 timer0 및 late응답무효, in-flight 요청 중복없음 | 반영 완료 | 같은 경로 | 완료 | 예 |
| S-6 | 격리·숨은 실패 | source SHA·원본 사용자파일 hash·오류·PID 확인 | 실제 수정 소스 검증, 비밀/외부효과0, owned 환경 정리 | 통과: 검토SHA동일·package불변·2세션/owned서버/fixture정리완료 | 없음 | 같은 경로 | 완료 | 예 |

신규 JSON/문자열 파서 및 지시 실행 표면 없음: Unicode·경로 이탈·prompt injection은 적용하지 않는다.
필수 통과 6/6. 미통과 필수 없음. 완료 가능.

## 실행·증거·제한

- source 및 정적: qa-source-verification.json, static-results.json, review-input.json과 두 독립 리뷰 원문. 초기 staged whitespace 검사 실패는 code-review.original.md.gz 보존 후 표시 문서 공백만 정리해 통과했다.
- 브라우저: browser-before/normal-running/normal-completed/conflict-running/conflict-completed/typeerror-recovered/unmount-before/unmount-after.txt, PNG4개와 diagnostic-completed.png를 직접 열어 대조했다. browser-verification.json의 요청 행렬과 일치한다.
- normal/409는 실제 Next UI와 합성 HTTP 상태 전이 검증이다. TypeError는 실제 SignalGenerationPipeline에 합성 Phase를 연결했으며 pipeline-probe.json.gz에 같은 예외와 호출1회가 기록되어 있다. 실제 운영 수집·LLM·거래 검증을 주장하지 않는다.
- 최초 page-errors.json에 URL-null SyntaxError1건. 새 diagnostic 세션에서 open/auth/complete/screenshot/typeerror/postconsole/navigation 단계별 오류 배열은 모두 빈 배열. 최초 오류는 재현되지 않았으며 제품/도구 원인을 단정하지 않는다. 기존 console의 합성 TypeError1건은 의도한 실패 응답이다.
- Next get_errors는 configErrors/sessionErrors 빈 배열. Webpack의 get_compilation_issues는 -32602 도구 없음으로, 실제 dev 컴파일로그와 typecheck/Vitest build 스모크로 대체했다. 해당 MCP 호출을 성공으로 표시하지 않는다.
- 하네스 준비의 실행권한·awk구문 문제를 실행 전에 보완했다. cleanup 첫 시도는 next-server의 변경된 process title 때문에 보수적으로 거부됐다. 부모PID/PGID/cwd를 재확인해 정확한 owned group만 종료했다. cleanup.json 및 diagnostic-cleanup.json 참조.
- 구현 스킬: brainstorming bounded(이전 제안 및 후속 묶음 진행 요청), TDD, vercel-react-best-practices(타이머 ref와 stale response), Next 번들 06-fetching-data/05-server-and-client-components 및 testing/vitest. UltraQA App대응 + agent-browser. native OMX 상태 변경 없음.

ULTRAQA COMPLETE: Goal met after 2 cycles
