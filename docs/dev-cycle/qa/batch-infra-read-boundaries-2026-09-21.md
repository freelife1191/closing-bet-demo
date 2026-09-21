# UltraQA Report

## 목표·실행 경계

INFRA-045/046/047: peer 감사 IP, GET 외부작업 시작 금지, scheduler리더기동과공유가격조회, 지원배포경계 정리.
engine: ultraqa; lifecycle: app-adapted; phase: complete; iteration: 2; same_failure_count: 0.
browser_applicability: required; browser_driver: ego-browser (사용자 지정), Space20/p1 연속 재사용.
Next UI + 실제 Flask 라우트/신원검증/portfolio서비스·SQLite; 인증서명/저장경로/외부 MarketGate 갱신 효과만 합성 대역.
원본 .env/data/logs·3500/5501/live/실제LLM·수집·설정·거래·삭제 금지. 소유scratch OS sandbox, 합성계정/DB만사용.
최대5cycles/동일실패3회; 명령timeout60~300초. 원본package보존. 실제PaaS배포검증아님.

## 필수 행렬

| ID | 의도·사용자 모델 | setup·command/harness | 기대 신호 | 실제 결과 | 수정 | 증거 | cleanup | required |
|---|---|---|---|---|---|---|---|---|
| I1 | 위조 forwarded 헤더 | 실제활동hook/event/chat로거에198.51.100.77 전달 | 세곳peer127.0.0.1; peer없으면None | 3종감사peer127.0.0.1,단위None검사PASS | 없음 | fixture/브라우저/pytest | batch정리완료 | yes |
| I2 | 조회 사용자·cold singleton | 실제portfolio GET반복+모달열기 | constructorautoFalse, sync/external0,71000 | constructor[false],sync0/external0,71000 | 없음 | fixture/브라우저 | batch정리완료 | yes |
| I3 | stale worker cache | reader존재후 writer72000저장→GET·모달재조회 | 72000, 총자산100002000, 외부0 | 72000·총100002000확인 | 없음 | fixture/브라우저 | batch정리완료 | yes |
| I4 | MarketGate조회 | normal/stale/empty·최신/과거반복GET | score73/73/50, updates0·external0 | normal73/stale73/empty50,갱신0 | 없음 | 실제route+브라우저 | batch정리완료 | yes |
| I5 | 관리자 경계 | 비관리자POST→403, 합성관리자POST→200 | 갱신stub1회, 실제외부0 | 403→200,합성update1·external0 | 없음 | fixture | batch정리완료 | yes |
| I6 | scheduler 장애·승계 | disabled/경합/직접·retry획득/예외/반복 bootstrap | 리더만sync, 실패해도2잡·loop유지 | 리더/실패/분당재시도 회귀통과 | 없음 | 실제scheduler회귀 | batch정리완료 | yes |
| I7 | 오류·복구/신원 | portfolio503→재열기200 및401→복구 | 안내표시·같은page복구·권한보존 | 503안내→200,401안내→200,동일page | 없음 | 실제Next+Flask | batch정리완료 | yes |
| I8 | 지원설정·오도된성공 | trackedenv/공개키/바인딩/명령종료코드검사 | .env.example만추적, 새publicsecret0,실제배포안함 | .env.example만추적·원본비밀미로드·build성공 | 없음 | git/build/logs | batch정리완료 | yes |
| I9 | dirty·종료 | source/frozen/hash와소유서버·scratch·Space경계 | 원본불변·소유batch자원정리, 공유Space명시 | batch서버/scratch정리·원본package보존 | 없음 | cleanup | batch정리완료 | yes |

| I10 | 잘못된날짜·경로입력 | traversal/불가능날짜/빈값/Unicode→GET | loader전400, 정상윤년200 | 8종입력400·단위loader0·윤년정상 | 날짜strict검증 | fixture/브라우저 | batch정리완료 | yes |

prompt injection·취소명령은변경한제품parser/agentworkflow에없어적용불가. 비신뢰헤더(I1)와stale상태(I3/I4)를실행한다.
정체는소유processgroup timeout종료, 거짓성공은exit와필수행렬함께판정. flaky는원인없이반복하지않음.

## Baseline

RED9실패55통과, scheduler3실패 → target132통과. 최종전체pytest2444/3skip,Vitest640/83files,typecheck/lint/build통과.
삭제된GET전용cooldown31검사를폐기하고10개경계검사를추가했다. 기존실패를숨기기위한삭제가아님.
최종리뷰와브라우저통과. 아래증거·정리참조.

검증주소: http://127.0.0.1:57970/dashboard/kr ; Next57971, fixture57972. 리더복구는분당1회job으로재시도하며새감시스레드없음.

## 동적 결과와 한계

필수10/10통과, 미통과필수없음. ULTRAQA COMPLETE: Goal met after 2 cycles.
cycle1 locator visible/hidden중복과fixture인접backtest응답누락404 → cycle2 snapshot/가시상태조건 및응답보강. 제품변경없음.
브라우저matrix·recovery명령exit0, JSON증거를직접대조. 중간open호출은stdout없는exit0여서후속snapshot으로실제상태확인,exit0만으로판정하지않음.
Next configErrors0/compilationissues0. 남은console error1은의도한합성portfolio503이며복구후신규0. 401은로그인안내로처리.
스크린샷9개리더직접열람. 401의동일계정기존헤더캐시를전부지웠다고주장하지않음. 실제외부KRX/AI/원본계정/배포검증아님.

## 정리

소유fixture2PID/Next/gateway종료,57970/71/72닫힘,scratch삭제,원본package불변.
Space20은하나의연속사용자목표공유자원으로about:blank에두고다음NumPy라운드로이어감. finish0회이며전체브라우저종료로보고하지않음.
제품기준3f5d07f,소스30경로root/scratch/frozen일치.
