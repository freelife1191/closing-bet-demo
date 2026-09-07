# [INFRA-049] `.env` 를 셸이 실행하지 않게 한다 — QA 시나리오

- 대상: `scripts/env_value.sh`, `restart_all.sh`, `stop_all.sh`, `tests/scripts/test_env_value_sh.py`
- 구성 근거: `TODO.md` 의 `[INFRA-049]` 「QA 시나리오」 줄과 「확인할 것 하나」,
  계획 문서 `docs/superpowers/plans/2026-09-08-infra-049-env-source-removal.md`,
  `oh-my-claudecode:critic` 의 계획 검토 지적 일곱
- 구성 2026-09-08 01:12 | 실행 2026-09-08 01:12
- QA 엔진(engine): Claude Code — 화면이 없는 경로이므로 안전한 하네스와 실제 명령
- 단계(phase): 시나리오 구성 완료 | 실행 완료
- 반복(iteration): 3회 (코드 리뷰 지적 둘, 보안 리뷰 지적 셋을 반영하며 전체 재실행)
- baseline 상태: 기준값 수집 완료 (변경 전 `source` 방식의 값과 동작을 먼저 측정했다)
- 필수 여부(required): 예
- 결과: 통과
- 증거: 아래 각 시나리오의 명령과 출력
- 정리(cleanup): 임시 gunicorn(PID 11378) 종료 확인, `/tmp/infra049-*` 제거,
  스크래치패드의 돌연변이 사본과 임시 `.env` 제거

## 화면 대신 하네스를 쓰는 이유

이 항목이 고치는 것은 기동 스크립트가 `.env` 를 읽는 방식이라 화면이 없다. 설정 화면의
「저장」은 운영 `.env` 를 실제로 다시 쓰므로 누를 수 없고, `./restart_all.sh` 는 사용자가
방금 띄운 서비스를 죽인다. `tier-rules.md` §1-1 의 「화면이 없는 경로는 해당 CLI·안전한
하네스를 검사 대상으로 삼고 그 사실을 적는다」에 따라, 임시 디렉터리의 `.env` 와 임시
포트에 따로 띄운 프로세스를 검사 대상으로 삼았다.

**Next 는 전체 기동 대신 로더를 불렀다.** `next dev` 를 하나 더 띄우면 돌고 있는
next-server 와 `frontend/.next` 를 공유해 서로를 깨뜨린다. 그래서 Next 가 실제로 쓰는
`@next/env` 의 `loadEnvConfig` 를 같은 조건(`env -i`)으로 불렀다(S-4).

**임시로 띄운 프로세스에는 `SCHEDULER_ENABLED=false` 와 `NOTIFICATION_ENABLED=false` 를
함께 넘겼다.** 운영 `.env` 의 `NOTIFICATION_ENABLED` 는 `true` 이고 디스코드 웹훅과
텔레그램 토큰과 SMTP 자격 증명이 실제 값이다. `load_dotenv()` 가 `override=False` 이므로
환경으로 넘긴 `false` 가 이긴다.

## 시나리오

### S-1. 값에 셸 문법을 넣어도 명령이 실행되지 않는다 (회귀)
- 조작: 임시 디렉터리의 `.env` 에 `SMTP_HOST=x$(touch pwned_subst)`,
  ``SMTP_USER=y`touch pwned_backtick` ``, `SMTP_PASSWORD=z; touch pwned_semi`,
  `TELEGRAM_CHAT_ID=w touch pwned_space` 를 두고 `env_value` 로 각각 읽는다.
- 기대: 네 값이 리터럴 그대로 돌아오고, `pwned_*` 파일이 하나도 만들어지지 않는다.
- 필수 여부(required): 예
- 실제: 네 값 모두 리터럴로 돌아왔고 `pwned_*` 는 0개였다. 같은 `.env` 를 옛
  `set -a; source .env` 방식으로 읽으면 `pwned_subst` 가 실제로 만들어지는 것을 스크래치패드
  사본으로 확인했다. 검사가 잡을 결함이 실재한다.
