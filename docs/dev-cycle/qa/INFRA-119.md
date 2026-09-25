# [INFRA-119] 수동 V2 실행의 실행권 저장 실패 거부 — QA 기록

- 대상: `launch_jongga_v2_screener`(`services/kr_market_jongga_runtime_service.py`)가 잠금 안의 `save_v2_status(True)` 가 False 이면 스레드 없이 500 을 돌려주고, 라우트의 `_save_v2_status`(`app/routes/kr_market_jongga_execution_routes.py`)가 `write_v2_status` 의 성공 여부를 돌려준다
- 단계(phase): 완료 | 시나리오 구성 완료 | 실행 완료
- 구성 2026-09-25(설계 승인 14:45 뒤, 실행 전, 분 단위 시각은 기록하지 않음) | 실행 2026-09-25 14:50:59~14:51:04
- 검증 기준 커밋: `04bf3166`(이 문서를 담은 첫 커밋). 대조는 수정 전 커밋 `302c9c6d`. 사본은 각 커밋의 `git archive` 다
- 구성 근거: 설계 승인(대화 14:45). 결함은 상태 파일 저장이 실패할 때만 드러난다
- QA 엔진(engine): Claude Code. browser_applicability: 하네스 대체. 화면의 실행 버튼은 409 가 아닌 오류에서 스피너를 끄는 기존 분기를 그대로 탄다(`page.tsx` 변경 없음). 저장 실패는 운영 `data/` 의 권한을 바꿔야 재현되며, 원본 서버에 실행 요청을 보내면 실제 LLM 분석이 돌기 때문에 금지다. 그래서 사본에서 실제 라우트·launcher·`write_v2_status`·`atomic_write_text` 를 Flask 테스트 클라이언트로 부르고, 분석 파이프라인만 시작 흔적을 남기는 가짜로 바꾼다
- 실패 주입: 가짜 함수가 아니라 실제 디스크 조건이다. 사본 `data/` 를 0555 로 바꿔 원자적 저장의 임시 파일 생성을 실패시킨다. 잠금 파일과 상태 파일(`isRunning: false`)은 미리 둔다
- 격리: 각 커밋의 `git archive` 사본에서 `secrets/`·`data/`·`.env` 를 지운다. 하네스는 소켓 연결을 막는다. 서버와 포트는 쓰지 않는다
- 하네스: 세션 스크래치의 `infra119qa_harness.py <사본>`(사본 경로가 scratchpad 가 아니면 거부)
- 필수 여부(required): S-1·S-2 예
- 반복(iteration): 1회
- 결과: 통과 (필수 2/2)
- 증거: 아래 「실제」 줄(하네스 `RESULT` 줄 원문, scratchpad `qa-infra119-old.txt`·`qa-infra119-new.txt`), 두 실행 모두 exit 0, stderr 0줄(소켓 차단 예외 0건)

## 시나리오

### S-1. 실행권을 저장하지 못하면 수동 실행을 거부하고 분석을 시작하지 않는다 (하네스, 필수)
- 조작: 사본 `data/` 를 쓰기 금지로 바꾸고 실행 요청을 보낸다
- 기대: 수정 뒤 500·`status: error`, 분석 시작 없음, 상태 파일 `isRunning` false 그대로, 저장 실패 로그 있음(True 와 거부 뒤 되돌리는 False 두 번), 임시 파일 남지 않음. 수정 전은 200 과 분석 시작(결함 재현)
- 실제: 수정 뒤 500·`error`, 분석 시작 없음, `isRunning` false, 저장 실패 로그 2건(True·되돌리는 False), 임시 파일 0. 수정 전 200·`started`, 분석 시작(결함 재현), 저장 실패 로그 2건(True·끝난 뒤 False), 임시 파일 0. 통과

### S-2. 회귀: 쓰기가 돌아오면 요청이 200 이고 끝난 뒤 False (하네스, 필수)
- 조작: 권한을 되돌리고 다시 요청한다
- 기대: 수정 전후 모두 200, 분석 1회, 끝난 뒤 `isRunning` false
- 실제: 수정 전후 모두 200·`started`, 분석 1회, 끝난 뒤 false. 통과

## 정리
- 실제: 두 사본(`q119old`·`q119new`)을 리터럴 경로로 삭제(남은 사본 0), 하네스 프로세스 0. 원본 `data/` 에서 QA 직전(14:50:50) 뒤 수정된 파일 0개(`find data -newermt`, 14:51:11 확인). 서버·포트·브라우저는 쓰지 않았다. 원본 `data/`·`.env` 사용 없음. 결과: 필수 2/2 통과
