# [INFRA-079] 유물 사용량 모듈 삭제 (코드 삭제분) — QA 시나리오

- 대상: 격리 사본에서 직접 띄운 backend(gunicorn 58121)의 기존 API, 폐기 라우트 `POST /api/kr/reanalyze/gemini`, 사본 `data/` 의 파일 목록
- 구성 근거: `[INFRA-079]` 설계 승인(2026-09-24 00:36, 두 모듈과 전용 테스트 삭제, 폐기 라우트 테스트를 `user_quota.json` 확인으로 교체, `data/usage.db` 는 건드리지 않음)
- 구성 2026-09-24 00:44 | 실행 2026-09-24 00:44 (1회차)
- 검증 기준 커밋: `6efcb93` (첫 커밋, 00:43). 사본은 이 커밋의 `git archive HEAD` 이며 실행 중 범위 파일은 바뀌지 않았다
- QA 엔진(engine): Claude Code. 삭제한 모듈은 어떤 화면·API 에도 연결되어 있지 않아 사용자 진입 흐름이 바뀌지 않는다. 확인할 것은 삭제 뒤에도 앱이 기동하고 기존 API 가 그대로 응답하며 `usage.db` 가 다시 생기지 않는다는 것이므로 CLI·HTTP 하네스로 검사한다. 하네스:
  첫 커밋 **뒤에** `git archive HEAD` 로 사본을 만들고, 추적 파일 때문에 생긴 `data/` 를 지운 뒤 빈 `data/` 를 새로 만든다. 원본 `data/` 는 복제하지 않는다(이메일이 키인 `user_quota.json`·챗봇 DB 가 scratchpad 로 퍼지지 않게. S-1 의 두 GET 은 저장 자료가 없어도 응답한다). `venv` 는 `cp -c -R` 로 APFS clone 하고, 원본과 inode 가 다른지 `stat -f %i` 로 한 파일을 대조한다. `.env` 계열은 두지 않고 사본의 `secrets/` 는 만들자마자 지운다.
  원본 보호 확인: 실행 전후에 원본 `data/` 의 파일 목록과 `usage.db`·`user_quota.json` 의 크기·수정 시각을 `ls -la`·`stat` 으로만 기록해 대조한다(파일 내용은 열지 않는다).
  정리: 서비스를 내리고 사본 트리를 지운 뒤 `ls` 로 없음을 확인한다.
  `env -i` 로 `SCHEDULER_ENABLED=false` 와 더미 `INTERNAL_IDENTITY_SECRET`·`ADMIN_EMAILS` 를 주고 `venv/bin/python -m gunicorn flask_app:app --bind 127.0.0.1:58121 --workers 2 --threads 8 --timeout 120 --keep-alive 0` 으로 띄운다. 출력은 사본 밖 scratchpad 로 보낸다.
  원본 `data/`·`logs/`·3500·5501·운영 주소는 건드리지 않고 LLM·발송·저장 조작은 하지 않는다
- 기대값 출처: 설계 승인 범위, 폐기 라우트의 기존 응답(`LEGACY_ANALYSIS_RETIRED`, 410)
- 단계(phase): 시나리오 구성 완료 | 실행 완료
- 반복(iteration): 0. 계획은 심층 리뷰(critic) 유보 1~4 를 반영해 고쳤다(S-2 기대 하향, 원본 보호 확인, 원본 `data/` 미복제, 사본에 모듈 부재 확인). 실행 1회. 하네스 실수 둘: (가) 원본에 `user_quota.json` 이 없어 전 상태 기록의 `stat` 이 실패하며 `&&` 연결이 끊겼다(사본 생성 전이라 영향 없음, 실패를 허용해 다시 기록). (나) 정리의 `pgrep -f "<사본>/venv/bin/python -m gunicorn"` 이 프로세스를 찾지 못했다(venv 파이썬이 프레임워크 경로로 풀려 명령줄이 다름). 58121 리스너 셋의 cwd 가 사본임을 `lsof` 로 확인한 뒤 마스터를 TERM 으로 내렸다
- 필수 여부(required): 예
- 결과: 통과 (필수 3/3)
- 증거: 아래 각 시나리오의 「실제」 줄(명령 출력 원문) · 대조 실행 한 건(변경 전 모듈 import 로 결함 재현) · 원본 `data/` 전후 목록·`stat` 대조 `diff` 무차이. HTTP 만 검사해 스크린샷은 없다
- 정리(cleanup): gunicorn 마스터(PID 79555)를 TERM 으로 내려 워커 둘과 함께 종료, 58121 리스너 0, `pgrep -fl infra079` 0건. 대조용 모듈과 대조가 만든 사본 `data/usage.db` 삭제 뒤 사본 트리 삭제, `ls` 로 없음 확인. 원본 `data/`(전후 동일, `usage.db` 28672바이트 2월 22일 12:58:08 그대로, `user_quota.json` 없음)·`logs/`·3500·5501 미접촉

