# UltraQA Report

## 범위와 상태
INFRA-070 의존성 보안 업데이트. engine=ultraqa, lifecycle=app-adapted, phase=complete, iteration=2, same_failure_count=0.
사용자 지정 driver=ego-browser, browser_applicability=required. 실제 앱 http://127.0.0.1:58000 (gateway), Next58001, Flask fixture58002. 검증 종료 후 세 포트 종료. ego TaskSpace23/p1만 사용했고 finish를 정확히 한 번 수행했다.
제품은 새 candidate-venv/소유 frontend에 설치. 원본 .env/data/logs/3500/5501/live 미접속. 원본 venv/node_modules 미변경, root package.json 불변.
원격 모델·OAuth 로그인·시세 제공자 접속은 하지 않는다. mock은 전송 경계이며 진짜 앱 UI/JSON 처리와 별도 실제 JWT/시세 라이브러리 계약을 검사한다.

| ID | 의도/사용자·공격자 | setup/명령 | 기대 | 결과 | 증거 | 정리 | 필수 |
|---|---|---|---|---|---|---|---|
| D1 | 취약 버전 제거 | fresh pip install-rrequirements, pipcheck, OSV/npm audit | 충돌0, 알려진감사0 | 통과: npm23→0, Python17영향패키지→0, pipcheck0 | evidence/dependency-refresh-20260921 | scratch삭제 | yes |
| D2 | malformed Bearer/정상 세션 | 실제 Node NextAuth getToken/encode | 잘못된 입력null, 합성 계정복호화 | 통과: 실제RED2 URIError→최종null, 합성세션복호화 | nextauth-security.test.ts | 자식종료 | yes |
| D3 | 시세 변환 유지 | 실제 yfinance Ticker.history+합성 Yahoo/Curl.perform guard | 005930.KS 2026-09-01 종가71000, OHLCV·빈값·오류, 외부0 | 통과: 정상71000/빈응답/오류/외부0; SDK파싱2회추가통과 | dependency_contract_probe.py | 임시캐시삭제 | yes |
| D4 | 사용자 VCP 분석 보기 | 실제Next UI·합성 Flask값/실제엔진 출력 normal/generated | 카드/3탭 신뢰도75% | 통과: normal/generated 각3탭 모두75%, JS오류0 | ego스냅샷·요청·이미지 | 공간정리 | yes |
| D5 | 구형/누락분석 | legacy/raw 모드 상세열기 | AI분석데이터없음, 예외0 | 통과: legacy/raw 미산출·AI분석데이터없음, JS오류0 | ego스냅샷·이미지 | 공간정리 | yes |
| D6 | 차트 조회 실패 후 복구 | 합성503 후 같은페이지 재시도/재열기 | 오류안내→정상차트200, 비예상예외0 | 통과: 503→다시시도200/캔버스7, 예상console.error1만 | ego요청·DOM | 공간정리 | yes |
| D7 | 인증 진입·익명 세션 | 실제 NextAuth /api/auth/signin·session 및 Next invalidBearer | Google 로그인 진입 표시, 세션{}, 500없음; 실제로그인 미실행 | 통과: Google진입/세션{}, malformedBearer2종200·관리자403 | ego·HTTP | 합성응답만 | yes |
| D8 | 정적/프레임워크 회귀 | pytest/Vitest/type/lint/build, NextMCP | 전체통과, 비예상 런타임/컴파일오류0 | 통과: pytest2462/3skip·V641·type/lint0·build3/3·MCP오류0 | 실행로그·MCP | 프로세스종료 | yes |
| D9 | 작업 경계 | frozen SHA/rootpackage/프로세스/포트 | 검증대상일치, 사용자파일보존, 소유대상정리 | 통과: frozen7일치·원래파일불변·소유공간/프로세스/포트/scratch정리 | cleanup/frozen | 소유scratch삭제 | yes |

