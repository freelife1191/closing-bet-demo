# INFRA-063 RED 대역 보정 기록

최초 RED 실행에서 multipart 입력을 파일명 문자열로 넘겨 Werkzeug가 `body.txt`를 열려 했고, 라우트에 도달하기 전에 `FileNotFoundError`가 났다. 이는 요청 경계의 실패가 아니라 테스트 대역 구성 오류다.

대역을 `io.BytesIO(b"{}")` 파일 객체로 고친 뒤, 이전 메시지 라우트 상태에서 같은 경계 테스트를 다시 실행했다. 그 실제 표준 출력은 `impl-red.log.gz`에 보존했다. 결과는 exit 1, `12 failed, 12 passed`이며, 모든 실패는 기대한 415/400 대신 실제 200이 나온 요청 경계 회귀다.
