# UltraQA Report

- 항목: FE-043, JONGGA-030, FLOW-006. 사용자 2026-09-21 「승인」에 따른 연속 묶음.
- engine: ultraqa; lifecycle: app-adapted; phase: complete; iteration: 3; same_failure_count: 0.
- browser_applicability: required; browser_driver: ego-browser; Space11/p1.
- 구현 기준: `fcf440a`, 제품·테스트32파일 SHA는 `../evidence/quota-ticker-20260921/review-frozen.json`.
- 목표: 비JSON 사용량 응답을 통제된 실패로 처리하고 복구하며, 가격 생산자·소비자의 티커를 통일하고 백테스트 공개 API/계산을 보존한다.
- 완료 조건: 정적 검사·필수행렬·독립리뷰·증거·소유자원 정리 모두 통과. 같은 실패3회/전체5회 중단.
- 안전 경계: 원본3500/5501/live와 실제.env/data 접근 금지. 실제 수집·LLM·인증·설정저장·충전·삭제·거래 금지. 테스트/import는 비밀 없는 git archive scratch에서만 실행하고 sandbox로 원본쓰기/data/env읽기 및 외부네트워크 차단.

## 실행 행렬

모든 증거 경로는 `../evidence/quota-ticker-20260921/` 기준이다.

| ID | 의도·사용자/적대적 모델 | Setup 및 실제 실행 | 기대와 실제 결과 | 수정·증거 | Cleanup | 필수 |
|---|---|---|---|---|---|---|
| S1 | 기존 기능 회귀 | scratch runner pytest/Vitest/lint/build | PASS: pytest2422/3skip, Vitest629, lint0오류184경고, build/typecheck3/3 | `validation-final.json`, `pytest-review-fixed`, `vitest-review-fixed`, `lint-review-fixed`, `build-review-typed` 로그/JSON | 프로세스 종료 | 예 |
| Q1 | 오류 응답을 받는 사용자 | 실제 VCP 화면 Sidebar와 설정 모달, HTML502/404/200 및 JSON401/403/500 | PASS: 양쪽 모두 사용량 조회 실패 표시, 원문 JSON SyntaxError·페이지/console 오류0 | `ego-quota-modes.json`, `ego-{mode}.json`, `ego-settings-error.png` | Space 종료 | 예 |
| Q2 | 동일 화면 실패·복구 | fixture mode 제어 후 실제 설정 닫기/열기; 3회 정상→HTML502→8회 정상 | PASS: 기존3회는 실패시 사라지고 오류 표시; 회복후8회/2사용 표시. 초기 실패도 확인 | `ego-recovery.json`, `ego-quota-recovered.png` | Space 종료 | 예 |
| Q3 | 누락/잘못된 숫자, 세션 경합 | Vitest 실제 소비자/hook, HTML200·빈값·숫자문자열·0limit, A→B/로그아웃/같은identity역순·loading | PASS: 파싱/shape 실패 제어, 신원·generation 경계 유지, pending에서 기본10회 표시 없음 | `target-quota-*`, `target-loading-red`, `vitest-review-fixed`, `target-review-typed` | runner 종료 | 예 |
| T1 | 잘못된 티커가 남의 가격을 참조 | pytest None/pd.NA/0/음수/NaN/inf/날짜/비정수/Unicode/PathLike 및 실제 CSV/backtest | PASS: invalid 키 제외; 5930·정수float·A005930·005930.KS·0007c0 정상화. 기존 허용 문자열 추출 계약은 보존 | `pytarget-ticker-*`, `pytarget-stats-*`, `pytest-review-fixed` | 임시 데이터 정리 | 예 |
| T2 | 구형/충돌 캐시 | 합성 SQLite lower/unpadded와 동률canonical, JSON공백alias충돌 | PASS: 최신timestamp 우선, 동률raw canonical 우선; JSON canonical/lexical 선택. 원본DB재작성 없음 | `pytarget-canonical-red`, `test_kr_market_ticker_normalization.py`, `fixture-expanded`, 전체pytest | 임시 DB 제거 | 예 |
| B1 | 실제 화면 가격·성과 흐름 | 원시 혼합ticker DataFrame→실제 가격/백테스트함수→합성 HTTP→실제 VCP·종가·누적 UI | PASS: VCP0007C0/15200/+15.2%; 종가raw0007c0·신호일종가14000; 누적canonical0007C0·WIN/+5.0%·1건 | `ego-vcp`, `ego-jongga`, `ego-cumulative`, `ego-cumulative-row` JSON/PNG, `fixture.py` | 서버/Space 종료 | 예 |
| B2 | 기존 보유 종목의 가격 소비 | 실제 모의투자 보유종목 UI; synthetic raw0007c0/3주와 실제 valuation helper | PASS: 현재15200·평가45600·+8.57%·총자산103600, 저장ticker소문자 유지. 평가/자산합계 경계102단위검사도통과 | `ego-portfolio.json`, `ego-portfolio-stable.png`, `pytarget-valuation-authority-green` | 거래 버튼 미실행, 임시 데이터 제거 | 예 |
| C1 | 소유권·중단·허위성공 방지 | 원본package SHA, 리뷰32SHA, 로그exit/skip, PID/cwd/PGID, 포트와scratch/Space종료 확인 | PASS: 사용자파일동일, source/scratch일치, 57930~32닫힘, scratch제거, venv존속, finish1회 | `source-verification.json`, `request-audit.json`, `cleanup.json`, `ego-finish.json` | 완료 | 예 |

