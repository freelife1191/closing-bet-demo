## 코드 리뷰 결과

**REQUEST CHANGES**

[HIGH/P1] (확신도 10/10) `../infra062_transport_support.py:265-294` — Next dev 실행 환경이 `os.environ.copy()`를 그대로 상속하며 텔레메트리를 끄지 않습니다. 설치된 Next는 `frontend/node_modules/next/dist/telemetry/post-telemetry-payload.js:21`에서 외부 POST를 수행하고, 종료 시 `next-dev.js:118-136`에서 detached flush를 생성합니다. `infra062_transport_support.py:449-479`의 PGID 정리는 이 분리된 프로세스를 관측하지 못합니다.

수정: `NEXT_TELEMETRY_DISABLED=1`, `NEXT_TRACE_UPLOAD_DISABLED=1`을 강제하고 debug 변수를 제거하십시오. 일회용 Next PGID는 종료 핸들러가 실행되지 않도록 정리하며, loopback 전용 네트워크 정책과 detached process·`.next/_events_*` 부재를 종료 조건으로 확인해야 합니다.

제품 변경은 승인 요구를 충족합니다. `app/routes/kr_market_jongga_execution_routes.py:204-221`은 인증 후 비JSON 415, malformed·비객체 JSON 400을 발송 부수효과 전에 처리합니다. 정상 `{}`·날짜·null·force·중복·claim 재시도도 유지됩니다. 새 테스트와 16개 입력 해시가 현재 파일과 일치하며, 추가 코드 차단점은 없습니다.

Python LSP는 실제 진단이 아니라 `tsc skipped`로 끝났습니다. 제공된 pytest·AST 증거를 확인했으며 이번 리뷰에서는 테스트·HTTP·외부 조회·텔레메트리·파일 변경을 실행하지 않았습니다. 실제 HTTP QA는 하네스 수정 후 진행해야 합니다.
