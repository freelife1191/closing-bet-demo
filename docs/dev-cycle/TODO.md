# TODO

> 백로그의 단일 관리 지점입니다. 형식은
> `.claude/skills/dev-cycle/references/archive-format.md` 를 따릅니다.
> 완료된 항목은 아카이브로 옮기고 이 파일에서 제거합니다.
> 진행은 `/dev-cycle next` 로 시작합니다.

## P0 — 즉시

### [INFRA-001] 파이썬 의존성 버전 고정
- 카테고리: 인프라 | 티어: T3 | 근거: 2026-09-01 실측
- [ ] `requirements.txt` 의 14개 패키지에 버전 핀 적용
- [ ] `google-genai` 1.62 → 2.x 호환성 확인 (`engine/genai_client.py` 호출부)
- [ ] `requirements.updated.txt` 와의 관계 정리 또는 폐기
- [ ] pytest 전체 통과 확인

## P1 — 이번 주기

### [JONGGA-001] generator.py 의 인라인 페이즈 로직을 phases 모듈로 교체
- 카테고리: 종가베팅 | 티어: T3 | 근거: CLAUDE.md 이관
- [ ] `engine/generator.py` 의 인라인 페이즈 로직 범위 확정
- [ ] `engine/phases_*.py` 의 기존 클래스로 대체
- [ ] 신호 생성 결과가 교체 전후로 동일한지 확인
- [ ] 회귀 테스트 추가

## P2 — 대기

### [FE-001] 낡은 업그레이드 베이스라인 테스트 정리
- 카테고리: 프론트엔드 공통 | 티어: T1 | 근거: 2026-09-01 vitest 실행
- 세 건이 과거 업그레이드 시점의 버전을 고정 검사해 항상 실패합니다.
  현재 Next 16.1.6 / React 19.2.4 인데 각각 14.x, 18.x, 15.x 를 기대합니다.
- [ ] `tests/baseline/upgrade-baseline.test.ts` 의 버전 고정 검사 처리
- [ ] `tests/baseline/upgrade-nextjs15.test.ts` 의 버전 고정 검사 처리
- [ ] 버전 검사를 유지할지 삭제할지 결정 (하한선 검사로 바꾸는 방안 포함)
- [ ] vitest 160개 전체 통과 확인

### [FLOW-001] 장중 실시간 수급 데이터 KIS API 연동
- 카테고리: 수급·백테스트 | 티어: T3 | 근거: docs/plans/TO_DO_LIST.md 이관
- 선행 조건: 한국투자증권 계좌 개설과 Open API 키 발급이 끝나야 착수할 수 있습니다
- [ ] `KIS_APP_KEY`, `KIS_APP_SECRET`, `KIS_ACCOUNT_NO` 를 `.env.example` 에 추가
- [ ] `engine/kis_collector.py` 연동 활성화
- [ ] 장중 수급 점수가 0 으로 고정되던 동작 해소 확인
- [ ] 참고 문서: `docs/KIS_API_GUIDE.md`

### [FLOW-002] 수급 데이터 분석 고도화
- 카테고리: 수급·백테스트 | 티어: T2 | 근거: docs/plans/TO_DO_LIST.md 이관
- [ ] 섹터별 수급 집계 설계
- [ ] 기존 `services/investor_trend_5day_service.py` 와의 경계 정리

### [INFRA-002] 타입 힌트 보강
- 카테고리: 인프라 | 티어: T2 | 근거: CLAUDE.md 이관
- [ ] 타입 힌트가 없는 공개 함수 범위 확정
- [ ] 우선순위가 높은 모듈부터 보강
- [ ] 한 번에 300줄을 넘기지 않도록 여러 항목으로 나누어 진행
