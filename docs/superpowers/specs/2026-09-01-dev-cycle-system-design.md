# dev-cycle 개발 사이클 운영 체계 설계

작성일: 2026-09-01
상태: 승인 대기
분류: architectural (하위 프로젝트 A)

## 1. 배경

이 저장소는 파이썬 약 11.6만 줄(테스트 포함, pytest 1,515개)과 TypeScript 약 1.77만 줄
(vitest 160개)로 이루어져 있다. 챗봇, 종가베팅, VCP 시그널, 수급·백테스트, 모의투자가 한
저장소 안에 공존하며, `closing-bet/page.tsx` 2,680줄이나 `scripts/init_data.py` 2,712줄처럼
단일 파일이 비대해진 지점이 여럿 있다.

개선 작업을 진행할 절차 자체는 이미 자산으로 갖추어져 있다. `autoplan`, `simplify`,
`code-review`, `review`, `ponytail-review`, `qa`, `agent-browser` 가 모두 사용 가능한 상태다.
그러나 이들을 어떤 순서로 엮을지, 어떤 작업에 어디까지 적용할지, 완료된 작업을 어디에 기록할지를
정한 규약이 없다. 그 결과 작업이 즉흥적으로 시작되고, 진행 이력은 커밋 로그에만 흩어져 남는다.

기존 `docs/plans/TO_DO_LIST.md` 는 25줄 분량으로 KIS API 연동 항목만 담은 채 사실상 방치되어
있고, `CLAUDE.md` 의 "Remaining Refactoring Tasks" 섹션이 또 다른 백로그 역할을 겸하고 있어
관리 지점이 이중으로 존재한다.

## 2. 목표

- 작업 단위를 TODO 항목으로 명시하고, 그 항목을 정해진 절차로 완주시키는 규약을 만든다.
- 리뷰와 검증의 강도를 변경 규모와 위험도에 따라 자동으로 정한다.
- 완료된 작업을 월별 요약과 일별 상세라는 두 층위로 기록하고 백로그에서 제거한다.
- 백로그의 관리 지점을 한 곳으로 통합한다.
- 새로 작성하는 코드를 최소화한다. 기존 스킬을 엮는 규약과 문서만으로 구성한다.

## 3. 비목표

- 새로운 리뷰 로직이나 테스트 프레임워크를 만들지 않는다. 기존 자산을 순서대로 호출할 뿐이다.
- `code-simplifier` 플러그인을 설치하지 않는다. CLI 내장 `/simplify` 가 같은 역할을 하며
  수정 적용까지 수행한다.
- 티어 판정을 자동화하는 스크립트를 만들지 않는다. 판정은 계획 단계의 판단이므로 코드가
  개입할 여지가 없다.
- 아카이브 통계를 집계하는 스크립트를 만들지 않는다. 항목이 수십 개 쌓여 손으로 세기
  번거로워질 때 추가한다.
- 외부 이슈 트래커와 연동하지 않는다. 마크다운 파일로 충분하다.
- 이 스펙은 하위 프로젝트 A(운영 체계 구축)만 다룬다. 카테고리별 감사(B), 개선 실행(C),
  패키지 업데이트(D)는 각자 별도의 스펙과 계획을 갖는다.

## 4. 리뷰 자산의 역할 구분

다섯 자산은 서로 다른 축을 담당하며 상호 대체되지 않는다.

| 자산 | 소재 | 검사 축 | 수정 적용 |
|---|---|---|---|
| `/simplify` | CLI 내장 | 재사용, 단순화, 효율, 추상화 층위 정렬. 버그는 찾지 않는다 | 직접 적용한다 |
| `/ponytail-review` | ponytail 마켓 | 과잉 설계만 본다. `delete:` `stdlib:` `native:` `yagni:` `shrink:` 다섯 태그로 삭제 대상을 열거한다 | 적용하지 않는다 |
| `/code-review` | CLI 내장 | 버그와 결함 탐지 | 보고 위주 |
| `/review` | gstack 전역 스킬 | 랜딩 전 구조 검토. SQL 안전성, LLM 신뢰 경계, 조건부 부작용 | 보고 |
| `/security-review` | CLI 내장 | 보안 | 보고 |

`/simplify` 는 "이 코드를 어떻게 더 낫게 쓸까"를 묻고, `/ponytail-review` 는 "이 코드가
존재해야 하는가"를 묻는다. `yagni:`(구현체가 하나뿐인 추상화)와 `native:`(플랫폼이 이미
제공하는 일을 하는 의존성) 판정은 `/simplify` 의 검사 축에 없다. 반대로 성능과 추상화 층위
정렬은 `/ponytail-review` 가 명시적으로 범위 밖에 둔다.

실행 순서에서 `/ponytail-review` 를 `/simplify` 앞에 둔다. 지울 코드를 먼저 걷어내야 곧
사라질 코드를 정성껏 다듬는 낭비가 생기지 않는다.

## 5. 산출물

