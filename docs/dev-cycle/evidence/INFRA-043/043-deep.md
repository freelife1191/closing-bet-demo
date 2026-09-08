# INFRA-043 심층 리뷰

- 표면: 리더가 설치된 gstack-review 스킬과 review/checklist.md를 직접 적용한 저장소 대응 검토. 외부 CLI review 실행으로 주장하지 않는다.
- 기준: e4c4fd6 → 현재 Task1 diff, 043-input-v2.json 9개 SHA 일치. 같은 develop에서 분리 clone 작업이므로 스킬의 같은 브랜치 조기 종료 대신 저장소 dev-cycle의 명시적 기준 diff를 사용한다.
- 홈 기록/텔레메트리/원격 PR 조회/배포는 이 로컬 검토 범위 밖이라 실행하지 않았다. 원문 보고서는 저장소 evidence에 보존한다.
- Critical: SQL/스키마/셸/LLM 실행 변경 없음. 기존 관리자 게이트 유지, 비활성화는 transport 이전 차단. 새로운 502/503은 유일 UI consumer SettingsModal의 res.ok 실패 분기로 전달된다. 다른 네트워크 호출자를 전체 검색했으며 facade 반환값의 None 의존은 없다.
- Informational: exception type만 남기고 requests의 외부 resp.text는 status로 바꿔 값 노출을 막는다. config.disabled는 객체 생성 시 확정되며 런타임 전체 워커에 설정을 방송하는 기능이 아니다. notifier 스택의 로그도 같은 정책으로 맞췄으며 새 추상화/의존성 없음.
- 회귀: 실제 Messenger/sender+transport 대역과 실제 Flask 라우트, 개별 custom HTTP 결과 검증 69 passed. 전체 pytest2112 passed/3 skipped, frontend 동일 SHA에서 Vitest373 passed. 테스트 성공용 None 대역은 실제 bool 계약의 True로 갱신했고 실제 구현 통합 검사로 보강했다.
- 미실행: 외부 CVE 조회(의존성 변경 없음), MCP LSP/AST(Transport closed). stdlib AST 구문/위험로그 스캔은 대체 검사이고 LSP 성공이 아니다.
- 결과: Pre-Landing Review: No issues found. APPROVE. 별도 독립 code/architecture/security 레인과 실제 UltraQA는 별도의 완료 조건이다.
