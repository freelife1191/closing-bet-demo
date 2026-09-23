# [JONGGA-040] 종가베팅 최신 파일 단일 쓰기 — QA 시나리오

- 대상
  - 스케줄러 진입 함수 `scripts/init_data.py` 의 `create_jongga_v2_latest`
  - 관리자 실행 라우트가 쓰는 `services/kr_market_route_service.py` 의 `run_jongga_v2_background_pipeline`
  - 그 결과를 읽는 종가베팅 화면 `/dashboard/kr/closing-bet`
- 구성 근거
  - TODO 의 범위 줄(중복 쓰기 세 곳 제거)
  - 계획 검토 R1: 스케줄러 체인 뒤 `send_jongga_notification` 이 새 파일을 읽는지(cwd=BASE_DIR)
  - 승인 줄: 격리 사본, 가짜 `run_screener`, 브라우저 확인
- 가짜 `run_screener` 의 동작: 실제 `engine.generator.save_result_to_json` 으로 결과를 저장한 뒤 결과를 돌려준다. 이는 `run_screener` 의 마지막 단계(`engine/generator.py:170`)와 같다. 시그널 한 건은 원본 `data/jongga_v2_latest.json` 의 첫 시그널을 읽기 전용으로 복사하고, 이름만 「QA종목040」으로 바꾼다. LLM·시세 조회·Market Gate 는 부르지 않는다
- 쓰기 계측: `atomic_write_text` 와 `builtins.open` 을 감싸서, `jongga_v2_latest.json` 에 대한 쓰기를 경로와 방식별로 센다
- 구성 2026-09-23 14:05 | 실행 2026-09-23 14:09~14:13 (1회차)
- 검증 기준 커밋: `09dca99` (첫 커밋, `code/` 는 `git archive 09dca993`). 대조군은 `git archive 09dca993~1` 로 같은 harness 를 돌렸다
- QA 엔진(engine): Claude Code, 브라우저는 gstack `browse`
- 금지 사항
  - 원본 3500·5501, live 주소, 원본 `.env`, 원본 `data/` 쓰기
  - 실제 LLM 호출, 실제 메시지 발송. `Messenger` 발송 메서드는 기록만 하는 가짜로 바꾼다
  - 설정 저장, Refresh 계열, 재분석, 모의 매수, 삭제
- 격리 구성
  - 코드 사본 `code/` 는 `git archive <첫 커밋>` 으로 만들고 `.env`·`secrets/` 는 두지 않는다
  - 원본 `data/` 의 JSON·CSV 를 `code/data/` 에 복사한다
  - cwd 는 `code/` 로 두어 운영처럼 BASE_DIR 과 cwd 를 같게 한다
  - gunicorn `env -i`, `SCHEDULER_ENABLED=false`, 더미 `INTERNAL_IDENTITY_SECRET`, 5754 포트로 띄운다
  - Next 는 `API_URL=http://127.0.0.1:5754` 로 3754 포트에 띄운다
- 단계(phase): 시나리오 구성 완료 | 실행 완료
- 반복(iteration): 1회
- 결과: 통과 (필수 4/4)
- 증거: harness 출력 scratchpad `jongga040-harness.out`, 격리 gunicorn access 로그 사본 `jongga040-access.log`, 스크린샷 `jongga040-s4.png`(열어 확인), browse `js`·`console --errors` 출력, `/_next/mcp get_errors`
- 정리(cleanup): browse 서버 정지, 격리 gunicorn 마스터 TERM, 격리 Next 프로세스 그룹 TERM. 3754·5754 와 원본 3500·5501 에 리스너 0, 사본 경로 프로세스 0, 사본 `qa-jongga040/`·대조군 `qa-jongga040-base/` 삭제. 사본 구성 시각(14:09:20) 이후 원본 `data/`·`logs/` 에서 수정 시각이 바뀐 파일 0개. 루트 `node_modules/.vite` 없음, 작업 트리 변화 없음
- 구성 중 차이: 첫 Next 기동은 `env -i` 의 PATH 에 npm 경로(`/usr/local/bin`)가 없어 `FileNotFoundError` 로 뜨지 않았다. PATH 를 고쳐 다시 띄웠고 판정에는 영향이 없다
- 필수 여부(required): 예
- browser_applicability: required. 사용자는 이 파일을 종가베팅 화면으로만 본다. browser_driver: gstack `browse`

