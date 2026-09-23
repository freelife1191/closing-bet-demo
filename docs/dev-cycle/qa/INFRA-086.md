# [INFRA-086] `python scripts/init_data.py` 를 루트 밖에서 실행하면 종가 최신 파일이 `<cwd>/data` 에 생긴다 — QA 시나리오

- 대상: 격리 사본의 `scripts/init_data.py` 를 루트 밖 cwd 에서 CLI 로 실행(인자 없음, `all`), 그리고 같은 모듈을 import 만 하는 경로
- 구성 근거: `[INFRA-086]` 설계 승인(2026-09-24 00:23, `__main__` 블록 첫 줄 `os.chdir(BASE_DIR)` 하나, 모듈 수준 chdir 금지)
- 구성 2026-09-24 00:27 | 실행 (미실행)
- 검증 기준 커밋: (첫 커밋 후 기재)
- QA 엔진(engine): Claude Code. 사용자 진입 흐름은 운영자의 CLI 실행 하나이며 화면·API 흐름은 바뀌지 않는다. 진짜 UI 가 없는 CLI 라 브라우저 실측 대신 CLI 하네스로 검사한다. 하네스:
  `git archive HEAD` 사본에서 추적 파일 때문에 생긴 `data/` 를 지우고 원본 `venv` 를 APFS clone 으로 둔다(`data/` 는 비워 둔다. 원본 자료가 필요 없다). `.env` 계열은 두지 않고 사본의 `secrets/` 는 만들자마자 지운다.
  실제 수집·LLM·발송을 막으려고 **사본에서만** `init_data.py` 의 `if __name__ == '__main__':` 바로 앞에 같은 이름의 가짜 작업 다섯 개(`create_korean_stocks_list`·`create_daily_prices`·`create_institutional_trend`·`create_signals_log`·`create_jongga_v2_latest`)를 정의한다. `main()` 은 호출 시점에 전역 이름으로 찾으므로 가짜가 불린다. 가짜는 이름과 `os.getcwd()` 를 사본 밖 기록 파일에 남기고, `create_jongga_v2_latest` 가짜는 `engine/generator.py:244` 처럼 상대 경로 `data/` 에 표식 파일을 쓴다. 검사 대상인 `__main__` 블록과 chdir 줄은 건드리지 않는다.
  실행은 `env -i PATH=/usr/bin:/bin HOME=$HOME` 로 사본 밖 임시 디렉터리를 cwd 로 두고 `<사본>/venv/bin/python <사본>/scripts/init_data.py` 를 부른다. 원본 `data/`·`logs/`·3500·5501·운영 주소는 건드리지 않는다
- 기대값 출처: 설계 승인 범위, `scripts/run_full_update.py:9` 의 같은 chdir
- 단계(phase): 시나리오 구성 완료
- 필수 여부(required): 예

## 시나리오

### S-1. 인자 없는 실행이 루트에서 돈다 (결함 재현)
- 조작: 루트 밖 임시 cwd 에서 `init_data.py` 를 인자 없이 실행한다.
- 기대: exit 0, 가짜 기록 다섯 건의 cwd 가 모두 사본 루트, 표식 파일이 사본 `data/` 에 있고 임시 cwd 는 비어 있다.
- 필수 여부(required): 예

### S-2. `all` 하위 명령도 루트에서 돈다 (인접 갈래)
- 조작: 같은 방식으로 `init_data.py all` 을 실행한다.
- 기대: exit 0, 가짜 기록 네 건(종목·가격·수급·VCP)의 cwd 가 모두 사본 루트, 임시 cwd 는 비어 있다.
- 필수 여부(required): 예

### S-3. import 만 하면 cwd 가 바뀌지 않는다 (경계)
- 조작: 임시 cwd 에서 `python -c` 로 사본 루트를 `sys.path` 에 넣고 `import scripts.init_data` 한 뒤 `os.getcwd()` 를 출력한다.
- 기대: exit 0, 출력이 임시 cwd.
- 필수 여부(required): 예

### S-4. 변경 전 코드는 결함을 재현한다 (대조)
- 조작: 사본의 `init_data.py` 에서 chdir 두 줄만 뺀 판(변경 전 커밋 `8bfe438` 과 같은 `__main__`)에 같은 가짜를 넣고 S-1 을 반복한다.
- 기대: 가짜 기록의 cwd 가 임시 cwd, 표식 파일이 `<임시 cwd>/data` 에 생긴다.
- 필수 여부(required): 예

## 실행 결과

- (미실행)
