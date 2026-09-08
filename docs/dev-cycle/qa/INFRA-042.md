# [INFRA-042] 관리자 라우트 게이트 — QA 시나리오

- 대상: 화면이 아니라 서버 측 인가 게이트다. 아래 「화면 대신 하네스를 쓰는 이유」를 본다
- 구성 근거: `docs/superpowers/plans/2026-09-08-infra-042-admin-route-guard.md` +
  계획 검토(`critic`, `ACCEPT`), 코드 리뷰(`feature-dev:code-reviewer`, 결함 없음),
  보안 리뷰(`security-reviewer`), 적대적 리뷰(`general-purpose`), Codex 교차 검토의 지적
- 구성 2026-09-08 10:20 | 실행 10:25 | 범위 확대 후 재실행 10:58 | 회귀 수정 후 재실행 11:15
- QA 엔진(engine): Claude Code. `/qa-only` 대신 하네스로 구성했다(아래 절)
- 단계(phase): 시나리오 구성 완료 | 실행 완료
- 반복(iteration): 3회. 1회차는 게이트 여섯 자리, 2회차는 리뷰가 찾은 여섯을 더한 열두
  자리, 3회차는 잘린 리뷰 회신이 찾은 화면 쪽 회귀를 고친 뒤
- baseline 상태: 기준값 수집 완료. 사이클 전 열두 라우트에 서버 측 검사가 없었고, 화면의
  `useAdmin` 조건부 렌더링만이 방어였다
- 필수 여부(required): 예
- 결과: 통과 (필수 11/11)
- 증거: 아래 각 시나리오의 실제 값
- 정리(cleanup): 돌연변이 사본 일곱 벌 삭제. 운영 `.env` 에 쓰지 않았고 알림을 발송하지
  않았으며 서비스도 재기동하지 않았다

## 범위가 세 차례 늘어난 경위

**최초 승인은 여섯 자리였고 최종 게이트는 열두 자리다.** 늘어난 경위를 적어 두는 이유는,
같은 누락이 다음 라운드에서 되풀이되지 않게 하기 위해서다.

| 계기 | 추가된 라우트 | 놓친 원인 |
|---|---|---|
| 최초 승인 | `jongga-v2/run`·`reanalyze-gemini`·`message`, `signals/run`, `init-data`, `start-update` | — |
| 적대적 리뷰 F2 | `stop-update`, `finish-update`, `update-item-status` | 분류 기준을 「화면이 버튼을 누구에게 보이는가」로 잡아 **서버 쪽 형제 라우트**를 세지 못했다 |
| 보안 리뷰 4-2 + 전수 조사 | `signals/reanalyze-failed-ai`, 그 `/stop`, `jongga-v2/analyze` | TODO 가 나열한 목록을 그대로 믿고 저장소를 독립적으로 훑지 않았다 |

**두 번의 확대가 같은 원인이다.** 마지막에야 POST 라우트 30개를 전수 조사해 게이트 없는
19개를 가려냈다. 그 조사가 오판 하나도 막았다. `/user/quota/recharge` 는 관리자 전용으로
보였지만 `Sidebar.tsx:286` 의 `{!isAdmin && ...}` 안에 있어 **비관리자에게만 보이는**
버튼이다. 게이트를 두르면 기능이 죽는다.

`signals/reanalyze-failed-ai` 는 중단 계열과 같은 비대칭을 갖고 있었다. `vcp_status` 를
`signals/run` 과 공유하므로 익명 요청이 게이트 붙은 라우트를 잠글 수 있었다.

## 화면 대신 하네스를 쓰는 이유

`tier-rules.md` [3] 검증 3번이 「화면이 없는 경로는 해당 CLI·안전한 하네스를 검사 대상으로
삼고 그 사실을 적는다」고 정한다. 이 항목이 바꾸는 것은 서버의 인가 판정이며 **화면에는
아무 변화가 없다.** 열두 라우트가 이미 관리자에게만 버튼을 보이고 있었기 때문이다.

**화면을 쓸 수 없는 이유가 둘 더 있다.**

