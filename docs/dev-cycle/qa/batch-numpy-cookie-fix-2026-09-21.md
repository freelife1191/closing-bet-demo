# UltraQA Report

## 목표와 상태
INFRA-018 NumPy2.4.6/pykrx1.2.9+cookie.1 업그레이드. engine=ultraqa, lifecycle=app-adapted, phase=planning, iteration=2, same_failure_count=0.
최초 iteration1의 공식pykrx Cookie 유출(N4 실패)·화면 검수(N5 차단)를 그대로 해결하는 재개다. 수정판의 회귀 GREEN으로 같은 실패 원인이 해소됐으며 필수 기준을 낮추지 않았다.
Browser required, 사용자 지정 ego-browser. 신규 소유 공간 하나에서 실제 Next58011·Flask58012·gateway58010을 사용한다. 원본3500/5501/live/.env/data/logs/venv/node_modules는미변경.
공식wheel 다운로드 외 실제KRX로그인·Naver/Yahoo시세·OAuth·유료LLM은금지. 가짜cookie와HTTP/model전송대역만사용한다.

| ID | 의도/입력 | 표면·명령 | 기대 | 결과 | 증거 | cleanup | required |
|---|---|---|---|---|---|---|---|
| U1 | 공급망/변조 | 공식SHA·rebuild3회·RECORD/METADATA검사 | 동일SHA/원본2파일만patch/변조거부 | 통과 | wheel-verification.json | 소유빌드정리 | yes |
| U2 | 설치계약(N1) | fresh pip install-rrequirements, pipcheck, upstream-normalizedOSV | numpy2.4.6/localpykrx선택·충돌0·감사0 | 통과 | installed-wheel-proof/versions/audit | candidate삭제 | yes |
| U3 | 쿠키경계(N4) | 실제Get/Post·KRXSession·stock.get_market_ohlcv_by_date, domainless가짜cookie,HTTPAdapter대역 | KRX인증유지/외부Cookie없음·재인증0/redirect차단/실외부0 | 통과 | permanent transport probe RED→GREEN | 자식종료 | yes |
| U4 | 데이터계약(N2/N3) | NumPy타입JSON/실제pykrx6API/yfinance | 숫자·배열·날짜·DataFrame/오류계약유지 | 통과 | 표적6건 | 자식·캐시정리 | yes |
| U5 | 화면연결(N5) | actualstock→np.int64가격→NumpyEncoder→Flask→Next VCP 정상/생성 3탭 | 가격71000·신뢰도75%·예외0 | 대기 | qa-numpy-flow/ego | 공간정리 | yes |
| U6 | 빈값/실패복구 | legacy/raw 상세와차트503후다시시도 | 빈상태/200복구·예상오류외0 | 대기 | egoDOM/요청/이미지 | 공간정리 | yes |
| U7 | 전체회귀 | pytest/Vitest/type/lint/build·SDK전송대역 | 전체성공 | 통과 | 2464/3skip,V641,type0,lint0/184warn,build3/3,SDK2회 | 프로세스종료 | yes |
| U8 | 잘못된날짜·Next오류 | 앱API400·MCPget_errors/compilation | 4개400·비예상오류0 | 대기 | ego/MCP | 프로세스종료 | yes |
| U9 | 변경/정리 | frozen9/원래packageSHA/PID/포트 | 불변과소유대상정리 | 대기 | cleanup | scratch/공간종료 | yes |

## 경계와 해석
보안재현은공식1.2.9에서실제NaverCookie유출 및전역세션조회 RED를확인한뒤수정했다. 별칭만삭제한이전부분작업으로N4/N5를완료시키지않는다.
공개요청은환경proxy/netrc를상속하지않고인증redirect를자동추종하지않는다. 공급자가해당동작을요구하면별도검토가필요하다.
실제KRX인증성공이나실시간시세정확성을시험한것은아니다. 합성HTTP에서실제라이브러리/파서/JSON/화면의동작을검증한다.
프롬프트자료/가짜Cookie문자열은지시로처리하지않는다. 다른작업파일보존과명령timeout/실패신호해석을정리행에포함한다.
