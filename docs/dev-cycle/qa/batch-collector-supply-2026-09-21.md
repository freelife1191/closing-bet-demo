# UltraQA Report

대상: INFRA-030 / FLOW-014 · 구현 커밋 cb51702 · 티어 T3.
engine=ultraqa, lifecycle=app-adapted, phase=complete, iteration=2, same_failure_count=0, cleanup=complete.
브라우저 required, 사용자 지정 ego-browser Space16/p1, 1280×1000 데스크톱.
검증된 제품·계획29경로 SHA 목록은 `review-frozen.json`(aee99f...f11a3)이며,
원본 작업 트리·검증 scratch·구현 커밋의 일치를 정리 전에 확인했다.

## 목표·완료 조건·경계

공개 수집기 단일화와 과거 날짜 계약을 보존하고 개인 수급0/자료없음, 조회 경합 및 대량 대기
개선을 실제 수정 코드로 검증한다. 필수9행·baseline·증거·정리가 모두 통과했다.
한도는 최대5cycle/동일실패3회다. 개발 TDD 실패와 브라우저 QA cycle을 분리해 기록했다.
원본3500/5501/live, 실제 .env/data, 실제 인증·LLM·시장 수집·설정저장·계좌변경·삭제는 사용하지 않았다.
원시 합성 공급자 → 실제 parser/service/SQLite → 합성 Flask HTTP → 실제 Next UI를 검사했다.
인증·외부 공급자·HTTP 라우트 껍질은 대체됐으며 운영 end-to-end나 시장 API 속도를 검증한 것은 아니다.

## 필수 행렬

| ID | 의도·사용자/오류 모델 | 실행·기대 | 실제·증거 | 판정 |
|---|---|---|---|---|
| Q1 | 운영 호출자·import 순서 | 공개/하위 클래스·과거 날짜·설정 경로 계약 유지 | package/collector 회귀와 service-first subprocess; 최종 전체2449에 포함 | PASS |
| Q2 | 정상·누락·잘못된 개인 값 | 0,+1억,-1억,None을 구분, 역산 없음 | 실제 parser+서비스의6모드와 개인 날짜/숫자 회귀 | PASS |
| Q3 | 구형·신형·손상 캐시 | 구형0→None, 새0→0, 외국인기관보존 | reference/collector/detail cold SQLite 회귀 및 fixture6모드 reread | PASS |
| Q4 | 중복·느린 작업·clear | 같은key1회,60초후재시도,구세대publish0회 | Event/Future/가상clock, 경로 분리, 대기자 해제, 실패LRU검사 | PASS |
| Q5 | 대량 cutoff·중복 후보 | 범위밖조회0회,결과·순서동일 | 가격19행·max0/음수·VCPfalse·중복ticker·순차대조 | PASS |
| Q6 | 느린 공급자 | 600×50ms,각방식3회,동일결과·최대4·중앙값50%이하 | 35.673345→9.883845초,비율0.277065,각600호출·digest동일 | PASS |
| Q7 | 실제 사용자 화면 | 0/+1억/-1억/누락/invalid/legacy의API·표시일치 | ego-modes.json 6/6; 모든모드 외국인+10억/기관+5억보존; 화면8PNG직접열람 | PASS |
| Q8 | 조회 실패·복구 | 모달닫기/재열기,페이지reload없이503→정상 | 합성조회실패 문구→+1억,같은performance.timeOrigin,ego-recovery.json | PASS |
| Q9 | misleading success·dirty파일·잔재 | Next오류0·소유자원종료·기존package유지 | Next두진단빈배열,로그51개SHA,Spacefinish1회,3포트닫힘,scratch제거 | PASS |

## 실행과 정적 검증

baseline: pytest2422/3skip, Vitest629. 최종: pytest2449/3skip, Vitest634/83파일,
build3/3, typecheck exit0, lint0오류184경고. skip은 수동Gemini2건과 실제.env없는환경1건이며
필수 시나리오 성공으로 세지 않는다. 명령·종료코드·시각·timeout은 동일이름 JSON에 보존했다.

