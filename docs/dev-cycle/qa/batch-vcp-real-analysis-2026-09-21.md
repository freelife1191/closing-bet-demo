# VCP-022 실제 분석 경로 — UltraQA App 대응

범위: 구형 모의 생산 중단, 정확한 템플릿 조회 제외, 실제 VCP 엔진 재사용, 실패/과거 저장 보존, 구형 개인키 API 410. 사용자 승인 판단 위임과 critic ACCEPT 설계에 따른다. 특정 20260211 실행 요청 귀속은 조사 자료 없이 확정하지 않는다. 이번 라운드 시작 전 별도 역사 귀속 요구는 비상용 프로젝트의 재발 방지 완료 기준에서 제외했으며 QA 실패를 사후 면제하는 것이 아니다.

실행: Codex App에서 ultraqa 절차를 수행하고 OMX tmux/runtime state는 사용하지 않는다. 사용자 지정 ego-browser Space20/p1 재사용. 실제 외부 AI 품질/운영 데이터 검증은 포함하지 않는다. 실제 클래스·parser·writer·병합·화면을 실행하되 외부 모델 transport와 시장 자료만 합성한다.

| ID | 필수 시나리오 | 기대 결과 | 결과 |
|---|---|---|---|
| V1 | 구형 Gemini/GPT 키 유무와 정확 템플릿 3종 | 생산 None, 전체 템플릿 차단, 한 글자 변형·정상 문장 보존 | 정적 PASS, UI 대기 |
| V2 | 실제 VCP batch/model transport/parser/writer | 합성 transport 1회, 외부0, confidence75 저장 | target PASS, 실측 대기 |
| V3 | None/실패/부분 실패/빈 대상 | 이전 provider/news/다른 ticker와 파일 보존 | target PASS |
| V4 | 과거 실행 및 메모리 날짜선택 | 과거 dated만 갱신, latest 바이트 보존, 대상 날짜만 선택 | target PASS |
| V5 | VCP+AI 통합 선택 | 대상0 done, 날짜/ticker 불일치 error, 추가 모델0·쓰기0 | target PASS |
| V6 | 구형 개인키 API | 410, 파싱·쿼터·모델 호출0, 현재 VCP 경로 유지 | target PASS, HTTP 대기 |
| V7 | merged/raw UI 경로 및 정상 복구 | 정확 템플릿 미노출, 정상75/실제엔진 합성75, JS 오류 없음 | 대기 |
| V9 | 날짜 조회 경로 탈출·빈값·잘못된 달력 | 파일 조회0, HTTP400, 정상ISO/compact 허용 | target29 PASS, HTTP 대기 |
| V8 | 전체 회귀/리뷰/정리 | 필수 검사 통과·원본 보존·소유 프로세스 종료·Space finish1 | 진행 중 |

한도: 최대5 QA cycle, 동일 원인3회 실패 시 중단. 명령300초 이하. 최초 source-import 순환 오류·테스트 property setter 오류와 수정 이력은 progress.md 및 원문 로그에 보존한다. 원본 env/data/logs/3500/5501/live 미접근, root package 해시 보존. 조건부 완료 문구를 쓰지 않으며 모든 필수행 완료 전 TODO 유지.