첫째, 이 게이트를 화면에서 재현하려면 관리자로 로그인해 버튼을 눌러야 하는데 그 버튼들이
**전부 비용이 들거나 되돌릴 수 없다.** `jongga-v2/message` 는 운영 디스코드·텔레그램 채널로
실제 종가베팅 시그널을 발송하고, `jongga-v2/run` 과 `signals/run` 은 LLM 호출 비용을 낸다.
이번 라운드의 안전 제약이 그 경로를 금지한다.

둘째, **떠 있는 워커는 옛 코드를 들고 있다.** gunicorn 이 `--reload` 없이 기동하므로 지금
화면에서 눌러도 게이트가 없는 옛 코드가 돈다. 이 사실은 이 사이클의 결함이 아니라 배포
성질이며 다음 재기동에서 해소된다. 저장소의 기존 learning `gunicorn-needs-hup-before-qa` 가
같은 것을 적고 있다.

그래서 동적 시나리오는 Flask 검사 클라이언트로 같은 등록 함수를 직접 세워 친다. 검사하는
코드 경로는 동일하다. **의존성은 「불리면 `AssertionError` 를 내는 가짜」로 넣어, 게이트가
없을 때 호출이 실제로 일어났다는 것을 검사가 직접 증명하게 했다.** 실제 발송 함수는 어느
시나리오에서도 부르지 않는다.

**프런트엔드 검사는 전체로 돌렸다.** 이번 변경이 `frontend/` 에서 건드린 것은
`src/lib/adminEmails.test.ts` 하나지만, 게이트를 열두 자리로 늘린 뒤 스위트 전체를 다시
돌려 54파일 349건이 통과하는 것을 확인했다. 타입 검사도 전체로 돌렸다.

## 시나리오

### S-1. 신원 없는 발송 요청이 403 을 받고 발송 준비에 닿지 않는다 (핵심)
- 조작: `register_jongga_execution_routes` 를 의존성 전부 실패 가짜로 등록하고, 신원 없이
  `POST /jongga-v2/message` 를 보낸다.
- 기대: 403 과 `{"error": "Forbidden"}`. 그리고 `resolve_jongga_message_filename` 이 불리지
  않는다.
- 근거: 이 라우트가 열둘 중 가장 무겁다. `Messenger().send_screener_result` 로 **실제 종가
  베팅 시그널 메시지**를 보내므로 구독자는 정상 발송과 구분하지 못한다.
- 실행: `pytest tests/app/test_admin_gated_routes.py::test_jongga_message_refuses_anonymous_even_with_force`
- 결과: **통과.**
- 필수 여부(required): 예

### S-2. `{"force": true}` 로도 우회되지 않는다
- 조작: S-1 과 같되 본문에 `{"force": true}` 를 넣는다.
- 기대: 같다. 403.
- 근거: `force` 는 `kr_market_jongga_execution_routes.py:216` 에서
  `claim_jongga_notification_send` 중복 가드를 통째로 건너뛰는 값이다. 게이트가 없으면
  **횟수 제한 없이** 발송할 수 있다. 게이트는 그보다 앞에 있어야 한다.
- 결과: **통과.** S-1 과 같은 검사가 `force` 를 넣은 본문으로 친다.
- 필수 여부(required): 예

### S-3. 관리자가 아닌 신원도 거부된다
- 조작: `g.user_email` 을 `someone@example.com` 으로 세우고 친다.
- 기대: 403.
- 근거: 「신원이 있다」와 「관리자다」는 다르다. 신원 유무만 보는 게이트로 잘못 구현하면 이
  검사가 잡는다.
- 실행: `pytest tests/app/test_route_guards.py::test_non_admin_identity_is_refused`
- 결과: **통과.**
- 필수 여부(required): 예

### S-4. 관리자 신원은 통과한다
- 조작: `ADMIN_EMAILS=admin@example.com` 을 세우고 같은 이메일로 친다.
- 기대: 200 과 정상 응답.
- 근거: **막는 것만 확인하면 통과 판정이 무의미하다.** 게이트가 전부를 막아도 S-1~S-3 은
  통과한다. 정상 경로를 함께 재야 한다.