| 경로 | 역할 |
|---|---|
| `.claude/skills/dev-cycle/SKILL.md` | 사이클 오케스트레이터. 게이트 관리와 기록 갱신을 담당한다 |
| `.claude/skills/dev-cycle/references/tier-rules.md` | 티어 판정 규칙과 위험 경로 목록 |
| `.claude/skills/dev-cycle/references/archive-format.md` | TODO 및 아카이브 기록 형식 |
| `.claude/agents/dev-workflow.md` | 감사·조사 전담 서브에이전트 |
| `docs/dev-cycle/TODO.md` | 백로그 (단일 관리 지점) |
| `docs/dev-cycle/archive/YYYY-MM.md` | 월별 요약 |
| `docs/dev-cycle/archive/daily/YYYY-MM-DD.md` | 일별 상세 |
| `CLAUDE.md` | dev-cycle 섹션 추가, 기존 백로그 섹션 이관 |
| `.gitignore` | `docs/` 를 `docs/*` 로 바꾸고 `dev-cycle`, `superpowers` 를 예외로 되살린다 |

`.claude/skills/` 아래에 두는 이유는 이 규약이 저장소 고유의 위험 경로 목록과 파일 구조에
의존하기 때문이다. 전역 스킬로 두면 다른 프로젝트에서 오작동한다.

`.gitignore` 90번 줄이 `docs/` 를 통째로 제외하고 있어, 기록 파일과 스펙 문서가 버전 관리
밖에 놓인다. 디렉터리 전체를 제외한 패턴은 하위 경로를 부정 패턴으로 되살릴 수 없으므로
`docs/*` 로 바꾸고 두 경로만 예외로 지정한다. 이미 추적 중인 48개 파일과 나머지 하위
디렉터리의 무시 상태는 그대로 유지된다.

## 6. 사이클 절차

    /dev-cycle next          (또는 /dev-cycle INFRA-001)

    [0] 준비   TODO.md 에서 항목 선택 (P0 → P1 → P2, 동순위는 상단 우선)
               git 작업 트리가 깨끗한지 확인하고, develop 브랜치에서 시작한다

    [1] 계획   autoplan 으로 실행 계획 수립
               변경 예상 범위로 티어 판정
               ⏸ 게이트 1 — 계획과 티어를 승인받는다

    [2] 구현   계획대로 구현한 뒤 티어별 리뷰를 순서대로 실행
               T1  /simplify
               T2  /ponytail-review → /simplify → /code-review
               T3  T2 전체 + /review
                   인증·시크릿 접촉 시 /security-review 추가
               지적 사항을 반영한다

    [3] 검증   T1  변경 범위의 pytest / vitest
               T2  pytest / vitest 전체 + agent-browser 로 변경 화면 실측
               T3  pytest / vitest 전체 + qa 스킬 전체 시나리오

    [4] 마감   ⏸ 게이트 2 — 커밋 메시지와 아카이브 기록을 승인받는다
               커밋 → TODO 항목 제거 → 일별 상세 기록 → 월별 요약 한 줄 추가

승인 게이트는 두 곳뿐이다. 계획이 확정되는 시점과 결과가 저장소에 남는 시점이며, 되돌리는
비용이 가장 큰 두 지점에 해당한다.

## 7. 티어 판정 규칙

| 티어 | 조건 |
|---|---|
| T1 경량 | 변경 50줄 이하이면서 위험 경로에 닿지 않는다. 문서, 상수, 라벨, 스타일이 해당한다 |
| T2 보통 | 변경 300줄 이하이면서 위험 경로에 닿지 않는다 |
| T3 중량 | 변경 300줄을 초과하거나, 위험 경로에 한 줄이라도 닿는다 |

위험 경로는 이 저장소의 실제 파일 기준으로 다음과 같다.

- 신호·등급 결정: `engine/grade_*.py`, `engine/generator*.py`, `engine/phases.py`
- VCP 판정: `engine/vcp_ai_analyzer*.py`
- 모의투자 계좌와 거래: `services/paper_trading*.py`
- 수급 집계: `services/investor_trend*.py`, `services/kr_market_flow_service.py`
- 스케줄러와 데이터 적재: `app/services/scheduler.py`, `scripts/init_data.py`
- 시크릿과 인증: `.env*`, `secrets/`
- 저장소 스키마: 파일명에 `sqlite` 를 포함하는 모듈

티어는 계획 단계에서 판정하되, 구현 후 실제 diff 가 상위 티어에 해당하면 상향만 허용하고
하향은 금지한다. 리뷰를 줄이려고 티어를 낮추는 일을 구조적으로 막기 위해서다.

## 8. 기록 형식

### 8.1 백로그 (`docs/dev-cycle/TODO.md`)

    ## P0 — 즉시

    ### [INFRA-001] 파이썬 의존성 버전 고정
    - 카테고리: 인프라 | 티어: T3 | 근거: AUDIT-INFRA §1
    - [ ] requirements.txt 버전 핀 적용
    - [ ] google-genai 2.x 호환성 확인
    - [ ] 회귀 테스트 확인

