# AUDIT-INFRA — 인프라·패키지 감사

**감사 범위**: `requirements.txt`, `requirements.updated.txt`, `frontend/package.json`,
`services/scheduler.py`, `services/scheduler_jobs.py`, `services/scheduler_loop.py`,
`services/scheduler_runtime_status_service.py`, `scripts/init_data.py`
**읽은 파일 수**: 8개 / 총 3,407줄
**대조용으로 함께 읽은 파일**: `numpy_json_encoder.py`, `.env.example`,
`frontend/package-lock.json`, `tests/services/test_scheduler*.py`,
`tests/scripts/test_init_data_vcp_scheduler.py`
**감사일**: 2026-09-01

## 0. 시크릿 노출 점검

`git ls-files` 로 확인한 결과 저장소가 추적하는 `.env` 계열 파일은 `.env.example` 하나뿐이며,
`git log --all --diff-filter=A` 로 과거 커밋을 훑어도 추가된 적이 있는 `.env` 계열 파일은
역시 `.env.example` 하나였습니다. `secrets/` 아래에 추적되는 파일은 없고, 자격 증명으로
의심할 만한 `*.pem`, `*.key`, `token` 계열 파일도 추적되지 않습니다.
`.gitignore` 는 19~21번 줄에서 `.env` 와 `.env.*` 를 덮고 `!.env.example` 만 예외로 두고
있으며, 이 규칙이 실제로 지켜지고 있습니다.

작업 중 생성되는 `services/scheduler.lock` 역시 `.gitignore:58` 의 `services/*.lock` 이
덮고 있어 추적되지 않습니다.

**결론: 시크릿 노출은 발견되지 않았습니다.** 이 관점에서 나온 개선 항목은 없습니다.

## 1. 깨진 동작

### 1.1 `JONGGA_SCHEDULE_TIME` 이 어디에서도 읽히지 않아 15:20 단독 종가베팅이 실행되지 않는다

- 위치: `services/scheduler.py:166-199` (`_bootstrap_scheduler_after_lock_acquired`),
  `services/scheduler.py:30` (사용되지 않는 import)
- 증상: 문서가 약속한 "매일 15:20 AI 종가베팅 단독 실행" 이 실제로는 한 번도 일어나지
  않습니다. 종가베팅 결과는 `CLOSING_SCHEDULE_TIME` 인 17:00 체인 안에서만 생성됩니다.
- 원인: `_bootstrap_scheduler_after_lock_acquired` 가 등록하는 잡은
  `market_gate` 태그(`services/scheduler.py:173`)와 `closing_analysis`
  태그(`services/scheduler.py:181-186`) 두 개뿐입니다. `run_jongga_v2_analysis` 는
  `services/scheduler.py:30` 에서 import 되지만 `schedule.every()` 에 한 번도 걸리지
  않습니다. 저장소 전체에서 `JONGGA_SCHEDULE_TIME` 을 읽는 파이썬 코드를 찾으면
  결과가 없고, 이 변수는 `.env.example:123` 과 `README.md` 의 105, 399, 1434, 1465,
  2049번 줄에만 존재합니다. 대조 대상인 `CLOSING_SCHEDULE_TIME` 은
  `services/scheduler.py:180` 에서 정상적으로 읽힙니다.
- 영향: 운영자가 `.env` 에 `JONGGA_SCHEDULE_TIME` 을 설정해도 아무 효과가 없습니다.
  15:20 에 종가베팅 신호를 기대하는 사용자는 두 시간 가까이 빈 화면을 보게 되며,
  설정값이 무시되고 있다는 사실을 알려 주는 로그도 없습니다.
- 우선순위: **P0**

### 1.2 `scripts/init_data.py` 가 두 이름으로 이중 로드되어 모듈 전역 상태가 갈라진다

- 위치: `services/scheduler_jobs.py:32-36` 대 `engine/screener.py:150`,
  `services/kr_market_flow_service.py:118`, `services/common_update_service.py:53`,
  `services/kr_market_vcp_background_service.py:51`
- 증상: 같은 파일이 `init_data` 와 `scripts.init_data` 라는 서로 다른 두 모듈로
  메모리에 올라갑니다. 실측으로 확인했습니다.

  ```
  두 모듈 객체 동일한가: False
  sys.modules 키: ['init_data', 'scripts.init_data']
  루트 로거 필터 수 before/mid/after: 0 1 2
  한쪽 캐시 설정 후 다른 쪽 캐시: None
  ```