- 결과: 통과
- 증거: `pytest tests/scripts/test_env_value_sh.py::test_env_value_does_not_execute_shell_syntax`
- 정리(cleanup): `tmp_path` 안에서만 만들어져 자동 삭제

### S-2. 세 파일 어디에도 `.env` 를 셸로 실행하는 줄이 없다 (회귀)
- 조작: `restart_all.sh`, `stop_all.sh`, `scripts/env_value.sh` 를 정규식
  `^\s*(?:source|\.)\s+\S*\.env\b` 와 `^\s*set\s+-a\b` 로 검사한다.
- 기대: 세 파일 모두 매칭 0건. 부분 문자열이 아니라 정규식을 쓰므로 `. .env` 와
  `source "$PROJECT_ROOT/.env"` 도 잡히고, 행 앞을 묶었으므로 `env_value.sh` 의 주석에
  들어 있는 같은 문구는 잡히지 않는다.
- 필수 여부(required): 예
- 실제: 세 파일 모두 매칭 0건. 변경 전에는 `restart_all.sh` 에서 매칭되어 검사가 실패했다.
- 결과: 통과
- 증거: `pytest tests/scripts/test_env_value_sh.py::test_startup_scripts_do_not_source_env`
- 정리(cleanup): 이 시나리오가 소유한 임시 자료 없음

### S-2b. 회귀 검사가 자기가 걷어낸 바로 그 표기를 잡는다 (리포트)
- 조작: 옛 `restart_all.sh:11` 의 한 줄 형태
  `[ -f .env ] && { echo "..."; set -a; source .env; set +a; }` 를 비롯해 여섯 표기를
  회귀 검사의 정규식에 직접 돌린다. 함께 오탐이 없어야 할 여섯 표기도 돌린다.
- 기대: 여섯 모두 잡히고, 오탐 여섯은 하나도 걸리지 않는다.
- 필수 여부(required): 예
- 실제: 처음 쓴 정규식(`^\s*` 로 행 앞을 묶은 것)은 **옛 한 줄 형태와 변수 경유를
  놓쳤다.** 즉 검사가 통과하면서도 자기가 대체한 코드가 되살아나는 것을 막지 못했다.
  `oh-my-claudecode:security-reviewer` 가 실측으로 찾았고 저도 재현했다. 앵커를 셸의
  명령 시작 자리(`^`·`;`·`&&`·`||`·`{`·`(`·`|`)로 바꾸고 주석을 먼저 걷어내니 여섯을 모두
  잡고 오탐 여섯을 모두 피한다.
- 근거: 리뷰가 제안한 「행 앞 앵커 제거 + 주석 제거」만으로는 오탐이 났다. 제가 쓴 오류
  메시지 `"❌ $1 의 값이 숫자가 아니다. .env 의 해당 줄을 확인하라"` 안의 `다. .env` 가
  걸렸기 때문이다. 리뷰는 문자열 리터럴에 `#` 이 없는 것만 확인했고 마침표는 보지 못했다.
- 결과: 통과
- 증거: `pytest ...::test_regression_regex_catches_the_line_it_replaced`
- 정리(cleanup): 이 시나리오가 소유한 임시 자료 없음

### S-3. export 없는 환경에서 Flask 가 정상 기동한다 (회귀)
- 조작: `env -i PATH=... HOME=... LANG=... SCHEDULER_ENABLED=false NOTIFICATION_ENABLED=false`
  로 gunicorn 을 임시 포트 5599 에 띄우고 `/health` 를 친다. 돌고 있는 5501 은 건드리지 않는다.
- 기대: HTTP 200. 로그에 `.env` 값을 못 읽어 생기는 오류가 0줄.
- 필수 여부(required): 예
- 실제: `HTTP 200`. 오류 0줄. 로그에
  `Scheduler is disabled in configuration. Skipping start.` 가 남아 스케줄러가 돌지 않은 것을
  확인했다. **이것이 `TODO.md` 의 「확인할 것 하나」가 요구한 실측이다.**
