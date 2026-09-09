# INFRA-029 구현 증거

## 원인

`run_daily_closing_analysis`는 네 단계의 결과를 합산하지 않고, 종가베팅 실행 직후
`장 마감 정기 분석 및 종가베팅 완료`를 기록했다. 앞의 일별 주가·기관/외인 수급·VCP가
`False`이거나 종가베팅이 falsey여도 이 완료 로그가 남았다.

## 변경

- 네 단계 결과를 `failed_steps`로 모은 뒤, 알림 처리가 끝난 다음 부분 실패 또는 전체 완료를
  기록한다.
- 앞 세 단계는 기존과 같이 `is False`일 때만 실패로 취급한다. 따라서 `None`은 호환된다.
- 종가베팅은 기존 truthiness를 유지해 `False`와 `None`을 실패로 취급한다.
- 종가베팅이 truthy이면 앞 단계 실패와 관계없이 기존 순서대로 알림을 호출한다.
- chaining 문구는 `데이터 수집·VCP 단계 처리 후`로, 알림 뒤 로그는
  `종가베팅 알림 처리 종료`로 바꿨다. 이 로그는 downstream 전달 성공을 뜻하지 않는다.

## 불변 계약

- 단계 순서: 일별 주가 → 기관/외인 수급 → VCP → 종가베팅 → (종가 성공 시) 알림.
- 각 단계의 개별 실패 감지 및 종가 실패 시 알림 건너뛰기.
- 수집 또는 알림 예외는 기존 outer `except`로 기록되고, `finally`가 세 scheduler 실행 상태를
  모두 해제한다.
- `run_jongga_v2_analysis`의 단독 실행 로그는 변경하지 않았다.

## RED / GREEN

- RED: `venv/bin/python ../run_check.py red-scheduler . venv/bin/python -m pytest tests/services/test_scheduler_jobs_refactor.py -q`
  → 종료 코드 1, 새 실패/복합/None 사례 6건 실패. 기존의 무조건 완료 로그와 부분 실패 집계 부재가 원인.
  상세: `red-scheduler.log`, `red-scheduler.json`.
- GREEN: `venv/bin/python ../run_check.py green-scheduler . venv/bin/python -m pytest tests/services/test_scheduler_jobs_refactor.py -q`
  → 종료 코드 0, `16 passed in 4.16s`.
  상세: `green-scheduler.log`, `green-scheduler.json`.
- 예외 RED 보강: `venv/bin/python ../run_check.py red-exception-scheduler . venv/bin/python -m pytest tests/services/test_scheduler_jobs_refactor.py -q -k does_not_log_completion_after_exception`
  → 이전 무조건 완료 로그를 임시로 복원한 격리 대역에서 종료 코드 1. 알림 예외 직전에
  완료 로그가 남는 것을 포착했다. 상세: `red-exception-scheduler.log`,
  `red-exception-scheduler.json`.

## 리뷰

- `git diff --check` → 종료 코드 0.
- 합성 경계 대역으로 각 단계 False, 복합 실패, 앞 세 단계 None, 종가 False/None, 수집 예외,
  알림 예외와 finally 상태 해제를 검증했다. 성공과 부분 실패 로그 모두 알림 처리 뒤에
  남는 순서도 검사했다.
- 실제 수집·LLM·알림·서버 HTTP는 실행하지 않았다.
