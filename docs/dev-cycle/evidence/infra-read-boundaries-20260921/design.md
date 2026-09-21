# 조회·감사·기동 경계 설계

2026-09-21 사용자 요청은 연관 TODO 연속 진행과 승인 판단 위임이다. 리더가 아래 설계와 계획을 검토·결정한다. 별도 사용자 승인 발언을 만들어 기록하지 않는다.
brainstorming architectural/T3: INFRA-045·046·047을 함께 처리한다.

## 목표

조회 GET이 새 외부 작업을 시작하지 않고, 감사 로그는 위조 가능한 전달 헤더를 사용자 IP로 오인하지 않는다.
실제 프록시 구성은 추정하지 않는다. 감사 IP를 Flask가 직접 관측한 연결 상대(remote_addr)로 정의한다. 실제 사용자 IP를 보장하는 필드가 아니다.
Flask-only Procfile은 저장소가 지원하는 배포 경로에서 제거한다. 이 로컬 변경은 배포/재기동하지 않는다. 실제 외부 PaaS 사용 여부는 미확인이며 자동 배포를 수행하지 않는다.

## 선택과 대안

- IP: 신뢰할 프록시 목록을 추정하는 방식 대신 세 감사 지점 모두 peer 주소만 기록한다. 실제 client IP 추적 능력을 포기하고 위조 헤더 수용을 제거한다.
- GET: 새 POST를 추가하지 않고 기존 관리자 MarketGate POST와 scheduler를 유지한다. portfolio sync는 명시적인 scheduler 기동 경로에서 시작하며 GET/lazy singleton 생성은 시작하지 않는다.
- portfolio 평가의 소유자 초기화·자산이력 저장은 현행 계약으로 유지한다. 이번 항목은 GET의 외부 호출/백그라운드 시작 차단이며 완전한 DB 무쓰기 전환을 주장하지 않는다.
- Procfile: Next 없이 Flask만 노출하는 실행 파일을 보관하는 대신 삭제하고 문서에 지원 경계를 남긴다. 별도의 PaaS 통합 실행기는 만들지 않는다.

## 변경 경로

app/__init__.py, app/routes/common_update_routes.py, services/kr_market_chatbot_request_helpers.py: 감사 IP 세 지점.
app/routes/common_portfolio_routes.py, services/paper_trading.py, services/scheduler.py: GET와 singleton 자동sync 제거, scheduler lock 획득 후 bootstrap에서 기존 start_background_sync 호출. 기존 sync lock/loop 유지.
app/routes/kr_market_system_http_routes.py: stale/empty GET은 저장값/empty 반환. 관리자 POST 그대로.
app/routes/kr_market.py, kr_market_dependency_builders.py, kr_market_route_registry.py: GET전용3함수/state/import/deps배선제거.
frontend/src/app/dashboard/kr/page.tsx: 낡은GET자동갱신주석만수정. tests/app/test_market_gate_refresh_cooldown.py 삭제, 기존공개GET/adminPOST/scheduler 회귀보존·보강.
Procfile 삭제, CLAUDE.md/.env.example 현행 설명 갱신. 관련 기존 tests 수정 및 새 경계 회귀.

## 성공 조건

위조 forwarded 헤더에도 세 감사 IP가 peer로 일치. GET portfolio 반복과 lazy 최초접근은 sync0회. scheduler 시작은 기존 sync를 명시적으로 시작.
MarketGate 최신/과거/stale/빈 GET은 trigger dependency 없이 저장값/empty를 반환; 관리자 POST와 스케줄러 유지.
격리 실제 Flask 라우트·서비스 및 Next UI/ego-browser로 대조. 전체 pytest/Vitest, ponytail→code-review/architect→T3심층/보안 검토.
원본 .env/data/logs·3500/5501/live 접근금지. 변경 적용/배포/실제 LLM/수집/거래/설정저장·원본자료삭제 안함.
연속 라운드 공유 scratch와 Space20 사용, 마지막에 소유 자원 정리 후 완료아카이브.

## 기동 시점 변경의 캐시 보존

scheduler 리더만 기동 시 singleton과 sync를 시작한다. 비리더는 첫 조회 때 singleton을 만들고 동기화를 시작하지 않는다. 이 비리더의 메모리 가격은 이후 리더가 갱신해도 낡을 수 있다.
GET에서는 외부 조회 대신 기존 `_load_price_cache_from_db()`로 공유 SQLite 가격만 갱신한다(is_running=False인 워커).
이를 두 서비스 인스턴스·하나의 임시DB로 검증해 읽기 워커에서도 동기화된 가격이 보이는지 고정한다.

## Critic 후 확정

paper sync는 모든 워커의 start_scheduler가 아니라 scheduler lock을 획득한 bootstrap에서만 시작한다. 실패해도 기존2잡/스케줄러루프는 유지한다. 리더의 매분 tagged job이 기존멱등start를 호출해 다시기동한다.
GET전용 MarketGate 자동갱신의 3함수·전용상태·deps배선·전용cooldown검사도 함께제거한다. 프론트는낡은주석만수정한다.
reader 선생성→writer가격저장→GET재로드 순서로반복가격동기화를검증한다.

공개GET 날짜 검증 누락(기존결함)을 같은조회경계에서 보완한다. None은최신, 두가지ASCII달력날짜만허용하고 나머지는파일접근전400. 생성파일명은고정prefix+검증날짜+json이어서구분자/경로이탈불가. 공용내부파일로더의다른계약은변경하지않는다.