항목 ID 는 `카테고리 약어 - 일련번호` 형식을 쓴다. 카테고리 약어는 `CHAT`(챗봇),
`JONGGA`(종가베팅), `VCP`(VCP 시그널), `FLOW`(수급·백테스트), `FE`(프론트엔드),
`INFRA`(인프라·패키지) 여섯 가지다. 일련번호는 카테고리별로 독립 증가하며 재사용하지 않는다.

우선순위는 `P0`(즉시), `P1`(이번 주기), `P2`(대기) 세 단계다.

### 8.2 일별 상세 (`docs/dev-cycle/archive/daily/YYYY-MM-DD.md`)

    ## [INFRA-001] 파이썬 의존성 버전 고정
    - 완료 2026-09-01 14:32 | 티어 T3 | 커밋 abc1234, def5678
    - 변경: requirements.txt, engine/genai_client.py (+42 -18)
    - 리뷰: ponytail-review(net -12) · simplify(3건 적용) · code-review(0건) · review(1건 반영)
    - 검증: pytest 1515 통과 · vitest 160 통과 · qa 헬스 99
    - 메모: google-genai 2.x 에서 GenerateContentConfig 시그니처가 바뀌어 대응했다

### 8.3 월별 요약 (`docs/dev-cycle/archive/YYYY-MM.md`)

    | 완료일 | ID | 제목 | 카테고리 | 티어 | 커밋 |
    |---|---|---|---|---|---|
    | 09-01 | INFRA-001 | 파이썬 의존성 버전 고정 | 인프라 | T3 | abc1234 |

    ## 통계
    - 완료 12건 (P0 3 · P1 5 · P2 4)
    - 순 코드 증감 -340줄

두 파일 모두 게이트 2 를 통과한 직후에 즉시 기록한다. 월말에 몰아서 집계하는 배치 작업은
두지 않는다. 해당 날짜나 월의 파일이 없으면 그 시점에 새로 만든다.

## 9. dev-workflow 에이전트

이 에이전트는 사이클을 실행하지 않는다. 독립 컨텍스트에서 감사와 조사만 수행하고 TODO 항목
초안을 돌려주는 역할을 맡는다.

- 입력: 카테고리 이름 하나 (챗봇, 종가베팅, VCP, 수급·백테스트, 프론트엔드, 인프라)
- 출력: 감사 리포트와 `TODO.md` 형식에 맞춘 항목 초안
- 분리하는 이유: 감사는 수십 개 파일을 읽어야 하는데, 그 내용이 메인 세션의 컨텍스트를
  잠식하면 정작 사이클을 끝까지 실행할 여유가 사라진다.

하위 프로젝트 B(카테고리별 감사)는 이 에이전트를 카테고리마다 한 번씩, 모두 여섯 번
호출하는 방식으로 진행한다.

## 10. CLAUDE.md 갱신

기존 내용은 유지하고 다음 섹션을 추가한다.

    ## 개발 사이클 — dev-cycle

    작업은 `docs/dev-cycle/TODO.md` 의 항목 단위로 진행한다.
    `/dev-cycle next` 로 시작하며, 절차와 티어 규칙은 스킬 정의를 따른다.

    - 백로그: docs/dev-cycle/TODO.md
    - 완료 기록: docs/dev-cycle/archive/ (월별 요약 + 일별 상세)
    - 티어와 위험 경로: .claude/skills/dev-cycle/references/tier-rules.md

    TODO 에 없는 작업을 즉흥으로 시작하지 않는다. 새로 발견한 개선점은
    TODO.md 에 항목으로 추가한 뒤 순서에 따라 처리한다.

아울러 기존 "Remaining Refactoring Tasks" 섹션의 세 항목(`market_gate.py` 리팩토링,
`generator.py` 리팩토링, 타입 힌트 보강)을 `TODO.md` 로 이관하고, CLAUDE.md 에는 포인터만
남긴다. 같은 백로그가 두 곳에 존재하면 반드시 어긋난다.

`docs/plans/TO_DO_LIST.md` 의 KIS API 연동 항목도 `TODO.md` 로 이관하고 원본 파일은
삭제한다.

## 11. 성공 기준

1. `/dev-cycle next` 를 호출하면 TODO 항목 하나가 계획부터 아카이브 기록까지 완주하며,
   그 과정에서 승인을 요청하는 지점이 정확히 두 곳이다.
2. 티어 판정 결과에 따라 실제로 호출되는 리뷰 자산과 검증 범위가 달라진다.
3. 완료된 항목이 `TODO.md` 에서 사라지고 일별 상세와 월별 요약 두 곳에 모두 남는다.
4. 백로그가 `docs/dev-cycle/TODO.md` 한 곳에만 존재한다.
5. 새로 추가된 실행 코드가 없다. 산출물은 스킬 정의, 에이전트 정의, 레퍼런스 문서,
   기록 파일뿐이다.

## 12. 이후 순서

이 스펙이 승인되면 A 를 구현한다. 완료 후에는 D(패키지 업데이트)를 이 체계의 첫 실전
검증 사례로 삼고, 이어서 B(카테고리별 감사)와 C(개선 실행)로 진행한다. 각 하위 프로젝트는
자기만의 스펙과 계획을 따로 갖는다.