- 실행: `pytest tests/app/test_route_guards.py::test_admin_identity_passes` 와
  `...::test_signals_run_passes_for_admin`
- 결과: **통과.** 후자는 라우트 등록 경로까지 함께 밟는다.
- 필수 여부(required): 예

### S-5. OPTIONS preflight 는 신원 없이 통과한다
- 조작: 신원 없이 `OPTIONS /jongga-v2/reanalyze-gemini` 를 보낸다.
- 기대: 200.
- 근거: `app/__init__.py:171` 의 `before_request` 가 OPTIONS 에서 일찍 반환해 `g.user_email`
  을 세우지 않는다. 게이트가 여기를 막으면 preflight 가 403 을 받아 **브라우저가 본 요청을
  아예 보내지 않는다.** 관리자에게도 화면이 멈춘다.
- 구멍이 아닌 근거: 게이트가 **뷰를 부르지 않고** `current_app.make_default_options_response()`
  로 끝낸다. preflight 는 200 과 `Allow` 헤더를 그대로 받고 뷰는 어떤 경우에도 불리지 않는다.
- **1회차의 해법을 왜 버렸는가.** 처음에는 OPTIONS 를 뷰로 통과시키고 「`methods` 에 OPTIONS
  를 두는 라우트가 저장소에 하나뿐이고 그 뷰가 첫 줄에서 빠진다」를 근거로 삼았다. 세 리뷰
  (보안·적대적·Codex)가 **각각 독립적으로** 같은 결론을 냈다. 그 불변식을 지키는 것이 주석
  뿐이면, 다음에 OPTIONS 를 `methods` 에 두면서 조기 반환을 빠뜨린 라우트가 생기는 순간 그
  자리가 통째로 열린다. 발송 핸들러가 같은 파일에 있다.
- **실측으로 재현한 것.** Flask 는 `methods` 에 OPTIONS 를 적으면 `provide_automatic_options`
  가 False 가 되어 뷰를 부르는데, **그 요청에 본문을 실을 수 있다.** `curl -X OPTIONS -d ...`
  한 줄이 무인증으로 뷰에 닿는 것을 확인했다. 그래서 갈래 자체를 원천 차단했다.
- 실행: `pytest ...::test_options_preflight_passes_without_identity`,
  `...::test_jongga_reanalyze_preflight_passes_without_identity`,
  `...::test_options_does_not_reach_the_view_even_with_a_body`
- 결과: **통과.** 마지막 검사가 본문을 실은 OPTIONS 로 쳐서 뷰가 불리지 않음을 증명한다.
- 필수 여부(required): 예

### S-6. 나머지 라우트도 신원 없이 거부된다
- 조작: `signals/run`, `init-data`, `jongga-v2/run`, `system/start-update` 를 각각 친다.
  2회차에 늘어난 여섯 가운데 중단 계열 셋(`stop-update`, `finish-update`,
  `update-item-status`)은 `parametrize` 로 묶어 같은 형태로 친다.
- 기대: 전부 403.
- **중단 계열을 왜 더했는가.** 적대적 리뷰 F2 가 짚은 비대칭이다. `start-update` 만 막으면
  익명이 `stop-update` 로 관리자가 돌리던 갱신을 중단시키고, `finish-update` 로 진행 중인
  작업을 끝난 것처럼 표시할 수 있다. 셋은 `start-update` 와 **같은 상태 파일**을 쓴다.
  들어가는 문만 잠그고 나오는 문을 열어 두면 잠근 의미가 없다.
- `system/start-update` 의 검사 설계를 밝혀 둔다. `load_update_status` 만 통과하는 가짜로
  두고 `start_update` 와 `run_background_update` 를 실패 가짜로 두었다. 라우트가
  `load_update_status` 를 먼저 부르고 `isRunning` 을 본 뒤에야 스레드 기동에 닿으므로
  (`common_update_routes.py:130-136`), 그것까지 실패 가짜로 두면 게이트가 없을 때 첫 호출에서
  터져 「403 이 났다」는 재지만 **「스레드가 뜨지 않았다」는 증명하지 못한다.** 계획 검토가
  짚어 준 것이다.