- pytest 최종: `pytest-import-repair.json`, 180초한도, exit0.
- 프론트엔드: `vitest-final.json`, `build-integrated.json`, `typecheck-final.json`, `lint-final.json` 모두exit0.
- 성능: `bench-final.json`, 6개자식각60초/전체240초한도, exit0. 요청수는 최초600개를 유지하며 대기를 줄였다.
- fixture: `fixture-cycle2-preflight.json`, 실제Flask handler·parser·SQLite6모드와 금지mutation405, exit0.
- 최종 증거 대조: `verify_evidence.py`, source/scratch/commit29경로 및로그51개SHA확인.

원시 로그는 `<원래이름>.log.gz`에 보존했다. `log-index.json`의 원문SHA/바이트가 압축해제 결과와
일치한다. 최종 diff도 `review-diff.txt.gz`와 무결성 기록으로 보존한다.

## 발견과 보완

개발 TDD에서 공개 KRX identity, import순환, 개인값삭제/구형0, TTL/clear/data_dir혼합,
batch API/cutoff, UI0/None을 재현하고 수정했다. 기존 테스트 기대 변경은 승인한0/None계약에
한정한다. 제거한 private테스트24개와 대체 실행 계약은 `retired-tests.md`에 남겼다.

코드 리뷰가 날짜유실/개인날짜집합 불일치와 import그룹을 지적해 수정했다. 이후 상세 캐시의
비정수와 KRX 캐시의 잘못된 개인값도 RED로 재현해 공용 decoder로 보완했다. 공통 helper를
정리하다 logger가 import보다 앞에 놓여 수집오류55건과fixture실패가 생겼다. 실패 원문을
보존하고 고친 뒤 전체2449/3skip과fixture를 다시 검증했으며 오래된GREEN으로 대체하지 않았다.

구조 리뷰의056080 fallback회귀 주장은 비실사용 모듈형과 실사용legacy를 혼동한 것이었다.
기준 소스와 실제 호출자로 재대조해 reviewer가 BLOCK을 철회했다. 이를 제품 수정으로 보고하지 않는다.

QA cycle1에서는 여섯개 개인 값은 맞았지만 마지막 snapshot root에CSS를 준 호출형식 오류가 났다.
또 구형fixture에는 확정5일필드가 빠져 외국인·기관 대조값이 달랐다. 제품은 변경하지 않고
snapshot호출을 교정하며 실제서비스로 확정필드를 넣어구형cache를 만들었다. fixture별 고유
cache epoch를 추가해 preflight잔재를 재사용하지 않게 했다. 같은Space16을 유지하고 cycle2에서
6모드를 모두 다시통과했다. cycle1자료는 별도폴더와 relocation기록으로 보존한다.

## 리뷰·정리·제한

ponytail2개삭제제안 반영 → code-review APPROVE → architect CLEAR → T3 APPROVE.
생성한독립코드/심층레인과 기존독립에이전트의architecture역할 검토를 사용했다. 신규구조레인생성은
thread limit으로 거부되어 기존에이전트에 배정했으며 전용새호출성공으로 주장하지 않는다.
T3는 App-safe 체크리스트+native 적대적검토, 테스트/fixture는summary mode였다.
외부gstack/ClaudeCLI·LSP·홈기록·텔레메트리 및 OMX상태는 실행하지 않았다.

Gateway77응답 중 API52건(200:49, 예상503:3), 금지브라우저mutation0, 예상외API실패0.
합성fixture로그의405는 별도경계프로브이며 원본라우트에 보낸 것이 아니다.
Next진단 configErrors/sessionErrors/issues 모두빈배열. DOM 오류·console.error 계측도빈배열이며
예상HTTP503 자체를 성공응답이라고 표현하지 않는다.

Space16을 finish({keep:[]})로정확히한번닫았다. 소유PID/cwd/PGID확인후서버종료,
57940/57941/57942닫힘, scratch제거, 원본venv존속과 사용자packageSHA보존을확인했다.
화면판정은 개인수급영역의 데스크톱 실측이며 전체앱/모바일미관감사는 아니다.
개별HTTP요청의 전체deadline과 전역여러프로세스 동시성제한은 이번에추가하지 않았다.

## 최종 판정

ULTRAQA COMPLETE: Goal met after 2 cycles (App-adapted).
필수9/9와정리통과. [증거 폴더](../evidence/collector-supply-20260921/verify_evidence.py).