- 결과: 통과
- 증거: gunicorn 로그 `Listening at: http://127.0.0.1:5599 (11378)`, `curl` 이 돌려준 `200`
- 정리(cleanup): PID 11378 만 `kill`(`pkill -f gunicorn` 은 5501 까지 죽이므로 쓰지 않았다).
  5599 잔여 프로세스 0개 확인. `/tmp/infra049-backend.log` 와 `/tmp/infra049-gunicorn.pid` 제거

### S-4. export 없는 환경에서 Next 가 값을 얻는다 (회귀)
- 조작: `env -i` 로 띄운 node 에서 `@next/env` 의 `loadEnvConfig` 를 `frontend/` 에 대해
  부르고 다섯 키의 유무를 본다. 값은 출력하지 않는다.
- 기대: `FLASK_PORT`, `FRONTEND_PORT`, `NEXTAUTH_SECRET`, `ADMIN_API_TOKEN`,
  `INTERNAL_IDENTITY_SECRET` 다섯 줄 모두 `채워짐`.
- 필수 여부(required): 예
- 실제: 다섯 줄 모두 `채워짐`. 계획 단계의 같은 명령에서 `.env` 키 58개가 채워지는 것도
  확인했다. `frontend/.env` 는 루트 `.env` 의 심볼릭 링크이므로 같은 파일을 읽는다.
- 결과: 통과
- 증거: 위 명령의 출력 다섯 줄
- 정리(cleanup): 프로세스가 즉시 끝나므로 남는 것 없음

### S-5. 세 키의 값이 옛 방식과 같다 (인접)
- 조작: 실제 `.env` 에서 `FLASK_PORT`, `FRONTEND_PORT`, `FLASK_HOST` 를 `env_value` 와
  옛 `set -a; source .env` 방식으로 각각 읽어 비교한다. 값은 출력하지 않고 일치만 본다.
- 기대: 세 줄 모두 `같음`. 그리고 python-dotenv 의 `dotenv_values` 와도 같다.
- 필수 여부(required): 예
- 실제: 세 줄 모두 `같음`. python-dotenv 와의 비교도 검사에서 통과했다.
- 결과: 통과
- 증거: 위 대조 출력, `pytest ...::test_env_value_matches_dotenv_for_startup_keys`
- 정리(cleanup): 읽기만 했으므로 없음

### S-6. 포트 값이 오염되면 기동을 멈춘다 (인접)
- 조작: 임시 `.env` 에 `FLASK_PORT=5501 # 백엔드 포트` 를 두고 `env_port FLASK_PORT 5501` 을
  부른다.
- 기대: 종료 코드가 0이 아니고, 표준 출력이 비어 있으며, 표준 오류에 `FLASK_PORT` 가 있다.
- 필수 여부(required): 예
- 실제: 종료 코드 1, 표준 출력 빈 문자열, 표준 오류에 키 이름 포함. `case` 블록을 지운
  스크래치패드 사본에서는 종료 코드 0 과 오염된 값 `5501 # 백엔드 포트` 가 나왔다.
- 근거: 이 검사가 없으면 `stop_all.sh:38` 의 `lsof -ti :$port` 가 단어 분리로
  `lsof -ti :5501 '#' 백엔드 포트` 가 되어 PID 를 하나도 찾지 못하고, 58행의 최종 확인까지
  함께 실패해 **포트가 살아 있는데 「✅ Port 5501 freed.」를 출력한다.** 오염된 값으로 직접
  `lsof` 를 불러 재현했다(정상 3개 → 오염 0개).
- 결과: 통과
- 증거: `pytest ...::test_env_port_rejects_non_numeric_value`
- 정리(cleanup): `tmp_path` 안에서만 만들어져 자동 삭제

### S-6b. 지역 변수 이름이 키와 겹쳐도 상속값을 잃지 않는다 (리포트)
- 조작: `env_port` 를 키 이름 `value`, `_v`, `MYPORT` 로 각각 부르되 그 이름의 환경 변수를
  `99` 로 내보내고 `.env` 에는 그 키를 두지 않는다.