- 결과: **통과.** 열한 자리 모두.
- 필수 여부(required): 예

### S-7. 게이트를 붙여도 기존 위임 동작이 그대로다
- 조작: `tests/app/test_kr_market_jongga_execution_routes_refactor.py` 12건을 돌린다.
- 기대: 전부 통과.
- 근거: 게이트를 붙이자 이 파일의 5건이 403 을 받아 깨졌다. 열두 검사를 각각 고치는 대신
  `_create_client` 한 자리에 관리자 신원을 세우고 `autouse` 픽스처로 `ADMIN_EMAILS` 를
  두었다. **그 `before_request` 도 OPTIONS 에서 일찍 반환하게 해** `:228` 의 OPTIONS 검사가
  신원 없이 200 을 받는 상태를 그대로 유지한다.
- 결과: **통과, 12/12.** 코드 리뷰가 「검사 의미가 훼손되지 않았다」를 독립적으로 확인했다.
- 필수 여부(required): 예

### S-8. 두 언어의 관리자 판정이 같은 답을 낸다
- 조작: 공유 케이스 13개를 파이썬과 타입스크립트 양쪽에서 돌린다.
- 기대: 양쪽 13/13 일치.
- 근거: 같은 규칙이 `services/admin_helpers.py` 와 `frontend/src/lib/adminEmails.ts` 에 두 벌
  있는데 일치를 강제하는 검사가 없었다. 한쪽만 고치면 **버튼은 보이는데 요청이 403 을 받는**
  상태가 된다.
- 케이스 셋이 각각 다른 오구현을 겨냥한다. 「부분 일치」는 접두사 비교를, 「다른 항목에
  붙어도」는 쪼개지 않은 원본 문자열 비교를, 「줄바꿈은 구분자가 아니다」는 한쪽만
  `split(/[,\n]/)` 로 고치는 변경을 잡는다. 하나만 남기면 나머지가 통과한다.
- 실행: `pytest tests/services/test_admin_helpers.py` (14건) +
  `npx vitest run src/lib/adminEmails.test.ts` (18건)
- 결과: **통과.**
- **알려진 천장.** 파이썬 `str.strip()` 과 자바스크립트 `trim()` 은 공백으로 보는 문자
  집합이 달라서 U+001C·U+0085 는 파이썬만, U+FEFF(BOM) 는 자바스크립트만 제거한다(양쪽
  런타임에서 실측). 그런 입력은 두 구현이 서로 다른 답을 내므로 공유 파일로 표현할 수 없다.
  `ADMIN_EMAILS` 가 `EDITABLE_ENV_KEYS` 에 없어 유입 경로가 `.env` 수작업 편집뿐이므로 별도
  항목으로 올리지 않고 케이스 파일의 `_ceiling` 에 적었다.
- 필수 여부(required): 예

### S-9. 돌연변이 일곱이 각각 다른 검사를 실패시킨다
- 조작: 저장소 파일을 고치지 않고 스크래치패드에 `app/`·`services/`·`tests/` 사본을 만들어
  회귀를 하나씩 심는다. **cwd 를 사본으로 옮기고 `__file__` 로 로드 위치를 확인한 뒤** 쟀다.
  `PYTHONPATH` 에만 얹고 저장소 루트에서 돌리면 `sys.path[0]` 이 빈 문자열이라 원본 모듈이
  먼저 잡혀 돌연변이가 하나도 안 잡힌다(`[INFRA-050]` 라운드에서 겪은 함정).
