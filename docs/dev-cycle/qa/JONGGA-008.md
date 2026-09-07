# [JONGGA-008] 백엔드가 확신도 없음을 0 으로 표현하는 자리를 정리 — QA 시나리오

- 대상 화면: http://localhost:3500/dashboard/kr/vcp, http://localhost:3500/dashboard/kr/closing-bet
- 백엔드: http://localhost:5501
- 구성 근거: 이번 사이클의 변경 열두 파일 + `/qa-only` 리포트
- 구성 2026-09-07 12:30 | 실행 2026-09-07 12:26~12:42
- QA 엔진(engine): Claude Code `/qa-only` → `/qa`
- 단계(phase): 시나리오 구성 완료 | 실행 완료
- 반복(iteration): 1회
- baseline 상태: 기준값 수집 완료 (`3aa0ef7` 코드를 같은 자료로 띄워 대조)
- 필수 여부(required): 예
- 결과: 통과 (필수 8/8, 선택 1/1)
- 증거: `.gstack/qa-reports/screenshots/jongga008-*.png` 네 장, 아래 실행 결과 표
- 정리(cleanup): worktree 제거, QA 백엔드 종료, 원본 `data/` 무변경 확인

## 검사 자료에 관한 전제

`data/` 는 읽기 전용이고, 오늘 자 분석 파일을 새로 만드는 화면 수단(「Refresh VCP」·「실패
AI 재분석」·「재분석」)은 되돌릴 수 없는 조작이라 실행할 수 없습니다. 그래서 원본 `data/`
전체를 심볼릭 링크로 건 사본 디렉터리를 scratchpad 에 만들고, 검사에 필요한 두 파일만
실제 사본으로 바꾸어 그 디렉터리를 작업 디렉터리로 삼아 백엔드를 띄웁니다.

작업 디렉터리를 바꾸는 이유는 `app/routes/kr_market.py:98` 이 `DATA_DIR = 'data'` 라는 상대
경로를 하드코딩하기 때문입니다. `engine/config.py:57` 이 읽는 `DATA_DIR` 환경변수는 이 경로에
닿지 않습니다. 코드는 저장소 것을 그대로 쓰도록 `app`·`engine`·`services` 등을 링크로 겁니다.

| 파일 | 바꾼 내용 | 이유 |
|---|---|---|
| `signals_log.csv` | `is_vcp` 를 `True` 로 채우고 세 행의 AI 열을 갈래별로 채움 | 원본은 이 열이 비어 있어 시그널이 0 건입니다 |
| `jongga_v2_latest.json` | 첫 종목은 사유 문자열만 남기고, 둘째 종목은 `ai_action` 만 남김 | 원본은 아홉 종목 모두 확신도가 채워져 있어 값 없음이 재현되지 않습니다 |

`signals_log.csv` 사본의 세 행이 각각 다른 갈래를 담습니다. 종목은
`ai_analysis_results_20260505.json` 이 담지 않은 것으로 골랐습니다. 그 파일에 있는 네 종목
(현대로템·SK·SK하이닉스·삼성전자)은 `_merge_ai_data_into_vcp_signals` 가 그 파일의 판정으로
CSV 판정을 덮어써서 CSV 갈래를 검사할 수 없습니다.

| 종목 | `ai_action` | `ai_reason` | `ai_confidence` | 무엇을 재현하는가 |
|---|---|---|---|---|
| `003550` LG | `BUY` | 있음 | 빔 | 추천은 있고 확신도만 없다 (핵심) |
| `403870` HPSP | 빔 | 빔 | 빔 | 추천 자체가 없다 |
| `005380` 현대차 | `HOLD` | 있음 | `78` | 값이 있으면 그대로여야 한다 |

쓰기가 일어나는 SQLite 캐시는 링크를 지워 사본 디렉터리에 새로 만들어지게 합니다.
`git status data/` 가 비어 있음을 검사 전후로 확인합니다.

## 시나리오

각 시나리오의 「고치기 전」 값은 `git worktree` 로 `3aa0ef7` 을 체크아웃하고 **같은 자료
사본**을 그 코드에 물려 실측했습니다. 갈래를 전환할 때마다 사본의 `data/runtime_cache.db`
를 지웠습니다. 지우지 않으면 앞선 갈래의 payload 캐시가 그대로 돌아옵니다. 실제로 첫
측정에서 옛 코드가 `confidence=None` 을 돌려주어 캐시를 의심했고, 캐시를 지운 뒤 `0` 으로
바뀌었습니다.