- 기대: 세 경우 모두 `99`.
- 필수 여부(required): 예
- 실제: 세 경우 모두 `99`. 고치기 전에는 키가 `value` 일 때 `7`(기본값)이 나왔다. `${!1}` 이
  이름으로 참조하므로 함수 안의 `local value` 자신을 가리켜 상속값이 조용히 무시된 것이다.
  `feature-dev:code-reviewer` 가 확신도 높음으로 지적하고 재현해 보였으며, 저도 재현한 뒤
  지역 변수 이름을 `_env_port_value` 로 바꾸었다.
- 결과: 통과
- 증거: 세 키에 대한 위 실행 출력
- 정리(cleanup): 스크래치패드의 임시 디렉터리 제거

### S-6c. 검사가 실패해도 `.env` 값이 출력에 새지 않는다 (리포트)
- 조작: 값 비교 어서트(`assert a == b`)와 불리언 어서트(`same = a == b; assert same, "..."`)를
  각각 실패시켜, pytest 출력에 값 리터럴이 몇 번 등장하는지 센다.
- 기대: 값 비교 형태는 여러 번 등장하고, 불리언 형태는 소스 줄 외에 등장하지 않는다.
- 필수 여부(required): 예
- 실제: 값 비교 3회, 불리언 1회(데모 소스에 적힌 리터럴 한 줄). 실제 검사 코드에는 값
  리터럴이 없으므로 0회다. `feature-dev:code-reviewer` 가 확신도 낮음으로 지적했으나 재현해
  보니 실재하는 유출 경로였다. 파서 일치 검사를 불리언 형태로 바꾸었다.
- 근거: 이 저장소는 「`.env` 값을 출력하지 않는다」를 규약으로 둔다. 검사 실패 경로도 그
  규약의 적용 대상이다.
- 결과: 통과
- 증거: 두 형태의 실패 출력에서 센 리터럴 등장 횟수
- 정리(cleanup): 데모 파일 제거

### S-6d. 키 이름에 셸 메타 문자가 있으면 거부한다 (리포트)
- 조작: `env_value` 와 `env_port` 에 키 이름 `a[$(touch pwned_key)]` 를 넘긴다.
- 기대: 두 함수 모두 종료 코드가 0이 아니고 `pwned_key` 가 만들어지지 않는다. 정상 키는
  그대로 값을 준다.
- 필수 여부(required): 예
- 실제: 두 함수 모두 거부하고 파일이 만들어지지 않았다. 정상 키는 `5501` 을 준다.
- 근거: 키 이름이 두 자리에서 코드로 평가된다. GNU sed 의 `s///e` 는 치환 결과를 셸에
  넘기므로 키가 `.*/명령/e;#` 이면 그 명령이 돌고(이 머신은 BSD sed 라 거부되는 것까지만
  확인), bash 의 간접 확장은 이름 안의 배열 첨자를 산술 평가하므로 `a[$(명령)]` 이면 그
  명령이 돈다. **후자는 bash 3.2 와 5.x 양쪽에서 실제로 파일이 만들어지는 것을
  확인했다.** 호출자가 리터럴 셋만 넘기는 지금은 닿지 않지만, 이 항목이 고치는 결함이
  바로 「데이터가 코드로 평가되는 자리」이므로 같은 자리를 새로 남기지 않는다.
- 결과: 통과
- 증거: `pytest ...::test_env_value_rejects_key_names_with_shell_metacharacters`
- 정리(cleanup): `tmp_path` 안에서만 만들어져 자동 삭제

### S-7. `.env` > 상속 > 기본값 순서가 옛 방식과 같다 (인접)
- 조작: 세 경우를 잰다. (1) `.env` 에 `FRONTEND_PORT=3500` 이 있고 호출자가 `4000` 을
  내보낸 상태, (2) `.env` 에 그 키가 없고 호출자만 `4000` 을 내보낸 상태, (3) 둘 다 없는 상태.
- 기대: 차례로 `3500`, `4000`, 기본값 `9999`. 옛 `set -a; source .env` 도 (2)에서 `4000` 을
  준다.