- 원인: `services/scheduler_jobs.py:32-36` 은 `scripts` 디렉터리 자체를 `sys.path` 에
  넣은 뒤 `importlib.import_module("init_data")` 로 최상위 모듈로 불러옵니다. 반면
  다른 다섯 곳은 `from scripts import init_data` 형태로 패키지 경로를 통해 불러옵니다.
  `scripts/__init__.py` 가 존재하지 않아 네임스페이스 패키지로 동작하는 탓에 두 방식이
  모두 성공하고, 파이썬은 이를 별개의 모듈로 취급합니다.
- 영향: 세 가지입니다. 첫째, `scripts/init_data.py:32` 의
  `logging.getLogger().addFilter(PykrxFilter())` 와 `scripts/init_data.py:37` 의
  `socket.setdefaulttimeout(30)` 같은 모듈 수준 부작용이 두 번 적용되어 루트 로거에
  같은 필터가 중복으로 쌓입니다. 둘째, `scripts/init_data.py:512-534` 의
  `_market_indices_cache` 와 `_sector_indices_cache` 가 두 벌 존재하므로, 한쪽에서
  갱신한 지수 데이터가 다른 쪽 호출자에게 보이지 않습니다. 셋째,
  `tests/app/test_common_update_service.py` 가 `fake_scripts.init_data` 로 주입하는
  대역이 `scheduler_jobs` 경로에는 적용되지 않아, 스케줄러 경로만 검증에서 빠집니다.
- 우선순위: **P1**

## 2. 중복

### 2.1 `NumpyEncoder` 사본이 공용 구현과 갈라져 datetime 직렬화가 빠져 있다

- 위치: `scripts/init_data.py:55-65` 대 `numpy_json_encoder.py:17-46`
- 증상: 같은 이름의 JSON 인코더가 두 벌 존재하며 동작이 다릅니다. 공용 구현은
  `numpy_json_encoder.py:44-45` 에서 `datetime` 과 `date` 를 `isoformat()` 으로
  변환하지만, `scripts/init_data.py` 의 사본에는 그 분기가 없어 `super().default(obj)`
  로 떨어지면서 `TypeError` 를 던집니다.
- 원인: 저장소의 다른 여덟 개 모듈(`engine/utils.py:7`,
  `engine/generator_result_storage.py:15`, `engine/market_gate.py:39`,
  `services/kr_market_data_cache_jongga.py:19`,
  `services/common_update_status_service.py:18`,
  `services/kr_market_backtest_summary_cache.py:24` 등)은 모두 공용 모듈을 import 하는데,
  `scripts/init_data.py` 만 자기 사본을 정의해 두고 730, 1785, 1790, 1978, 2680번 줄
  다섯 곳에서 그 사본을 `cls=` 인자로 넘깁니다.
- 영향: `create_jongga_v2_latest`(`scripts/init_data.py:1945`)나
  `update_kr_ai_analysis_prices`(`scripts/init_data.py:2655`)가 만드는 payload 안에
  pandas `Timestamp` 나 `datetime` 이 한 개라도 남아 있으면 파일 저장이 예외로 끝납니다.
  같은 payload 를 공용 인코더로 저장하는 다른 경로는 정상 동작하므로, 저장 경로에 따라
  결과가 달라지는 형태로 증상이 나타납니다. 두 구현 중 한쪽만 고쳐질 위험도 그대로
  남아 있습니다.
- 우선순위: **P1**

## 3. 과잉 설계

### 3.1 `assign_grade` 는 테스트만을 위해 존재하는 등급 판정 사본이다

- 위치: `scripts/init_data.py:91-145` (55줄)
- 증상: 프로덕션 코드에서 이 함수를 호출하는 곳이 한 군데도 없습니다. 유일한 호출자는
  `tests/test_grading_logic.py` 이며, 그 파일이 이 함수의 S/A/B/C/D 다섯 등급 분기를
  전부 검사합니다.
- 원인: 함수의 독스트링이 스스로 밝히고 있습니다. "Jongga 등급 산정 하위호환 함수.
  tests/test_grading_logic.py의 기존 계약을 유지한다." 실제 등급 판정은
  `engine/grade_classifier.py` 와 `engine/grade_decider.py` 가 담당하며, 이 함수의
  임계값(`scripts/init_data.py:110-142` 의 `1_000_000_000_000`, `500_000_000_000` 등)은
  `engine/constants.py` 의 `TRADING_VALUES` 를 참조하지 않고 직접 적혀 있습니다.