## 시나리오

### S-1. 스케줄러 진입 함수가 최신 파일을 한 번만, 원자적으로 쓴다 (핵심)
- 조작: 가짜 `run_screener` 와 쓰기 계측을 건 상태로 `create_jongga_v2_latest()` 를 부른다
- 기대
  - 반환값이 True 다
  - `jongga_v2_latest.json` 쓰기는 `atomic_write_text` 로 1회만 일어나고, `open(..., 'w')` 로는 0회다
  - 일자 파일 `jongga_v2_results_20260923.json` 도 1회 쓰인다
  - 최신 파일이 올바른 JSON 이고 「QA종목040」을 담는다
- 필수 여부(required): 예
- 실제: 반환 `True`. 최신 파일 쓰기 `[('atomic', …/code/data/jongga_v2_latest.json)]` 1건, `open:w` 0건. 일자 파일 `atomic` 1건. 최신 파일 `date=2026-09-23`, `names=['QA종목040']`, `summary=QA종목040 요약`. 대조군(변경 전 커밋)은 같은 조작에서 `('atomic', …)`, `('open:w', …)` 두 건이었다. harness stderr 0줄
- 결과: 통과

### S-2. 스케줄러 체인의 알림이 방금 쓴 파일을 읽는다 (계획 검토 R1)
- 조작: S-1 직후 `Messenger` 발송을 기록 전용 가짜로 바꾸고 `send_jongga_notification()` 을 부른다
- 기대: 가짜 발송이 받은 결과에 「QA종목040」이 들어 있다. 실제 발송은 0건이다
- 필수 여부(required): 예
- 실제: 가짜 발송 1건, 받은 결과의 시그널 `['QA종목040']`, 요약 `QA종목040 요약`. `Messenger` 를 기록 전용 가짜로 바꿔 실제 발송은 0건. cwd 와 `BASE_DIR` 이 모두 사본 `code/` 임을 harness 가 단언했다
- 결과: 통과

### S-3. 관리자 실행 경로도 한 번만 쓴다
- 조작: 같은 계측으로 `route_service.run_jongga_v2_background_pipeline(...)` 을 부른다. 알림 함수는 기록 전용 가짜로 바꾼다
- 기대
  - 최신 파일 쓰기가 원자적으로 1회 일어난다
  - 상태 기록은 `[True, False]` 순서다
  - 알림 함수가 1회 불린다
- 필수 여부(required): 예
- 실제: 최신 파일 쓰기 `atomic` 1건, 일자 파일 `atomic` 1건, 상태 `[True, False]`, 알림 함수 호출 1건. 최신 파일 `names=['QA관리자040']`. 대조군은 최신 파일 `atomic` 2건·일자 파일 2건이었다(두 번째 `save_result_to_json`)
- 결과: 통과

### S-4. 화면에 새 결과가 보인다
- 조작: 격리 서버를 띄우고 `/dashboard/kr/closing-bet` 을 연다
- 기대
  - 마지막 저장의 카드가 보인다. 계획 초안에는 「QA종목040」으로 적었으나, S-3 이 S-1 뒤에 같은 파일을 새로 저장하므로 기대값은 S-3 의 「QA관리자040」이다(실행 전 순서를 반영하지 못한 초안의 오기)
  - 최신 조회 API 가 200 이다
  - 콘솔 오류와 5xx 가 0 이다
- 필수 여부(required): 예
- 실제: 격리 gunicorn `GET /api/kr/jongga-v2/latest` 200(16026 바이트)이 `date=2026-09-23`, `['QA관리자040']` 를 돌려줌. 화면 `/dashboard/kr/closing-bet` 의 본문에 「QA관리자040」 있음, S GRADE 카드와 하단 `Updated: 2026-09-23T14:09:44` 가 S-3 저장 시각과 일치(스크린샷 `jongga040-s4.png`). `console --errors` 「no console errors」, `/_next/mcp get_errors` `configErrors:[]`·`sessionErrors:[]`. access 로그 8건 모두 200, error 로그의 Traceback·ERROR 0건
- 결과: 통과
