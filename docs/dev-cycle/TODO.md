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

### [FE-001] 낡은 업그레이드 베이스라인 테스트 정리
- 카테고리: 프론트엔드 공통 | 티어: T2 | 근거: 2026-09-01 vitest 실행
- 대상 두 파일이 합계 513줄이고 구현 파일은 건드리지 않으므로, `tier-rules.md` §1 의
  제외 조항이 적용되지 않아 그대로 셉니다. 화면이 바뀌지 않으므로 실측할 대상은 없습니다.
- 세 건이 과거 업그레이드 시점의 버전을 고정 검사해 항상 실패합니다.
  현재 Next 16.1.6 / React 19.2.4 인데 각각 14.x, 18.x, 15.x 를 기대합니다.
- [ ] `tests/baseline/upgrade-baseline.test.ts` 의 버전 고정 검사 처리
- [ ] `tests/baseline/upgrade-nextjs15.test.ts` 의 버전 고정 검사 처리
- [ ] 버전 검사를 유지할지 삭제할지 결정 (하한선 검사로 바꾸는 방안 포함)
- [ ] vitest 160개 전체 통과 확인

### [FE-002] Next.js 16.1.6 을 16.3.4 로 올린다
- 카테고리: 프론트엔드 공통 | 티어: T2 | 근거: 2026-09-01 실측
- 선행 조건: `[FE-001]` 이 끝나야 합니다. 낡은 버전 고정 검사를 남겨 둔 채 올리면
  업그레이드가 만든 실패와 원래 있던 실패를 구별할 수 없습니다.
- `next-dev-loop`, `next-cache-components-adoption`, `next-cache-components-optimizer`,
  `next-partial-prefetching-adoption` 네 스킬이 모두 16.3 을 하한선으로 두고 있어,
  이 항목이 끝나기 전까지 호출할 수 없습니다.
  자세한 내용은 `.claude/skills/dev-cycle/references/frontend-skills.md` 에 있습니다.
- [ ] `next-upgrade` 스킬로 공식 마이그레이션 가이드와 코드모드를 적용
- [ ] `eslint-config-next` 를 같은 버전으로 맞춤
- [ ] `npm run build`, `npm run type-check`, `npm run lint` 통과 확인
- [ ] vitest 전체 통과 확인
- [ ] `next-dev-loop` 의 preflight 가 통과하는지 확인해 문턱이 실제로 열렸는지 검증
- [ ] `frontend-skills.md` §1 의 실측 표를 갱신

### [JONGGA-001] generator.py 의 인라인 페이즈 로직을 phases 모듈로 교체
- 카테고리: 종가베팅 | 티어: T3 | 근거: CLAUDE.md 이관
- [ ] `engine/generator.py` 의 인라인 페이즈 로직 범위 확정
- [ ] `engine/phases_*.py` 의 기존 클래스로 대체
- [ ] 신호 생성 결과가 교체 전후로 동일한지 확인
- [ ] 회귀 테스트 추가

### [INFRA-004] 여섯 개 카테고리 감사로 백로그를 채운다
- 카테고리: 인프라 | 티어: T1 | 근거: 최초 요청의 카테고리별 검토 단계
- `dev-workflow` 에이전트를 카테고리마다 한 번씩 돌려 감사 리포트와 항목 초안을 받습니다.
  에이전트는 코드를 고치지 않으므로 이 항목 자체의 산출물은 문서뿐입니다.
- 현재 백로그에 챗봇과 VCP 항목이 하나도 없는 것은 두 카테고리를 아직 감사하지 않았기
  때문입니다. 이 항목이 끝나야 카테고리별 개선을 시작할 수 있습니다.
- [ ] 챗봇 감사
- [ ] 종가베팅 감사
- [ ] VCP 시그널 감사
- [ ] 수급·백테스트 감사
- [ ] 프론트엔드 공통 감사
- [ ] 인프라·패키지 감사
- [ ] 여섯 리포트에서 나온 항목 초안을 중복 제거하고 우선순위를 매겨 `TODO.md` 에 반영
- [ ] 감사 리포트는 `docs/dev-cycle/audits/` 에 남김

## P2 — 대기

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