### S-1. 추천은 있고 확신도만 없는 종목이 「미산출」을 보인다 (회귀)
- 조작: VCP 화면에서 과거 → 2026-05-05 을 고르고 `003550` LG 행을 눌러 상세 모달을 연다.
- 기대: 게이지 가운데 글자가 `0%` 가 아니라 `미산출` 이고 진행 원호가 그려지지 않는다.
- 필수 여부(required): 예
- 실제: 고친 뒤 `게이지글자: "미산출"`, `원개수: 1`(배경 원만). 고치기 전 `게이지글자: "0%"`,
  `원개수: 2`. 사유 본문 「확신도만 비어 있는 행입니다.」 도 함께 확인했다.
- 결과: 통과
- 증거: `jongga008-vcp-missing.png`, `jongga008-vcp-before.png`
- 정리(cleanup): 이 시나리오가 소유한 임시 자료 없음

### S-2. 확신도가 채워진 종목은 그 값을 그대로 보인다 (인접)
- 조작: 같은 화면에서 `005380` 현대차 행의 상세 모달을 연다.
- 기대: 가운데 글자가 `78%` 이고 원호가 78% 만큼 그려진다.
- 필수 여부(required): 예
- 실제: `게이지글자: "78%"`, `진행원호: "117.624 150.8"`. 150.8 의 78% 가 117.624 다.
- 결과: 통과
- 증거: 위 실행 로그
- 정리(cleanup): 이 시나리오가 소유한 임시 자료 없음

### S-3. 추천 자체가 없는 종목도 0% 를 그리지 않는다 (인접)
- 조작: `403870` HPSP 행의 상세 모달을 연다.
- 기대: 가운데 글자가 `미산출` 이고 본문이 「AI 분석 데이터 없음」 이다.
- 필수 여부(required): 예
- 실제: `게이지글자: "미산출"`, `원개수: 1`, `분석없음문구: true`.
- 결과: 통과
- 증거: 위 실행 로그
- 정리(cleanup): 이 시나리오가 소유한 임시 자료 없음

### S-4. 백엔드 응답의 확신도가 0 이 아니라 값 없음이다 (회귀)
- 조작: `GET /api/kr/signals?date=2026-05-05` 응답에서 세 종목의
  `gemini_recommendation.confidence` 를 읽는다.
- 기대: LG 는 `null`, 현대차는 `78`, HPSP 는 추천 자체가 `null` 이다.
- 필수 여부(required): 예
- 실제:

  | 종목 | 고치기 전 | 고친 뒤 |
  |---|---|---|
  | `003550` LG | `confidence=0 action='BUY'` | `confidence=None action='BUY'` |
  | `005380` 현대차 | `confidence=78 action='HOLD'` | `confidence=78 action='HOLD'` |
  | `403870` HPSP | `gemini_recommendation=None` | `gemini_recommendation=None` |

- 결과: 통과
- 증거: 위 표
- 정리(cleanup): 이 시나리오가 소유한 임시 자료 없음

### S-5. 판정만 있고 확신도가 없는 종가베팅 종목이 「미산출」을 보인다 (회귀)
- 조작: 종가베팅 화면을 열고 S-Oil 카드의 「확신도」 줄을 읽는다. 이 종목은 사본에서
  `ai_evaluation` 을 지우고 `ai_action` 만 남겨 `_normalize_jongga_signal_for_frontend`
  의 자리를 타게 했다.
- 기대: 0% 막대가 아니라 `미산출` 이다.
- 필수 여부(required): 예
- 실제: 고친 뒤 `미산출 ← S-Oil`. 고치기 전 `0% ← S-Oil`.
- 결과: 통과
- 증거: `jongga008-closing-bet-missing.png`, `jongga008-closing-bet-before.png`
- 정리(cleanup): 이 시나리오가 소유한 임시 자료 없음

### S-6. 사유 문자열만 있는 종가베팅 종목의 동작이 그대로다 (인접)
- 조작: 로보티즈 카드의 「확신도」 줄을 읽는다. 이 종목은 `score.llm_reason` 만 남겼다.
- 기대: `미산출` 이다.
- 필수 여부(required): 예
- 실제: 고친 뒤와 고치기 전 모두 `미산출 ← 로보티즈`.
- 결과: 통과
- 정리(cleanup): 이 시나리오가 소유한 임시 자료 없음
- **계획과 달라진 점**: 이 갈래를 회귀로 잡았으나 실측에서 고치기 전에도 이미 「미산출」
  이었다. `_extract_jongga_ai_evaluation` 의 `confidence: 0` 이 이 화면 경로에는 닿지
  않는다는 뜻이므로 인접 시나리오로 고쳐 적는다. 그 자리를 고친 것은 유지한다. 응답을
  만드는 다른 소비자가 같은 값을 읽기 때문이다.

