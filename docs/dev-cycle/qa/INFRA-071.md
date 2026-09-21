# INFRA-071 UltraQA

engine=ultraqa, lifecycle=app-adapted, iteration=1, phase=baseline, same_failure_count=0.
기준5b3a505 + 현재 소스diff. 정상 설치 환경을 실제 사용하되 자동 테스트는 별도 scratch/네트워크차단, 원본 data/secrets 읽기·쓰기 차단.
브라우저: ego-browser(사용자 지정), required. 원본3500/5501은 root만 사용, 외부 AI1회 사용자 승인 범위, 알림/매매 금지.

| ID | 의도/모델 | setup/command | 기대 | 실제 | 증거/cleanup |
|---|---|---|---|---|---|
| N1 | 뉴스 DOM/압축 변경 | synthetic current+legacy, header regression | 제목/언론사 정확·지원압축만 요청 | targeted PASS | tests/engine/test_news_current_markup.py |
| N2 | stale empty cache | memory/SQLite 빈 rows | fetch 재시도·positive cache 유지 | targeted PASS | test_news_collector_refactor.py |
| N3 | 오류/부분 실행 | KOSPI성공,KOSDAQ실패 | 예외전파, latest/daily바이트 보존, save미호출 | targeted PASS | test_generator_runtime_failure.py |
| N4 | 정상0건 | NoCandidatesError | 정상 빈 반환 유지 | targeted PASS | 같은 테스트 |
| N5 | 실제 수집→AI→저장 | 기존run_screener, 알림wrapper미호출 | 실제뉴스/LLM/오늘결과 성공 | 대기 | 로그는local private, 요약만evidence |
| N6 | 실제 화면 | 오늘종가리포트 조회 | 날짜/후보/AI근거 표시, JSON오류0 | 대기 | taskspace 종료 |
| N7 | 기존파일/정리 | rootpackage/설정 해시, scratch정리 | 보존·자체fixture만제거 | 대기 | 서비스 유지 |

전체pytest/Vitest 필수. 외부런타임변조/프롬프트인젝션은 이 변경에 해당없음. AI 응답을 코드/명령으로 실행하지 않는다. 중단/반복은1회작업 상태와실제실행대조, 실패3회또는5cycle상한 준수.

## Baseline
- 초기전체검증은 scratch에 node_modules가 없어 @next/env/TypeScript검사설정실패. 제품테스트를수정하지않고 기존설치의 copy-on-write복사로보완.
- 격리전체pytest2472passed,3skipped(기존manual2/env없음1),53.88초. Vitest84files/641passed.
- 이후제품소스변경없이 AllCandidatesFilteredError계약회귀1건추가. 최종표적17passed(0.87초). 전체2473을실행했다고주장하지않음.
- RED: 원본대비현행markup/빈캐시/partial실패4건실패, 압축계약별도실패확인.
- 실제HTTP비교: 기존기본헤더br 응답57153bytes/제목0, gzip응답332447bytes/제목10. 구finance410, 다음검색짧은페이지. 수정후3종목각3기사.