- 영향: 실제 등급 로직이 바뀌어도 이 테스트는 계속 통과합니다. 등급 판정에 테스트가
  다섯 건 붙어 있다는 겉모습이 실제로는 아무것도 지켜 주지 않아, 검증 공백을 가리는
  거짓 안전감을 만듭니다.
- 우선순위: **P2**

### 3.2 호출자가 없는 진입점 두 개가 남아 있다

- 위치: `scripts/init_data.py:1993-2096` (`create_market_gate`, 104줄),
  `scripts/init_data.py:529-534` (`reset_cache`)
- 증상: 두 함수 모두 저장소 전체에서 호출하는 곳이 없습니다. 테스트도 없습니다.
- 원인: Market Gate 의 실제 생성과 저장은 `engine/market_gate.MarketGate` 를 거치는
  경로로 옮겨 갔습니다. `app/routes/kr_market.py:251-252`,
  `engine/screener.py:209`, `engine/generator_runtime_helpers.py:35-36`,
  `services/common_update_pipeline_steps.py:200`,
  `services/kr_market_flow_service.py:131` 이 모두 그쪽을 씁니다.
  `services/scheduler_jobs.py:47-53` 의 `_run_market_gate_analysis` 도 마찬가지입니다.
  `reset_cache` 는 짝이 되는 `get_market_indices` 와 `get_sector_indices` 가
  `scripts/init_data.py` 내부에서만 쓰이는데, 캐시를 비울 필요가 있는 호출자가
  끝내 나타나지 않은 채로 남았습니다.
- 영향: 읽는 사람이 Market Gate 생성 경로가 둘이라고 오해하게 만들며, §1.2 의
  이중 로드 문제와 겹치면 어느 쪽 캐시를 비우는 함수인지도 불분명해집니다.
- 우선순위: **P2**

## 4. 비대한 파일

### 4.1 `scripts/init_data.py` 한 파일이 열세 가지 책임을 지고 있다

- 위치: `scripts/init_data.py` (2,712줄, 최상위 정의 33개)
- 증상: 한 파일 안에 다음 책임이 모두 들어 있습니다. 로깅 필터(`24-32`),
  JSON 인코더(`55-65`), 등급 판정(`91-145`), 거래일 계산(`147-208`),
  지수 수집과 캐시(`213-535`), 터미널 색상 출력(`539-582`),
  개별 종목 시세 수집(`377-514`, `849-1121`), 수급 수집과 Toss 백필(`592-715`, `1355`),
  VCP 시그널 생성(`716-731`, `1587`, `2572`), 종가베팅 생성(`1945`),
  Market Gate 생성(`1993`), AI 분석(`2097`, `2268`, `2655`),
  알림 발송(`2364`), CLI 진입점(`2537`, `2686`).
- 원인: 신규 수집 대상이 늘어날 때마다 같은 파일에 함수를 덧붙여 왔습니다.
- 영향: `services/scheduler_jobs.py:37-43` 이 실제로 필요로 하는 함수는 다섯 개인데,
  스케줄러 잡 하나를 실행하려면 2,712줄 모듈 전체가 로드되고 §1.2 에서 확인한
  모듈 수준 부작용까지 함께 실행됩니다. 한 책임을 고치려는 사람이 나머지 열두 개를
  함께 읽어야 하며, 실제로 `scripts/debug_details.py:13` 은 이미 존재하지 않는
  `calculate_advanced_score` 와 `get_themes_by_sector` 를 import 하고 있어 이 파일의
  공개 계약이 관리되지 않고 있음을 보여 줍니다.
- 우선순위: **P2**

## 5. 검증 공백

### 5.1 잡이 실제로 등록되는지 확인하는 테스트가 없다

- 위치: `tests/services/test_scheduler_refactor.py` (226줄),
  검증 대상 `services/scheduler.py:166-199`
- 증상: 스케줄러 테스트 다섯 파일 554줄은 잠금 획득, 잠금 경쟁 재시도, 타임존 적용,
  틱 예외 복구, 비활성화 시 조기 반환을 검증합니다. 그러나
  `_bootstrap_scheduler_after_lock_acquired` 가 어떤 잡을 어떤 태그로 어떤 시각에
  등록하는지 확인하는 테스트는 한 건도 없습니다.