### S-7. 확신도가 채워진 종가베팅 종목은 그대로다 (인접)
- 조작: 나머지 일곱 카드의 「확신도」 줄을 읽는다.
- 기대: 원본 자료의 확신도가 백분율로 보인다.
- 필수 여부(required): 예
- 실제: `75% 75% 76% 74% 72% 65% 62%`. 원본 `jongga_v2_latest.json` 의 원익홀딩스 75,
  한미반도체 75, 대한항공 76, 레인보우로보틱스 74, SK이노베이션 72, 삼성전자우 65,
  에스피지 62 와 모두 일치한다. 고치기 전과도 같다.
- 결과: 통과
- 정리(cleanup): 이 시나리오가 소유한 임시 자료 없음

### S-8. 정적 검증 전체가 통과한다 (회귀)
- 조작: `pytest`, `cd frontend && npx vitest run`, `cd frontend && npm run type-check` 를 돌린다.
- 기대: 셋 다 종료 코드 0 이고 실패 0 건이다.
- 필수 여부(required): 예
- 실제: `1741 passed, 2 skipped` / `299 passed` / 종료 코드 0.
- 결과: 통과
- 정리(cleanup): 이 시나리오가 소유한 임시 자료 없음

### S-9. 콘솔과 링크가 성하다 (리포트)
- 조작: 두 화면에서 콘솔 오류와 같은 오리진 링크를 확인한다.
- 기대: 콘솔 오류 0 건.
- 필수 여부(required): 아니오
- 실제: 콘솔 오류 0 건. 링크 목록은 외부 종목 페이지(네이버·토스)와 뉴스가 대부분이며
  끊긴 같은 오리진 링크는 없었다.
- 결과: 통과
- 정리(cleanup): 이 시나리오가 소유한 임시 자료 없음

## 이월한 발견

- **VCP 상세 모달의 게이지가 탭에 따라 갈린다** → 새 TODO 항목으로 올린다. `code-review`
  가 짚었다. 화면의 `rec` 은 활성 탭에 따라 gpt·perplexity·gemini 중 하나인데, 이번에
  `safe_confidence` 를 거치도록 고친 것은 `_build_vcp_gemini_recommendation` 이 만드는
  gemini 추천 하나뿐이다. 나머지 둘은 `ai_analysis.json` 캐시에서 오며 그 캐시는
  `engine/vcp_ai_analyzer_helpers.py:658` 의 `_normalize_confidence_value(..., default=0)`
  를 지난다. 그 파일은 `tier-rules.md` §2 의 위험 경로 「VCP 판정」에 속해 한 줄만 고쳐도
  T3 이 되므로 이번 라운드(T2)의 범위를 넘는다.
- **`RecommendationCombiner.combine` 의 「둘 다 없음 → confidence 0」** → 같은 항목에
  함께 적는다. `engine/kr_ai_strategies.py:150` 이 두 AI 판정을 평균하거나 비교하는
  계산 자리라서 `None` 을 받으면 계산 자체가 성립하지 않는다. 이번 범위 밖으로 두되,
  그 0 이 화면까지 확신도로 흘러가는지는 확인이 필요하다.

## 실행 결과

- 필수 시나리오: 통과 8 / 전체 8
- 선택 시나리오: 통과 1 / 전체 1
- 미통과 필수: 없음
- 수정: 0 건 (QA 도중 발견해 고친 것 없음)
- 계획에서 고친 것: S-5 와 S-6 의 성격을 실측에 맞게 맞바꿨다. 처음에 사유 문자열 갈래를
  회귀로 잡았으나 고치기 전에도 「미산출」이었고, 실제 회귀는 `ai_action` 갈래였다.

### 정적 검증

| 명령 | 결과 | 종료 코드 |
|---|---|---|
| `pytest` | `1741 passed, 2 skipped` | 0 |
| `cd frontend && npx vitest run` | `299 passed` (47 파일) | 0 |
| `cd frontend && npm run type-check` | 오류 없음 | 0 |

새 검사가 결함을 실제로 막는지는 `git worktree` 로 `3aa0ef7` 을 체크아웃하고 헬퍼만
옮겨 심어 확인했다. 파이썬 검사 9 건과 화면 검사 1 건이 그 코드에서 실패했고, 헬퍼 자체를
검사하는 16 건만 통과했다.

### 되돌릴 수 없는 조작

하나도 실행하지 않았다. 「재분석」·「Refresh VCP」·매수 버튼·챗봇 전송·설정 저장에 손대지
않았고 `localStorage` 의 `browser_session_id` 도 바꾸지 않았다. 원본 `data/` 는
`git status data/` 로 검사 전후 모두 비어 있음을 확인했다.

### 정리

- `git worktree` 는 제거하고 `git worktree prune` 을 실행했다.
- QA 용 gunicorn 과 `npm run dev` 는 종료했다.
- 자료 사본과 픽스처 스크립트는 scratchpad 안에만 있으며 저장소에 남기지 않는다.
