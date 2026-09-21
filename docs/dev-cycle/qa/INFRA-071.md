# INFRA-071 UltraQA

engine=ultraqa, lifecycle=app-adapted, iteration=1, phase=complete, same_failure_count=0.
기준5b3a505 + 현재 소스diff. 정상 설치 환경을 실제 사용하되 자동 테스트는 별도 scratch/네트워크차단, 원본 data/secrets 읽기·쓰기 차단.
브라우저: ego-browser(사용자 지정), required. 원본3500/5501은 root만 사용, 외부 AI1회 사용자 승인 범위, 알림/매매 금지.

| ID | 의도/모델 | setup/command | 기대 | 실제 | 증거/cleanup |
|---|---|---|---|---|---|
| N1 | 뉴스 DOM/압축 변경 | synthetic current+legacy, header regression | 제목/언론사 정확·지원압축만 요청 | targeted PASS | tests/engine/test_news_current_markup.py |
| N2 | stale empty cache | memory/SQLite 빈 rows | fetch 재시도·positive cache 유지 | targeted PASS | test_news_collector_refactor.py |
| N3 | 오류/부분 실행 | KOSPI성공,KOSDAQ실패 | 예외전파, latest/daily바이트 보존, save미호출 | targeted PASS | test_generator_runtime_failure.py |
| N4 | 정상0건 | NoCandidatesError | 정상 빈 반환 유지 | targeted PASS | 같은 테스트 |
| N5 | 실제 수집→AI→저장 | 기존run_screener, 알림wrapper미호출 | 실제뉴스/LLM/오늘결과 성공 | PASS: 135.8초, 424개 스캔, 뉴스36건, 실제AI12건·저장12건 | live-run.json, live-stages.txt |
| N6 | 실제 화면 | 오늘종가리포트 조회 | 날짜/후보/AI근거 표시, JSON오류0 | PASS: 오늘날짜·UPDATED·후보/결과12, 브라우저오류0 | live-browser.png, browser-errors.json, space28 finish1회 |
| N7 | 기존파일/정리 | rootpackage/설정 해시, scratch정리 | 보존·자체fixture만제거 | PASS: 설정/rootpackage 해시보존, scratch/임시스크립트삭제 | preserved.json,cleanup.json; 서비스유지 |

전체pytest/Vitest 필수. 외부런타임변조/프롬프트인젝션은 이 변경에 해당없음. AI 응답을 코드/명령으로 실행하지 않는다. 중단/반복은1회작업 상태와실제실행대조, 실패3회또는5cycle상한 준수.

## Baseline
- 초기전체검증은 scratch에 node_modules가 없어 @next/env/TypeScript검사설정실패. 제품테스트를수정하지않고 기존설치의 copy-on-write복사로보완.
- 격리전체pytest2472passed,3skipped(기존manual2/env없음1),53.88초. Vitest84files/641passed.
- 이후제품소스변경없이 AllCandidatesFilteredError계약회귀1건추가. 최종표적17passed(0.87초). 전체2473을실행했다고주장하지않음.
- RED: 원본대비현행markup/빈캐시/partial실패4건실패, 압축계약별도실패확인.
- 실제HTTP비교: 기존기본헤더br 응답57153bytes/제목0, gzip응답332447bytes/제목10. 구finance410, 다음검색짧은페이지. 수정후3종목각3기사.


## 실제 실행 결과

구현 커밋은 `5cc1c17`이다. 검증된 Gunicorn master 77981에 HUP을 보내 워커 69349/69350으로 갱신했다. 실제 스크리너는 기존 venv와 운영 설정을 사용하는 기존 `run_screener()` 경로로 실행했다. 알림을 보내는 웹 wrapper는 호출하지 않았다.

- 실행 시간: 135.8초. KOSPI174 + KOSDAQ250 = 424개 후보 검사.
- 뉴스: 필터를 통과한 12개 종목에서 총36건 수집.
- 실제 Gemini(Vertex) gemini-3.7-flash 분석: KOSPI9건, KOSDAQ3건 모두 성공. 모의 전송이나 고정 응답을 사용하지 않았다.
- 결과: 2026-09-21 날짜로12건 저장, 모든 결과에 AI 근거 포함. API의 최신 날짜와 결과 수 확인, 상태IDLE.
- ego-browser 실제 화면: 후보12·결과12, UPDATED, 오늘 종가와 Gemini 근거 표시. 이전의 오늘 자료 없음 경고 제거. PNG를 직접 열어 시각 확인했다.
- 브라우저 계측은 invocation 사이 지속되지 않아 처음 캡처의 errors 필드가 빠졌다. 같은 invocation에서 오류 hook 등록→reload→조회로 다시 검사해 errors=[]를 확보했다. 누락된 계측을 무오류로 세지 않았다.
- Next MCP configErrors/sessionErrors/compilation issues 모두 빈 배열.
- 소유 space28 finish keep[] 1회 완료. scratch 및 임시 실행 스크립트 제거. 기존 서비스3500/5501은 실행 유지.

## 보존과 제한

사용자 root package.json과 설정 파일 총9개의 해시가 일치한다. 기존 정상 결과는 실행 전 `logs/infra071-before-rerun/`에 백업했다. 이번에는 성공한 최신12건이 저장됐으므로 백업을 되돌리지 않았다. 정상 분석 경로가 데이터와 캐시를 갱신했으며 데이터 무변경을 주장하지 않는다.

KRX_ID/KRX_PW가 없는 제한은 유지된다. KRX 계정은 임의로 설정하지 않았으며, 실제 KRX 인증 조회 성공을 주장하지 않는다. 이번 전체 분석은 기존 대체 데이터 경로로 성공했다. AI 응답의 모든 서술이나 수치가 정확하다는 검증은 별개다. 시크릿 변경, 매매, 메신저 발송은 수행하지 않았다.

## 최종 판정

ULTRAQA COMPLETE: Goal met after 1 cycle. 시나리오7/7 통과. 새 압축/DOM 회귀와 실패 저장 보호가 확인됐고, 실제 신규 분석→저장→화면까지 성공했다.
