**APPROVE**

- `../infra062_transport_support.py:442-450`은 exact owned PGID만 `pgrep -g`로 조회하고 반환 코드 0/1 외에는 실패합니다.
- `../message_transport.py:324-339`은 `detached-flush*.js dev <escaped clone/frontend>`를 함께 고정해 관련 PID만 관측합니다.
- sandbox 증거가 dead/live 그룹 강제 종료, matching dummy 탐지, 무관 프로세스 제외, 종료 후 PID·이벤트 파일 부재를 확인합니다.
- 최신 하네스 해시는 manifest·gzip과 일치하며 제품 source/test 해시는 불변입니다.

QA 1회차의 HTTP 0건·서버 시작 전 실패 기록도 정확합니다. QA 2회차 결과는 별도 완료 조건입니다.