**필수 9/9 PASS. ULTRAQA COMPLETE: Goal met after 3 cycles**

## 명령·검증 결과

- 실행 명령·cwd·PID·시각·timeout·exit은 runner의 JSON별 기록. Python target120초/전체180초, Vitest300초, lint120초, build240초. 모두 최종exit0이고 timeout없음.
- pytest 2422 passed, 3 skipped: 수동 Gemini 외부통합2, 실제.env 부재1. 실사용API 성공으로 세지 않았다.
- Vitest629/83files PASS. 최종 테스트 타입 보완후 해당8검사와 build/typecheck3PASS를 추가 확인했다. 제품코드 변경 없는 타입 보완이었다.
- lint0errors/184warnings. 이전 기준188보다감소했으나 남은 경고가 모두 기존이라고 주장하지 않는다.
- Next MCP `get_errors`: configErrors/sessionErrors 빈 배열, `get_compilation_issues`: issues 빈 배열. `next-final-*.txt`.
- 실제 브라우저 오류 기록은 최종6모드 각각빈배열, 최종페이지도빈배열. 최초 계측없던 null 결과는 `ego-html-404-incomplete.json`에 남기고 PASS 증거에서 제외했다.
- PNG9개를 리더가 `view_image`로 직접 확인했다. 첫 portfolio이미지는전환중이므로 최종판정은 stable이미지. 데스크톱만 확인했으며 모바일 전체디자인감사를 주장하지 않는다.

## 실패 원인과 보완

- 계획critic REJECT(쿼터표시·shape·익명header·공용helper방향)→계약 확정→OKAY.
- 구현 검증: 잘못된 테스트 파일명 exit4는 하네스오류로 별도보존. quota RED18; 티커helper부재 collection오류와 기존함수 행동실패를분리. 누적결과의 테스트필드 ticker를실제code로수정한하네스보완도명시했다.
- 코드수정중 JSX조건식/200본문timeout회귀를검사가잡아보완했다. 화면오류문구가두곳이라단일selector테스트실패; 두위치검사로수정. 리더가수정완료전에복사한낡은테스트도재실행되어SHA대조후최신파일로교정했다. 실패기록은삭제하지않고gzip보존.
- 독립code REQUEST CHANGES: 공백alias가exact로분류됨→JSON RED1/SQLite동률계약검사→raw비교. loading기본10표시→RED2→pending표시. 동일identity역순과성공→실패회귀추가.
- architect BLOCK: 정규가격을raw보유평가가못찾음→RED2, canonical권위충돌RED1→canonical-first/rawfallback. 실제 보유·거래DB표기는바꾸지않음. 기존잘못된stale동작을고정하던테스트는승인한가격호환계약에맞춰갱신했고별도신규회귀로보강했다.
- 신규loading테스트nullable타입누락이build를막음→명시TestSessionState union→build/typecheck재통과. 타입억제없음.
- 최종리뷰: ponytail CUT1반영, code APPROVE, architect CLEAR, T3deep APPROVE. App-safe native읽기전용심층검토이며 별도gstack외부런타임·LSP성공을주장하지않음.
- 동적cycle1: gateway의이전scratch prefix guard로기동실패/브라우저연결거부. namespace만교정하고같은Space11재사용.
- cycle2: ego role locator에이름누락과CDP오류기록기가round종료후새문서에없던하네스문제. 유효CSS/이름locator와동일round내계측등록·reload로교정. null을오류0으로간주하지않음.
- cycle3: 6응답모드·동일페이지복구·가격/성과/평가화면과Next진단 모두PASS. 제품수정은없었고gateway하네스만교정했다.

## 실측의 범위와 정리

- 실제 React 화면과 수정된 Python 가격·CSV·SQLite·백테스트·평가함수를 합성 HTTP wrapper로 연결했다. 원래 서비스의 인증·LLM·외부시장·실제계좌/저장설정은 검사하지 않았다. 프로필·환경저장,충전,매수/매도,삭제버튼을누르지않았다.
- fixture전체207요청에는제어와경계거부probe가포함된다. gateway API157요청중132개200, 나머지는예상quota오류502/404/401/403/500. quota외API실패0, 금지browser mutation0. 요청자격증명/쿠키/원본env값은수집하지않았다.
- 종료전제품32SHA와scratch일치, 사용자package해시불변. 소유PID43249/48671/43171만현재cwd/PGID확인후종료; 이전소유PID3346/95303도교체전종료기록보존. gateway최초95355는guard실패로이미종료.
- scratch삭제, 원본venv보존, 포트57930/57931/57932 listener없음. ego.finish({keep:[]})1회로Space11닫힘. OMX모드미활성, state read/write/clear미실행.
- 원본자료 전체불변을 포괄적으로 주장하지 않는다. 이번 라운드에서 원본실행/import/서비스요청은하지않았으며, 이전 라운드의 별도실행편차를 소급해해결했다고주장하지않는다.

## 잔여 범위

원본 과거 사용자 제보의 요청URL/시각은 없어 당시 운영 원인까지 확정하지 않는다. 이번에 실제재현한 quota HTML응답 경로를고쳤다. 구형 yfinance 실패캐시 alias복원, 기존data정리와별도남은TODO는이범위에포함하지않았다. 원본서비스배포/재시작/푸시는수행하지않았다.
