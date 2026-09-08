# INFRA-063 구현 RED 증거

- 시각: 2026-09-08 KST
- 명령: `env -u OMX_ROOT -u OMX_STATE_ROOT SCHEDULER_ENABLED=false PYTHONDONTWRITEBYTECODE=1 sandbox-exec -p '(version 1)(allow default)(deny network-outbound)' /Users/freelife/vibe/lecture/hodu/closing-bet-demo/venv/bin/python -m pytest tests/app/test_jongga_message_request_boundary.py -q`
- 결과: exit 1, 12 failed, 12 passed.
- 관측: 인증된 form/text/plain/MIME 없음 요청은 415 대신 200으로 메시지 발송 경로에 진입했다. 빈 본문·문법 오류·`null`·빈 배열은 400 대신 200이었다. truthy scalar인 문자열·숫자·`true`는 `.get` 호출에서 500이 되어 400 기대를 어겼다. 기존 `request.get_json(silent=True) or {}`가 비JSON·파싱 오류·falsy 비객체를 빈 객체로 흡수하고, truthy 비객체를 그대로 넘긴 것이 원인이다.
- 확장 행렬: `impl-red-expanded.log.gz`는 falsy `""`·`0`·`false`와 truthy `[1]`·`1`·`true`·`"text"`를 더한 동일 이전 구현의 실행 원문이다. exit 1, 17 failed, 12 passed이며 각 입력의 실제 200/500 결과를 보존한다.
