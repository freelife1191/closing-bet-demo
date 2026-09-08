# INFRA-063 구현 보고

## 변경

- `app/routes/kr_market_jongga_execution_routes.py`의 `POST /jongga-v2/message`에서 `require_admin` 통과 뒤, 발송 처리와 `execute_json_route` 바깥에 요청 경계를 둔다.
- JSON MIME이 아니거나 MIME이 없으면 입력·조회·guard·발송을 시작하지 않고 `415`를 돌려준다.
- JSON MIME의 빈 본문과 문법 오류는 `BadRequest`를 고정 로그만 남기고 `400`으로 처리한다. JSON `null`·배열·문자열·숫자·불리언은 `400`으로 처리한다.
- 기존 정상 JSON 객체, 중복 방지, `force`, 발송 오류 뒤 claim 해제와 재시도 동작은 그대로 둔다.

## TDD 증거

- 이전 구현에서 새 실제 request-context/HMAC 관리자 경계 테스트가 exit 1, `12 failed, 12 passed`였다. 전체 원문은 `impl-red.log.gz`에 보관했다. 비JSON과 빈 본문·문법 오류·falsy 비객체는 기대 `415`/`400` 대신 `200`이었고, truthy scalar 문자열·숫자·`true`는 `.get` 호출로 `500`이 되어 `400` 기대를 어겼다.
- falsy `""`·`0`·`false`와 truthy `[1]`·`1`·`true`·`"text"`를 추가한 확장 RED는 `impl-red-expanded.log.gz`에 보관했다. 결과는 exit 1, `17 failed, 12 passed`이며 입력별 실제 200/500 결과를 원문으로 남긴다.
- 최초 multipart 대역의 `FileNotFoundError`는 요청 경계와 무관한 파일 입력 구성 오류여서 `impl-red-harness.md`에 분리했다. `io.BytesIO`로 고친 뒤의 RED 원문에는 그 오류가 없다.

## 검증

- `gtimeout -k 10s 180s env -u OMX_ROOT -u OMX_STATE_ROOT SCHEDULER_ENABLED=false PYTHONDONTWRITEBYTECODE=1 sandbox-exec -p '(version 1)(allow default)(deny network-outbound)' /Users/freelife/vibe/lecture/hodu/closing-bet-demo/venv/bin/python -m pytest tests/app/test_jongga_message_request_boundary.py tests/app/test_kr_market_jongga_execution_routes_refactor.py tests/app/test_admin_gated_routes.py -q` → exit 0, `62 passed in 1.15s`.
- 같은 sandbox에서 변경 Python 파일 AST parse → `AST parse passed`.
- `git diff --check` → exit 0.
- Ruff는 가상환경에 설치되어 있지 않아 `No module named ruff`로 실행할 수 없었다. LSP는 별도 `lsp-unavailable.json` 증거처럼 현재 Transport closed 상태다.

## 테스트 범위

새 테스트는 실제 `_register_request_context`와 `require_admin`, HMAC admin/user 신원, tmp_path 실제 중복 guard, 외부 발송만 가짜 Messenger로 조립한다. `construct`는 결과 빌더가 아니라 Fake Messenger 생성 횟수를 측정한다. resolver가 받은 `target_date`도 기록해 `{}`·날짜·null이 실제 파싱 결과 그대로 전달되는지 확인한다. form·multipart·text/plain·MIME 없음, 빈/문법 오류/큰 Unicode 오류/falsy·truthy 비객체 JSON, vendor JSON/charset/`{}`/날짜/null/force, 익명·일반 사용자 선행 403, OPTIONS, 중복·force·발송 오류 후 재시도를 측정한다.