## 시나리오

### S-1. 삭제 뒤에도 앱이 기동하고 기존 API 가 응답한다 (회귀)
- 조작: 사본에 `services/usage_tracker.py`·`engine/services/usage_tracker.py` 가 없음을 먼저 확인한다(사본이 삭제 뒤 커밋에서 떠졌다는 증거). 사본에서 gunicorn 을 띄우고 `GET /api/kr/market-gate`, `GET /api/kr/signals/status` 를 요청한다.
- 기대: 두 응답 200, backend 출력에 `ImportError`·`ModuleNotFoundError`·`usage_tracker` 없음.
- 필수 여부(required): 예
- 실제: 사본에 `services/usage_tracker.py`·`engine/services/usage_tracker.py`·`engine/services/` 없음, `data/` 비어 있음, venv inode 원본 407776760 / 사본 906319070. 00:44:36 기동 확인(`/api/kr/market-gate` 200), 00:44:41 `GET /api/kr/market-gate` 200, `GET /api/kr/signals/status` 200, backend 출력의 `ImportError|ModuleNotFoundError|usage_tracker|Traceback` 0건
- 결과: 통과

### S-2. 폐기 라우트는 그대로 410 이다 (인접)
- 조작: `curl -X POST http://127.0.0.1:58121/api/kr/reanalyze/gemini -H 'Content-Type: application/json' -d '{}'` 을 보낸다.
- 기대: 410, 본문 `code` 가 `LEGACY_ANALYSIS_RETIRED`. 쿼터를 쓰지 않는다는 것은 이 하네스로 증명하지 않는다: 서명된 신원 헤더가 없으면 `g.user_email` 이 없어 퇴행이 있어도 `increment_user_usage` 가 쓰지 않는다(`services/kr_market_quota_runtime_service.py:39-40`). 그 보장은 단위 테스트 `test_retired_gemini_returns_410_without_quota` 가 맡는다.
- 필수 여부(required): 예
- 실제: 00:44:41 http=410, 본문 `{"code":"LEGACY_ANALYSIS_RETIRED",…,"status":"error"}`
- 결과: 통과

### S-3. `usage.db` 가 다시 생기지 않는다 (결함 재현·대조)
- 조작: S-1·S-2 뒤 서비스를 내리고 사본 `data/usage.db` 존재를 확인한다. 대조로 사본에 변경 전 커밋의 `services/usage_tracker.py` 만 되돌려 `import services.usage_tracker` 를 실행하면 파일이 생기는지 본다(대조 뒤 삭제).
- 기대: 변경 판에서는 `data/usage.db` 없음, 대조 판에서는 import 만으로 생김.
- 필수 여부(required): 예
- 실제: 서비스 종료 전 사본 `data/` 는 `runtime_cache.db scheduler_runtime_status.json v2_screener_status.json vcp_status.json` 뿐. 00:44:50 `ls data/usage.db` 「No such file or directory」. 대조: `git show 6efcb93^:services/usage_tracker.py` 를 사본에만 두고 사본 cwd 에서 import → `db_path …/infra079-copy/data/usage.db`, `-rw------- 16384 Sep 24 00:44 …/data/usage.db` 생성(결함 재현), 대조 뒤 두 파일 삭제
- 결과: 통과

## 실행 결과

- 1회차(2026-09-24 00:44, 기준 `6efcb93`): 필수 3/3 통과
- 이월한 발견: 없음(운영 서버 `data/usage.db` 정리는 설계 때부터 이 항목의 운영자 단계)