- 원인: 테스트가 `start_scheduler` 의 방어 로직에만 초점을 맞추었고, 등록 결과 자체는
  대상으로 삼지 않았습니다.
- 영향: 이 공백 때문에 §1.1 의 종가베팅 잡 등록 누락이 잡히지 않았습니다. 앞으로
  잡을 추가하거나 태그를 바꿀 때도 같은 종류의 누락이 그대로 통과합니다.
- 우선순위: **P1**

### 5.2 `init_data` 의 생성 함수 가운데 절반이 실제 구현 기준으로 검증되지 않는다

- 위치: `tests/scripts/test_init_data_vcp_scheduler.py` (783줄, 테스트 16건)
- 증상: 이 파일이 다루는 대상은 `create_signals_log`, `send_jongga_notification`,
  `create_daily_prices`, `fetch_prices_yfinance`, `create_institutional_trend` 다섯
  갈래입니다. 반면 `create_jongga_v2_latest`(`scripts/init_data.py:1945-1992`),
  `create_kr_ai_analysis`(`2097`), `create_kr_ai_analysis_with_key`(`2268`),
  `update_kr_ai_analysis_prices`(`2655`), `create_korean_stocks_list`(`732`) 에는
  구현을 실행하는 테스트가 없습니다.
- 원인: `create_jongga_v2_latest` 는 다른 테스트에도 이름이 등장하지만
  (`tests/services/test_scheduler_jobs_refactor.py`), 그곳에서는 모두 monkeypatch 로
  대체되는 대역일 뿐 실제 구현이 실행되지 않습니다.
- 영향: 종가베팅 결과 파일을 만드는 경로가 §2.1 의 인코더 문제로 깨지더라도
  테스트는 통과합니다.
- 우선순위: **P2**

## 요약

| 관점 | 발견 | 그중 P0 | P1 | P2 |
|---|---|---|---|---|
| 깨진 동작 | 2 | 1 | 1 | 0 |
| 중복 | 1 | 0 | 1 | 0 |
| 과잉 설계 | 2 | 0 | 0 | 2 |
| 비대한 파일 | 1 | 0 | 0 | 1 |
| 검증 공백 | 2 | 0 | 1 | 1 |
| **합계** | **8** | **1** | **3** | **4** |

### 기존 백로그와의 관계

- 파이썬 의존성의 버전 고정 문제와 `requirements.updated.txt` 의 처리는 `[INFRA-001]`
  이 이미 담당하므로 이 감사에서는 항목으로 만들지 않았습니다. 다만 그 작업의 근거를
  한 가지 보탭니다. `requirements.txt` 는 `numpy` 를 아예 나열하지 않는데
  `scripts/init_data.py:13` 이 직접 import 하며, 공용 인코더
  `numpy_json_encoder.py:38` 은 numpy 2.x 에서 제거된 `np.float_` 을 참조합니다.
  현재 설치본은 numpy 1.26.4 라 동작하지만, `[INFRA-001]` 에서 `google-genai` 를
  2.x 로 올릴 때 전이 의존성으로 numpy 가 함께 올라가면 이 지점이 먼저 깨집니다.
- `frontend/package.json` 의 의존성은 모두 캐럿 범위이지만
  `frontend/package-lock.json` 이 `next@16.1.6`, `react@19.2.4`,
  `eslint-config-next@16.1.6`, `vitest@2.1.9` 로 실제 버전을 고정하고 있어 파이썬 쪽과
  같은 문제로 보지 않았습니다.
- `frontend/package.json:13,15` 의 `test:baseline` 과 `upgrade:check` 스크립트가
  현재 실패하는 베이스라인 테스트를 게이트로 삼고 있는 문제는 `[FE-001]` 의 범위입니다.

### 담당 경로 밖에서 눈에 띈 사실

- `scripts/debug_details.py:13` 이 `scripts/init_data.py` 에 존재하지 않는
  `calculate_advanced_score` 와 `get_themes_by_sector` 를 import 하고 있어 실행하면
  즉시 `ImportError` 가 납니다.

---

# 2부: TODO 항목 초안

### [INFRA-005] 종가베팅 단독 스케줄 등록 복구
- 카테고리: 인프라 | 티어: T3 | 근거: AUDIT-INFRA §1.1, §5.1
- 우선순위: P0
- `services/scheduler.py` 가 `tier-rules.md` §2 의 "스케줄러와 데이터 적재" 위험 경로에
  해당하므로 줄 수와 무관하게 T3 입니다.