- 기대: 각 돌연변이가 의도한 검사를 실패시키고 나머지는 통과한다.
- 결과: **통과.**

  | 돌연변이 | 실패 | 통과 | 걸린 자리 |
  |---|---|---|---|
  | 1. 게이트를 무동작으로 | 8 | 17 | 거부 검사 여섯 + 데코레이터 검사 둘. 로그에 「게이트를 지나 실행 경로에 도달했다」가 실제로 찍혔다 |
  | 2. OPTIONS 갈래 제거 | 3 | 22 | preflight 검사 둘 + **기존 검사** `test_reanalyze_gemini_route_options_short_circuit` |
  | 3. `functools.wraps` 제거 | 17 | 8 | 엔드포인트 이름 충돌로 등록 자체가 깨진다 |
  | 4. `message` 한 자리의 데코레이터 순서 뒤집기 | 1 | 7 | 그 자리만 정확히 |
  | 5. OPTIONS 를 뷰로 되돌림 | 1 | 16 | 본문을 실은 OPTIONS 검사 |
  | 6. `message` 의 게이트 한 줄 제거 | 2 | 11 | 그 라우트의 거부 검사 + 목록 불변식 검사 |
  | 7. `notification/send` 의 인라인 게이트 무동작 | 1 | 12 | 목록 불변식 검사만 |

  **측정 범위가 회차마다 다르다.** 1~4 는 게이트가 여섯 자리이던 1회차에 신규 검사 25건을
  대상으로, 5~7 은 열두 자리로 늘린 뒤 해당 검사 파일을 대상으로 쟀다. 그래서 합계가
  일치하지 않는다. 각 행의 「실패 + 통과」가 그때의 대상 건수다.

  **돌연변이 2 가 기존 검사를 깨뜨리는 것이 중요하다.** OPTIONS 예외를 나중에 누가 지우면
  이번에 새로 쓴 검사뿐 아니라 종전부터 있던 검사가 함께 빨간불이 된다. 회귀 보호가 두 겹이다.

  **돌연변이 4 는 계획이 「조용히 깨진다」고 예고한 자리다.** `@route` 와 `@require_admin` 의
  순서를 뒤집으면 게이트를 지나지 않는 원본이 등록되는데, 검사가 그 한 자리만 정확히 잡았다.

  **돌연변이 7 은 데코레이터를 쓰지 않는 자리도 지켜지는지 잰다.** `notification/send` 는
  뷰 몸통의 `if` 문으로 같은 판정을 하는데, 그 한 줄을 무동작으로 바꾸자
  `목록에 있는데 게이트가 없다: ['/api/notification/send']` 로 정확히 실패했다.
- **`sys.path` 함정을 피한 방법.** 사본을 `PYTHONPATH` 에만 얹고 저장소 루트에서 pytest 를
  돌리면 `sys.path[0]` 이 빈 문자열(= 저장소 루트)이라 **원본 모듈이 먼저 잡혀 돌연변이가
  하나도 안 잡힌다.** `[INFRA-050]` 라운드에서 실제로 겪어 1회차 수치가 틀렸던 함정이다.
  매번 cwd 를 사본으로 옮기고 `__file__` 로 로드 위치를 찍어 확인한 뒤 쟀다.
- 정리: 사본 일곱 벌 삭제 완료. 저장소 작업 트리는 측정 전후가 같다(`git status` 로 확인).
- 필수 여부(required): 예

### S-10. 게이트 목록과 실제 게이트가 일치한다 (불변식)
- 조작: `create_app()` 으로 앱을 세우고 `url_map` 을 훑어, `is_admin_email` 을 참조하는 POST
  라우트의 경로를 모아 선언한 `GATED_ROUTES` 열셋과 양방향으로 비교한다.
- 기대: 어느 방향으로도 차집합이 없다.
- 근거: 적대적 리뷰 F7 이 짚었다. 라우트를 이름으로 하나씩 여는 검사만 두면 **열넷째 라우트가
  조용히 무검사로 들어온다.** 인가 경계를 한 자리에 모아 두어야 다음 사람이 목록만 보고
  판단할 수 있다.
- 목록이 뜻하는 것은 「데코레이터가 붙은 자리」가 아니라 「관리자 전용 라우트」다. 그래서
  종전부터 인라인 `if` 로 닫혀 있던 `/api/notification/send` 도 목록에 넣었다. 이 자리는
  이번에 손대지 않았고, 목록에 넣은 것은 **누가 그 게이트를 지우면 잡히게 하려는 것**이다.
