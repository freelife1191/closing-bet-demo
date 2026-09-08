# INFRA-060 Implementation Plan

> **For agentic workers:** 승인된 spec을 읽고 파일 소유권에 따라 TDD로 구현한다. root가 통합·리뷰·검증·커밋·마감을 맡는다.

**Goal:** 로그인 사용자의 모의투자 계정을 격리하고 기존 공용 자료를 보존한다.
**Architecture:** SQLite와 기존 서명 신원을 재사용한다. 계정 API/SQL은 owner_id를 필수로 받고 시세 캐시만 공유한다.
**Tech Stack:** Python, SQLite, Flask, Next.js 16.3.4, React 19.2.4, pytest, vitest.
**Spec:** docs/superpowers/specs/2026-09-08-infra-060-owner-isolation-design.md

## Global Constraints

로그인 전용·legacy 보존·새 계정 100_000_000. 새 의존성/운영 DB 적용/외부 요청 없음. 원본 package.json 보존. 삭제된 임시 worktree 대신 독립 clone의 develop에서 구현하고 검증한 커밋을 원본 develop에 반영한다. 원본 DB/환경 파일은 clone에 복사하지 않는다.

## Task 1: 스키마·서비스 — services/paper_trading*.py, tests/services/test_paper_trading*.py

**Interface:** get_balance/get_portfolio/get_portfolio_valuation/get_trade_history/get_asset_history, deposit_cash/update_balance/buy_stock/buy_stocks_bulk/sell_stock/reset_account, record_asset_history 계열은 기존 인자 뒤 필수 keyword-only owner_id: str를 받는다. 빈 값/예약 legacy는 거부한다.

- [x] tmp_path DB로 아래 회귀를 작성하고 실패를 확인한다.

```python
service.deposit_cash(1000, owner_id='alice@example.test')
assert service.get_balance(owner_id='alice@example.test') == 100_001_000
assert service.get_balance(owner_id='bob@example.test') == 100_000_000
```

- [x] 단일 BEGIN IMMEDIATE 안에서 기존 4개 테이블을 예약 legacy owner와 복합키/인덱스로 재구성한다. 실패 rollback과 동시 초기화 재시도를 적용한다.
- [x] 같은 트랜잭션에서 기존 price_cache를 legacy_price_cache로 보존하고 활성 캐시는 빈 테이블로 전환한다. 반복 migration/동시 init/실패 rollback 후 legacy 가격이 active cache로 로드되지 않는 검사를 작성한다.
- [x] 계정 생성은 INSERT OR IGNORE, SQL은 WHERE owner_id = ?와 파라미터 바인딩을 사용한다. reset·스냅샷 중복 판단·모든 거래 분기에 적용한다.
- [x] buy/bulk/sell이 메모리와 DB 공용 가격 캐시에 입력 체결가를 쓰지 않고 provider sync만 갱신함을 검사한다.
- [x] A/B 같은 티커·모든 계정 연산·동시 초기화/잔고차감·legacy 불변 회귀를 통과시킨다. 기존 테스트에는 명시적 owner_id를 넣고 실제 data 대신 임시 DB를 사용한다.

## Task 2: HTTP 경계 — app/routes/common_portfolio_routes.py, tests/app/test_common_portfolio*.py

**Interface:** 기존 8개 URL·payload 유지. 성공한 서명 이메일만 서비스 owner_id로 전달한다.

```python
owner_id = verify_identity_header(request.headers.get('X-Auth-Identity'))
if owner_id is None:
    return jsonify(status='error', message='모의투자는 로그인 후 사용할 수 있습니다.'), 401
```

- [x] bare Flask+Blueprint 테스트에서 익명/위조 GET·POST가 서비스에 닿지 않는 실패를 재현한다.
- [x] 공통 인증 경계를 모든 8개 route에 적용하고 owner_id를 전달한다.
- [x] 임시 DB A/B 연산과 body/query/일반 헤더 사칭·만료 서명을 검사한다. create_app/운영 서버 호출은 하지 않는다.

## Task 3: 화면 — frontend 모의투자 컴포넌트, lib/api.ts, closing-bet/VCP 거래 진입부와 해당 tests

- [x] Next 번들 client/server·fetching·error-handling 문서와 React 스킬을 읽는다.
- [x] 로그인 필요 안내·익명 거래 금지·서버401·계정 변경 시 이전 응답/자료 제거를 테스트로 고정한다.
- [x] 공통 API와 직접 거래 fetch 4곳을 점검한다. 기존 NextAuth 신원을 재사용한다.
- [x] vitest/type-check 및 mock backend를 이용한 격리 UI 실측을 수행한다.

## Task 4: 통합·마감

- [x] 구현 전 계획 critic OKAY 확인. 최초 지적(기존 캐시 전환 누락)은 Task1에 보완했다.
- [x] T3 ponytail·독립 code-reviewer/architect·review·security-review의 차단 지적을 수정한다.
- [x] 관련/전체 pytest·vitest·type-check를 격리 환경에서 수행한다. 기존 검사 부작용과 manual skip은 별도 기록한다.
- [x] App 대응 UltraQA 행렬을 작성하고 staged 신규 파일 검사 성공 후 첫 커밋을 만든다. TODO 유지.
- [ ] 정상/적대적 QA·정리·최종 검증 후 아카이브 커밋에서만 TODO를 제거한다. 검증 커밋을 원본 develop에 반영한다.