- [ ] `_bootstrap_scheduler_after_lock_acquired` 에 `JONGGA_SCHEDULE_TIME` 기반
      `run_jongga_v2_analysis` 잡을 `jongga` 태그로 등록
- [ ] 재등록 시 중복이 쌓이지 않도록 `schedule.clear("jongga")` 를 함께 배치
- [ ] 세 잡의 태그와 등록 시각을 확인하는 테스트를 `tests/services/test_scheduler_refactor.py`
      에 추가
- [ ] 17:00 체인과 15:20 단독 실행이 같은 날 겹칠 때 알림이 두 번 나가지 않는지 확인
- [ ] pytest 전체 통과 확인

### [INFRA-006] init_data 임포트 경로를 하나로 통일
- 카테고리: 인프라 | 티어: T3 | 근거: AUDIT-INFRA §1.2
- 우선순위: P1
- `scripts/init_data.py` 와 `services/scheduler_jobs.py` 가 모두 위험 경로에 있어 T3 입니다.
- [ ] `scripts/__init__.py` 를 추가할지, `sys.path` 주입을 걷어낼지 방식을 확정
- [ ] `services/scheduler_jobs.py:32-36` 의 `importlib` 지연 로드를
      `from scripts import init_data` 방식으로 통일
- [ ] `services/kr_market_route_service.py:142` 와 `tests/test_grading_logic.py:9` 의
      최상위 임포트를 같은 방식으로 정리
- [ ] `sys.modules` 에 `init_data` 와 `scripts.init_data` 가 동시에 올라가지 않음을
      확인하는 테스트 추가
- [ ] pytest 전체 통과 확인

### [INFRA-007] init_data 의 NumpyEncoder 사본을 공용 인코더로 교체
- 카테고리: 인프라 | 티어: T3 | 근거: AUDIT-INFRA §2.1
- 우선순위: P1
- `scripts/init_data.py` 가 위험 경로에 있어 T3 입니다.
- [ ] `scripts/init_data.py:55-65` 의 사본을 삭제하고 `numpy_json_encoder` 를 import
- [ ] `cls=NumpyEncoder` 를 넘기는 다섯 곳(730, 1785, 1790, 1978, 2680)이 공용 구현을
      쓰는지 확인
- [ ] `datetime` 이 섞인 payload 가 정상 저장되는지 확인하는 테스트 추가
- [ ] pytest 전체 통과 확인

### [INFRA-008] init_data 의 죽은 진입점 정리
- 카테고리: 인프라 | 티어: T3 | 근거: AUDIT-INFRA §3.1, §3.2
- 우선순위: P2
- `scripts/init_data.py` 가 위험 경로에 있어 T3 입니다.
- [ ] `create_market_gate`(1993-2096)를 삭제하고 Market Gate 생성 경로가
      `engine/market_gate.MarketGate` 하나임을 확인
- [ ] `reset_cache`(529-534)의 존치 여부를 판단하고 불필요하면 삭제
- [ ] `assign_grade`(91-145)를 실제 등급 판정 경로에 연결하거나,
      `tests/test_grading_logic.py` 와 함께 폐기
- [ ] pytest 전체 통과 확인

### [INFRA-009] init_data 를 책임 단위로 분리
- 카테고리: 인프라 | 티어: T3 | 근거: AUDIT-INFRA §4.1, §5.2
- 우선순위: P2
- 선행 조건: `[INFRA-008]` 로 죽은 코드를 걷어낸 뒤 남은 규모로 분리 범위를 다시
  잡습니다. `scripts/init_data.py` 가 위험 경로에 있어 T3 입니다.
- [ ] 열세 가지 책임을 묶어 분리 단위를 확정 (수집 / 생성 / 알림 / CLI 를 후보로 검토)
- [ ] 한 번에 300줄을 넘기지 않도록 여러 사이클로 나누어 진행할 순서를 결정
- [ ] `scripts/debug_details.py:13` 의 깨진 import 를 정리 대상에 포함
- [ ] 분리 대상 함수 가운데 테스트가 없는 `create_jongga_v2_latest` 등에 회귀 테스트 추가
- [ ] 이동한 파일 경로를 `tier-rules.md` §2 위험 경로 목록에 반영