- 소지 비밀로 닫은 자리는 대상이 아니다. `verify_admin_api_token` 은 「이 사람이 누구인가」가
  아니라 「이 값을 아는가」를 보므로 `is_admin_email` 을 부르지 않는다.
- 실행: `pytest tests/app/test_admin_gated_routes.py::test_gated_route_list_matches_reality`
- 결과: **통과.** 돌연변이 6·7 이 양쪽 방향을 각각 잡는 것도 확인했다.
- 필수 여부(required): 예

### S-11. 전체 검사와 시크릿 확인
- 실행: `./venv/bin/python -m pytest -q` / `cd frontend && npm run type-check` /
  `cd frontend && npm run test -- --run`
- 결과: **통과.** `1850 passed, 2 skipped`, 종료 코드 0. 사이클 전 1818 이었으므로 +32 다.
  `type-check` 종료 코드 0, vitest `54 passed (54) / 349 passed (349)` 종료 코드 0.
- **화면 회귀를 고친 뒤 셋을 다시 돌려 같은 결과를 확인했다**(11:15). 중지 버튼의 렌더 조건은
  기존 검사가 덮지 않는 자리라 수치가 변하지 않는다. 그 조건 자체는 바로 위 두 자리가 이미
  쓰는 형태를 그대로 따랐고, 근거를 그 자리 주석에 적었다.
- **종료 코드를 파이프 없이 다시 쟀다.** 처음에 `npm run type-check 2>&1 | tail -20` 뒤에
  `${PIPESTATUS[0]}` 로 찍었더니 zsh 에서 빈 값이 나왔고, 파이프라인 마지막이 `echo` 라
  전체 종료 코드는 언제나 0 이었다. 이번 라운드가 `git add` 에서 지적한 것과 같은 종류의
  거짓 통과라 리다이렉트로 바꿔 `exit=0` 을 직접 확인했다.
- `tier-rules.md` §1 의 시크릿 확인 세 가지:
  - 추적되는 `.env` 계열 파일은 `.env.example` 하나뿐이다(`git ls-files`).
  - 게이트 응답 본문은 `{"error": "Forbidden"}` 뿐이고 값을 싣지 않는다.
  - `NEXT_PUBLIC_` 목록에 관리자 토큰이나 `ADMIN_EMAILS` 가 없다. 걸린 것은 「이 값은
    `NEXT_PUBLIC_` 을 붙이지 않는다」고 적은 주석 한 줄이다.
  - 새로 만든 `tests/fixtures/admin_email_cases.json` 은 `example.com`·`evil.test` 예시
    주소만 담는다.
- 운영 `.env` 를 읽지도 쓰지도 않았고 알림을 발송하지 않았다.
- 필수 여부(required): 예

## 이번 라운드에서 하지 않은 것

- **부류 B 셋**(`kr/refresh`, `market-gate/update`, `config/interval`)에 게이트를 두르지
  않았다. `frontend/src/app/dashboard/kr/page.tsx` 가 `useAdmin` 을 import 조차 하지 않아
  일반 사용자에게 노출된 버튼이고, 관리자 전용으로 바꿀지가 제품 정책 결정이다.
  다만 `kr/refresh` 는 성격이 다르다는 것이 적대적 리뷰 F1 로 드러났다. 그 라우트가
  `_resolve_common_update_handlers()` 로 `/init-data`·`/start-update` 와 **같은 함수와 같은
  상태 파일**을 쓰므로, 익명 요청이 LLM 비용을 유발하고 `isRunning` 을 세워 방금 잠근 자리를
  거꾸로 잠글 수 있다. 화면 노출 여부와 무관한 서버 쪽 결함이라 별도 항목으로 이월했다.
- **부류 C 넷**(모의투자)도 두르지 않았다. 계정이 전역 하나라 관리자 게이트로 막으면 기능이
  죽는다. 해법이 소유자 분리이고 `services/paper_trading.py` 는 위험 경로다.
