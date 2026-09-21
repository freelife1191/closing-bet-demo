# INFRA-074 적대적 수명주기 테스트

## 범위

- `ss`가 보고하는 복수 리스너 PID와 PID 비공개 상태
- 동시 start/stop 잠금과 비정상 종료 뒤 커널 잠금 회수
- 외부 프로세스의 HTTP 200 오인 방지와 준비 전 자식 종료
- supervisor 재기동 PID 및 TERM 대기 중 PID 재사용에 대한 강제 종료 거부
- 기록 master 계보 밖의 같은 프로젝트 리스너 거부
- 포트가 먼저 비거나 종료 직후 재점유되는 경합에서 성공·PID 삭제 거부
- 동기화 직후 포트 재점유 시 백엔드 시작 거부
- 다른 Next 관련 명령의 프론트엔드 프로세스 오인 방지
- PID 기록 쓰기 실패와 완료된 shell job의 PID 재사용에서 잘못된 TERM 방지
- 프론트엔드 준비 중 백엔드 종료 시 최종 Ready 거부
- 백엔드 성공 뒤 프론트엔드 실패 시 외부 리스너와 무관하게 자체 자식·PID 기록 정리

테스트는 임시 프로젝트, 가짜 `ss`/`lsof`, 셸 함수 대역, 자체 임시 자식만 사용했다. 원본
3500/5501 포트, 실행 서비스, `.env`, `data/`, `venv`, `node_modules`에는 쓰지 않았다.

## RED

초기 실행:

```text
venv/bin/python -m pytest -q tests/scripts/test_lifecycle_adversarial.py
...F...F
2 failed, 6 passed in 4.52s
```

- 실제 결함: 잠금 소유 셸이 release 없이 종료되면 다음 `lifecycle_acquire_lock`이 실패했다.
  기존 PID 디렉터리 방식이 stale 잠금을 자동 회수하지 못했다.
- 테스트 하네스 결함: 부분 시작 정리 테스트의 임시 자식 trap 문자열이 종료 표식을 남기지
  못했다. 제품 코드 기대값을 낮추지 않고 테스트 자식 스크립트만 고쳤다.

## GREEN

최종 적대적 파일:

```text
env -i PATH="$PATH" HOME=/tmp PYTHONDONTWRITEBYTECODE=1 \
  PYTHON_DOTENV_DISABLED=1 venv/bin/python -m pytest -q \
  -p no:cacheprovider tests/scripts/test_lifecycle_adversarial.py
.................                                                        [100%]
17 passed in 3.86s
```

관련 회귀 묶음:

```text
env -i PATH="$PATH" HOME=/tmp PYTHONDONTWRITEBYTECODE=1 \
  PYTHON_DOTENV_DISABLED=1 venv/bin/python -m pytest -q \
  -p no:cacheprovider \
  tests/scripts/test_lifecycle_adversarial.py \
  tests/scripts/test_service_lifecycle.py \
  tests/scripts/test_sync_dependencies.py \
  tests/scripts/test_next_environment.py
........................................................................ [ 94%]
....                                                                     [100%]
76 passed in 18.59s
```

## 폐기한 전체 pytest 실행

원본 venv와 상속 환경으로 전체 pytest를 실행한 것은 이 테스트 하위 작업의 격리 범위를
벗어났으므로 검증 증거로 사용하지 않는다. 실행은 종료됐고 자식 프로세스는 남지 않았다.
관찰된 다섯 실패는 이 테스트 파일이 만든 상태나 자식 프로세스와 무관했다.

- pykrx 로그인 비정상 JSON 처리 패치가 원본 venv에 아직 설치되지 않은 상태에서 발생한
  4건: VCP fixture 2건, login guard 1건, DataSourceManager 초기화 1건
- 신규 `scripts/service_lifecycle.sh`를 복사하지 않은 Next bootstrap fixture 1건

이 실행은 원본 `.env`를 읽어 KRX 로그인을 시도했으므로 출력 원문은 증거에 보존하지 않았다.
자격 증명 값도 기록하지 않았다. 전체 판정에는 상위 작업이 수행한 fresh 격리 설치와
`PYTHON_DOTENV_DISABLED=1` 실행만 사용한다.
