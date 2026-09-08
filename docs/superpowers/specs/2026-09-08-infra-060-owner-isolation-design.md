# INFRA-060 모의투자 계정 분리 설계

사용자는 이 대화에서 로그인 전용·기존 공용 자료 보존·각 개인 계정 모의자금 1억 원 시작을 설명받고 「진행해」로 승인했다. 승인된 같은 내용을 구체화한다.

## 신원과 인터페이스

기존 NextAuth → proxy의 X-Auth-Identity 서명 → Flask verify_identity_header를 재사용한다. 서버는 검증된 이메일만 owner_id로 정하며 body/query/X-User-Email/X-Session-Id는 소유권 근거가 아니다. 익명·위조·만료 서명은 포트폴리오 GET 3개와 POST 5개 모두 서비스/DB/동기화 접근 전에 401로 거부한다. 응답의 기존 데이터 필드 형태는 유지한다.

공용 PaperTradingService와 단일 시세 동기화 루프를 유지한다. 계정 public API에 필수 keyword-only owner_id를 전달하며 사용자 누락 폴백이나 singleton 현재 사용자 필드를 만들지 않는다. 사용자별 객체·스레드를 무한 생성하지 않는다.

## 저장·마이그레이션

balance는 사용자당 한 행, portfolio는 (owner_id,ticker), asset_history는 (owner_id,date), trade_log는 소유자 필터/인덱스를 갖는다. 기존 행은 예약 소유자 __legacy_unassigned__로 보존하고 계정 public API는 이 소유자 접근을 거부한다. 누구에게도 자동 승계하지 않는다. 새 소유자의 초기화는 INSERT OR IGNORE와 INITIAL_CASH_KRW=100_000_000을 사용한다.

기존 price_cache도 사용자 체결 가격이 섞였으므로 legacy_price_cache에 보존하고 새 활성 price_cache는 빈 상태로 시작한다. 시세 공급자 결과만 공용 메모리/DB 캐시를 갱신하며 buy/bulk/sell의 입력 가격은 그 캐시에 쓰지 않는다. 거래 가격은 자기 계정 거래 내역/매입 원가에만 반영한다.

계정 스키마와 가격 캐시 전환은 하나의 BEGIN IMMEDIATE 트랜잭션으로 수행하고 실패 시 전체 rollback한다. 재실행·동시 초기화가 행을 유실하거나 legacy 가격을 다시 활성화하지 않는다. 운영 DB 적용은 이번 개발 범위가 아니며 임시 DB에서만 migration을 검증한다.

## 계정 연산·화면

잔고·입금·포지션·거래 로그·자산 이력·평가·기간 조회·reset의 모든 SQL에 owner_id를 바인딩한다. 잔고 조건부 차감, 보유 수량 검사와 로그는 같은 거래 트랜잭션으로 유지한다. snapshot 메모리는 기존 단일 슬롯을 유지해도 owner_id가 일치할 때만 중복으로 판단한다. reset은 자기 행만 지우며 공용 시세 캐시는 지우지 않는다. background sync는 개인 계정 티커의 합집합을 처리하고 legacy를 제외한다.

미로그인 상태에서는 모의투자 진입점/모달에 로그인 안내를 표시하고 거래를 막는다. 종가베팅·VCP의 직접 개별/일괄매수, 모달 매수/매도·충전·reset·거래/자산 이력까지 적용한다. 로그인 사용자 변경과 늦게 도착한 이전 계정 응답이 기존 자료를 다시 표시하지 않도록 한다. 서버의 401도 명시적으로 처리한다.

## 검증과 안전

임시 SQLite, bare Flask+Blueprint, mock 시세를 사용해 A/B 동일 티커·모든 연산·동시 거래·legacy 보존·마이그레이션 재실행/rollback·가격 캐시 오염·신원 위조·UI 계정 전환을 검증한다. 원본 .env·data와 운영/로컬 Next3500·Flask5501 및 live URL에 접근하지 않는다. 실제 거래·알림·LLM·서비스 재기동·배포는 금지한다. UI 실측은 별도 mock backend만 연결한 격리 서버로 한다.

T3 계획 critic → ponytail → 독립 code-review 두 레인 → 심층 review·인증 보안 검토 → 정적 검사 → 첫 커밋(TODO 유지) → App 대응 UltraQA → 완료 아카이브를 따른다.