- **부류 D**(`reanalyze/gemini`)는 손댈 것이 없다. 이미 401 로 닫혀 있고 화면 호출자도 없다.
- **기존 게이트 두 자리**를 데코레이터로 바꾸지 않았다. 승인 범위 밖이고 이미 닫힌 자리라
  회귀 위험만 새로 생긴다. 다만 그중 `/api/notification/send` 는 S-10 의 목록에 넣었다.
  구현을 바꾸지 않고 **누가 그 게이트를 지우면 잡히게** 하는 것이 목적이다.

## 리뷰에서 반영한 것

| 리뷰 | 판정 | 반영 |
|---|---|---|
| `oh-my-claudecode:critic` (계획) | `REVISE` → `ACCEPT` | 지적 열 전부. 아래에 성격별로 적는다 |
| `/ponytail-review` | -18줄 가능 | 넷 전부 적용해 `route_guards.py` 를 54→49줄로 줄였다 |
| `feature-dev:code-reviewer` | 결함 없음 | 확신도 낮은 관찰 셋 가운데 둘을 반영했다 |
| `oh-my-claudecode:security-reviewer` | 지적 있음 | 4-2(`signals/reanalyze-failed-ai` 무방비)를 받아 게이트를 붙였다. OPTIONS 갈래 차단도 이 리뷰가 함께 짚었다 |
| 적대적 리뷰 (`general-purpose`) | 지적 있음 | F1 이월, F2 중단 계열 셋 추가, F7 목록 불변식 검사 신설 |
| Codex 교차 검토 | 지적 있음 | OPTIONS 갈래에서 뷰 호출 제거 |

**세 리뷰가 독립적으로 같은 결론을 낸 자리가 하나 있다.** 보안·적대적·Codex 가 각각
OPTIONS 갈래에서 뷰를 부르지 말라고 했다. 실측으로 확인하고 고쳤다(S-5).

**적대적 리뷰의 F1 은 앞선 세 리뷰가 모두 놓친 것이다.** 제가 라우트를 「화면이 버튼을
누구에게 보이는가」로 분류했기 때문에, 화면에 없더라도 **서버에서 같은 함수를 공유하는 형제
라우트**를 세지 못했다. 분류 기준 자체의 결함이라 경위를 문서 앞쪽에 표로 남겼다.

**두 리뷰의 잘린 나머지를 받아 반영했다.** 그 회신이 **이번 변경이 만든 회귀 하나**를
찾았다(N1). `/system/stop-update` 에 게이트를 붙였는데 화면의 중지 버튼 렌더 조건이
`{updating && (` 그대로라 비관리자에게도 그 버튼이 보이고, 누르면 403 이 나는데
`handleStopUpdate` 의 `catch` 가 `console.error` 뿐이라 **화면에 아무 반응도 없다.**
`data-status/page.tsx:553` 에 `!isAdminLoading && isAdmin &&` 를 더해 닫았다. 바로 위
`:537`·`:547` 이 이미 쓰는 형태다.

**이것이 계획이 부류 B 를 미룬 바로 그 이유다.** 계획 문서가 「화면이 일반 사용자에게 그
버튼을 보이므로 게이트를 세우면 403 이 난다」고 적어 두었는데, F2 를 반영하며 게이트만 붙이고
그 예측을 확인하지 않았다. **서버 게이트를 세울 때는 그 라우트를 부르는 화면 자리를 반드시
함께 본다.**

같은 회신이 나머지 다섯 게이트는 화면과 어긋나지 않음을 확인해 주었다. `jongga-v2/analyze`·
`finish-update`·`update-item-status` 는 `frontend/src` 에 호출자가 없고,
`signals/reanalyze-failed-ai` 와 그 `/stop` 은 `vcp/page.tsx:713` 의 `if (!isAdmin)` 을
거친다. 세 경로를 HTTP 로 부르는 서버 측 코드도 없어 갱신 파이프라인이 끊기지 않는다.

**F7 이 짚은 것은 검사의 형태다.** 라우트를 이름으로 하나씩 여는 검사만 두면 다음에 추가되는
라우트가 조용히 무검사로 들어온다. `url_map` 을 훑어 목록과 실제를 대조하는 검사로 닫았다
(S-10). 그 과정에서 종전 구현이 `__wrapped__` 유무로 거르고 있어 인라인 게이트를 놓치는 것도
드러나 함께 고쳤다.