- 필수 여부(required): 예
- 실제: `3500`, `4000`, `9999`. 옛 방식의 기준선도 (2)에서 `4000` 이었다. `${!1}` 없이
  `VAR=$(env_value VAR)` 로만 쓰면 (2)가 `9999` 가 되어 순서가 깨진다.
- 결과: 통과
- 증거: `pytest ...::test_env_port_prefers_env_file_then_inherited_then_default`
- 정리(cleanup): `tmp_path` 안에서만 만들어져 자동 삭제

### S-8. 중복 줄에서 나중 것이 이긴다 (인접)
- 조작: 임시 `.env` 에 `FLASK_PORT=1111` 과 `FLASK_PORT=2222` 를 차례로 두고 읽는다.
- 기대: `2222`. bash 의 `source`, python-dotenv 의 `dotenv_values`, `@next/env` 가 모두
  그렇게 읽으므로 `tail -1` 이 그 동작에 맞춘 것이다.
- 필수 여부(required): 예
- 실제: `2222`
- 결과: 통과
- 증거: `pytest ...::test_env_value_takes_last_duplicate`
- 정리(cleanup): `tmp_path` 안에서만 만들어져 자동 삭제

### S-9. `.env` 가 없으면 빈 값을 주고 기본값이 걸린다 (인접)
- 조작: `.env` 가 없는 임시 디렉터리에서 `env_value FLASK_PORT` 를 부른다.
- 기대: 빈 문자열. 종료 코드 0.
- 필수 여부(required): 예
- 실제: 빈 문자열, 종료 코드 0. S-7 의 (3)에서 호출자의 기본값이 걸리는 것도 확인했다.
- 결과: 통과
- 증거: `pytest ...::test_env_value_is_empty_without_env_file`
- 정리(cleanup): `tmp_path` 안에서만 만들어져 자동 삭제

### S-10. 따옴표·인라인 주석·export 접두의 한계가 문서화된 대로 동작한다 (인접)
- 조작: 임시 `.env` 에 `QUOTED="5501"`, `COMMENTED=5501 # 백엔드 포트`, `export EXPORTED=ok`
  를 두고 각각 읽는다.
- 기대: 차례로 `"5501"`(따옴표 유지), `5501 # 백엔드 포트`(주석 유지), 빈 값(`export` 접두를
  읽지 못함). 옛 `source` 와 python-dotenv 는 셋 다 다르게 읽는다.
- 필수 여부(required): 예
- 실제: 기대대로였다. 이 시나리오는 결함을 막는 것이 아니라 **한계를 고정한다.** 세 키가
  언젠가 그 모양이 되면 값이 달라진다는 사실을 검사가 들고 말해 준다. 이 저장소의 `.env` 는
  159줄 가운데 21줄이 `KEY=값  # 설명` 모양이고 `.env.example` 에도 24줄 있으므로 가정이
  아니라 집필 관례다. 포트는 S-6 의 `env_port` 가 막는다.
- 결과: 통과
- 증거: `pytest ...::test_env_value_does_not_strip_quotes_or_inline_comments`
- 정리(cleanup): `tmp_path` 안에서만 만들어져 자동 삭제

### S-11. `scripts/env_value.sh` 가 없으면 기동을 멈춘다 (인접)
- 조작: `PROJECT_ROOT` 를 존재하지 않는 경로로 두고 두 스크립트가 쓰는 것과 같은
  `source ... || { echo; exit 1; }` 형태를 실행한다. 저장소 파일은 건드리지 않는다.
- 기대: 오류 메시지 출력 후 종료 코드 1. 파일이 있으면 종료 코드 0 으로 진행하고
  `env_port` 를 쓸 수 있다.
- 필수 여부(required): 예
- 실제: 없을 때 종료 코드 1, 있을 때 0 과 `env_port` 사용 가능. 두 스크립트 어디에도
  `set -e` 가 없어서 이 처리가 없으면 함수가 없는 채로 진행해 조용히 코드 기본값으로
  떨어진다.
- 결과: 통과
- 증거: 위 두 명령의 종료 코드
- 정리(cleanup): 이 시나리오가 소유한 임시 자료 없음