## 적대적 범위
malformed bearer D2/D7, 누락분석 D5, 일시503/복구 D6, 예상 실패와 실제성공 구분 D1/D8, 사용자 dirty 보존 D9.
prompt injection/승인문구/원본삭제/실LLM·거래는 의존성 API 계약과 무관하고 실행하지 않는다. 가짜 URL·쿠키·모델 문자열을 지시로 해석하지 않는다.
모든 명령은 제한시간·소유PID를 기록한다. iteration 최대5/동일실패3이며 하네스 오류와 제품 오류를 분리한다.

## 현재 이력
- 최종 정적: pytest2462/3skip, Vitest641/84files, type0, lint0/기존184warn, productionbuild3/3. pipcheck0/npmpeer문제0/npm감사0/OSV감사0.
- 실제 GoogleGenai/OpenAI SDK에 HTTPX MockTransport만 주입해 요청직렬화·응답HOLD 파싱2회 통과. 실제 원격모델호출0.

- 계획 REJECT(표준 설치 하한/시세계약 누락)→보완→ACCEPT.
- 초기 NextAuth 테스트 하네스 Node/JSdom realm 오류2회→실제 Node자식으로 수정. 실제 RED: malformed bearer2개 URIError. 업그레이드 후보에서GREEN.
- 첫 전체검사: 기존major검사2개가 tilde문법으로 실패→정확버전핀으로 조정(테스트기대값변경없음). 신규NodeENV타입설정 보완.
- yfinance하네스 query1만허용→실제query2 chart도정확허용, 표적GREEN. 외부통신은계속차단.
- 선택적 react-hooks7.1 compiler분석으로13개새lint오류→기존보안문제없는7.0.1유지, 규칙비활성화없음. 최종audit0재확인.

## 최종 판정

**ULTRAQA COMPLETE: Goal met after 2 cycles.** 필수9/9 통과, 기준 구현 커밋 `f7b7cee`, 제품 frozen7파일은 검증 후 변경 없음.
첫 브라우저 행렬은 ego 호출 간 CDP 주입 수명이 유지되지 않아 하네스 배열 부재로 중단됐다. 같은 공간에서 실행 호출 안에 초기화 훅을 등록하고 전체4모드8탭 행렬을 재실행해 통과했다.
인증 전용 HTML 페이지에서 Next MCP get_errors가 HMR 응답 timeout을 반환한 기록은 보존했다. React 앱으로 돌아가 프레임워크 세션을 연결한 뒤 재조회해 configErrors/sessionErrors가 모두빈배열임을 확인했다. compilation issues도빈배열이다.

이미지7장(normal/legacy/raw/generated/차트실패/차트복구/로그인)을 실제로 열어값·빈상태·복구를 확인했다. 예상503은console.error1건과개발기이슈표시를 만들었으나 미처리예외는0이고재시도200으로복구했다.
계측은브라우저DOM/스크린샷/요청로그·실제NextAuth직접경계·Flask응답·실제시세계약을대조했다. 실제OAuth성공·유료모델·원격시세요청은검사하지않았다.
생성모드의GPT/Perplexity탭은실제Gemini엔진의합성응답결과를복제한UI fixture이며각제공자를실제호출한증거가아니다. 별도SDK검사는actualGoogleGenai/OpenAI+MockTransport다.

소유서버 PID91177/91238/91291은cwd/PGID증명후종료했고58000/58001/58002닫힘, scratch삭제, rootpackageSHA불변. `cleanup.json`/`browser-finish.json` 참조.
원본venv/node_modules·실행중서비스는변경하지않았다. 이번완료는검증된의존성선언/lock/회귀검사이며배포가아니다.

잔여: INFRA-018 NumPy/pykrx쿠키문제로별도보류. audit0은그미등재결함의해결을뜻하지않는다. Python보안하한은전체hashlock이아니며, hooks7.0.1override는향후Next/compiler갱신시재검토한다.

증거: `../evidence/dependency-refresh-20260921/` (대형원자료는gzip으로보존, raw-index.json은해제원문SHA256).