**계획 검토가 실행을 막는 것 둘을 잡았다.** 뷰 함수 이름을 `run_jongga_v2_route` 로 적었으나
실제는 `run_jongga_v2_screener_route` 라 붙일 자리를 못 찾는다. 그리고 `git add` 목록에 아직
없는 QA 문서가 들어 있어, 실행하면 `fatal` 로 아무것도 스테이징하지 않으면서 **종료 코드 0**
을 내고 이어지는 `git diff --cached --check` 도 빈 인덱스를 보고 `exit=0` 을 낸다. 두 신호가
모두 통과로 보인다. 실측으로 재현했고 `--name-only` 의 줄 수를 함께 세도록 고쳤다.

**제가 라우트 하나를 빠뜨린 것도 계획 검토가 찾았다.** 「14개를 세 부류로」라고 적고 13개만
분류했다. 빠진 것이 `reanalyze/gemini` 이고, 그 근거를 「일반 사용자 기능이라서」에서 「이미
401 로 닫혀 있어서」로 바꿨다. 앞의 서술로 두면 다음 감사가 같은 라우트를 다시 올린다.

**`CLAUDE.md` 의 사실 오류를 두 번 정정했다.** 첫 번째는 계획 검토가, 두 번째는 적대적·보안
리뷰가 잡았다.

1. 「Next 라우트 핸들러가 기동 시점의 값을 들고 있다」가 틀렸다. `route.ts:31` 은 함수 안이라
   매번 읽고, 모듈 최상위인 것은 `:17` 의 `FLASK_BASE` 다. 재기동이 필요한 진짜 이유는
   `process.env` 를 `.env` 에서 채우는 것이 기동 한 번뿐이고 `next start` 는 다시 읽지 않기
   때문이다. 결론은 같지만 근거가 달랐다.
2. 그 정정 뒤에 새로 쓴 문장도 틀렸다. 「설정 화면으로 바꾸면 워커 하나만 바뀐다」고 적었는데
   `ADMIN_EMAILS` 와 `ADMIN_API_TOKEN` 은 **둘 다 `EDITABLE_ENV_KEYS` 밖**이라 그 화면으로
   아예 바꿀 수 없다. 관리자가 화면에서 자기 자신을 잠그는 것을 막는 의도적 설계다. 막다른
   길로 안내하는 서술이었다. 두 키의 실제 차이는 **폐기 수단이 하나인가 둘인가**다.
   `ADMIN_EMAILS` 는 NextAuth 로그인을 끊는 두 번째 길이 있고 `proxy.ts` 가 매 요청
   `getToken` 하므로 재기동 없이 즉시 듣는다. 토큰 뒤에는 계정이 없어 그 길이 없다.
   `IDENTITY_TTL_SECONDS`(120초)를 폐기 수단으로 오해하지 말라는 경고도 함께 적었다. 그것은
   서명의 신선도만 정하고 인가와 무관하며, 만료되면 `proxy.ts` 가 다시 서명하는데 그 경로는
   `ADMIN_EMAILS` 를 보지 않는다.

보안 리뷰가 더 넓은 것도 짚었다. `[INFRA-042]` 이후로는 관리자 전용으로 닫은 라우트 열둘의
판정이 `INTERNAL_IDENTITY_SECRET` 으로 서명된 신원에 걸려 있고 그 안에 실제 발송 경로가
들어 있다. 회전 대상을 `ADMIN_API_TOKEN` 하나로 좁혀 생각하면 안 된다는 것을 적었다.

**코드 리뷰가 짚은 것 가운데 하나는 이 게이트의 한계다.** 판정 근거인 `g.user_email` 은
`verify_identity_header` 가 꺼낸 값인데 그 서명이 경로·메서드·nonce 에 묶이지 않는다. 한
경로에서 얻은 서명을 유효 기간 안에 다른 경로로 재생할 수 있다는 뜻이다. 이번 변경이 만든
결함이 아니라 물려받은 성질이고 `IDENTITY_TTL_SECONDS` 가 120 초라 창이 좁다. TODO 에 적었다.