### S-12. 세 파일의 bash 문법이 유효하다 (인접)
- 조작: `bash -n restart_all.sh && bash -n stop_all.sh && bash -n scripts/env_value.sh`
- 기대: 종료 코드 0
- 필수 여부(required): 예
- 실제: 종료 코드 0
- 결과: 통과
- 증거: `OK` 출력과 종료 코드 0
- 정리(cleanup): 실행하지 않고 파싱만 하므로 없음

### S-13. 저장소 전체 검사가 통과한다 (인접)
- 조작: `source venv/bin/activate && pytest`
- 기대: 기존 1799 통과·2 skip 에 새 검사 8 이 더해져 1807 통과·2 skip. 실패 0.
- 필수 여부(required): 예
- 실제: `1807 passed, 2 skipped in 25.83s`, 종료 코드 0
- 결과: 통과
- 증거: pytest 출력
- 정리(cleanup): 이 시나리오가 소유한 임시 자료 없음

### S-14. 돌고 있는 운영 서비스가 무사하다 (인접)
- 조작: 임시 기동과 정리 전후로 `http://127.0.0.1:5501/health` 와
  `http://127.0.0.1:3500/` 를 친다.
- 기대: 양쪽 모두 200. 임시 프로세스를 죽인 뒤에도 200.
- 필수 여부(required): 예
- 실제: 임시 기동 중 `5501: 200`, `3500: 200`. 임시 프로세스 종료 후에도 `5501: 200`,
  `3500: 200`.
- 결과: 통과
- 증거: 두 차례의 `curl` 출력
- 정리(cleanup): `services/scheduler.lock` 의 수정 시각이 임시 기동 시각으로 갱신되었으나
  **지우지 않았다.** `lsof` 로 확인한 결과 그 파일을 잡고 있는 것은 운영 워커(PID 85039)이고,
  `.gitignore:61` 의 `services/*.lock` 대상이며, `restart_all.sh:83` 이 매 기동에서 지운다.

## 시크릿 확인 세 가지

`tier-rules.md` §1 이 시크릿에 닿는 변경에 요구하는 항목이다.

1. **통과** — `git ls-files` 로 확인한 결과 추적되는 `.env*` 는 `.env.example` 하나뿐이다.
2. **통과** — 새 코드가 출력하는 것은 키 이름만 담은 오류 메시지와 함수의 반환 통로인
   `printf '%s' "$value"` 뿐이다. 두 스크립트가 출력하는 것은 포트 번호이고 시크릿이 아니다.
   **오히려 유출면이 줄었다.** 옛 `set -a` 는 `.env` 전체를 환경 변수로 내보내 gunicorn 과
   npm 자식 프로세스에 넘겼고 그 환경은 프로세스 조회로 읽힐 수 있었는데, 이제 넘기지 않는다.
3. **통과** — `.env` 에 `NEXT_PUBLIC_` 접두 변수가 하나도 없고, 이번 변경도 늘리지 않았다
   (네 파일 모두 등장 0회).

## 실행 결과

- 필수 시나리오: 통과 18 / 전체 18
- 미통과 필수: 없음
- 재개 판정: 완료 가능
- 시나리오 밖에서 새로 발견: 둘. 아래 「이월한 발견」 참조

## 이월한 발견

- `.env` 와 `.env.production` 의 모드가 0644 라 같은 호스트의 모든 로컬 계정이 읽는다.
  `update_env_file` 이 기존 모드를 유지하므로 설정 화면으로는 좁아지지 않는다.
  → `[INFRA-053]`(P1). 파일 권한과 쓰기 경로 양쪽을 함께 고쳐야 하고 배포 절차도 봐야 해서
  이번 범위를 넘는다.
- `restart_all.sh:36` 의 `pkill -f "flask_app.py" "next dev" "npm.*dev"` 가 패턴을 셋
  넘겨 사용법 오류로 끝나고 아무것도 죽이지 않는다. `|| true` 가 삼켜 조용하다.
  → `[INFRA-054]`(P2). 이번 변경이 만든 것이 아니고 정리 동작 자체를 손봐야 한다.
