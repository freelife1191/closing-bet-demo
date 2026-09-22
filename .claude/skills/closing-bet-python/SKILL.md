---
name: closing-bet-python
description: 이 저장소의 Flask 백엔드(app/, services/, engine/, chatbot/, scripts/, tests/)를 고치거나 검토할 때 먼저 읽는다. 파이썬 파일을 하나라도 건드리면 해당한다. 「시그널 판정 고쳐」「API 응답 바꿔」「스케줄러 손봐」「챗봇 프롬프트 수정」「폴백 판정」처럼 파이썬이나 Flask 라는 말이 없어도 서버 동작이 바뀌면 이 스킬이다. 계층, 재사용 사다리, engine/constants 우선, 위험 경로와 T3 승격, data/·.env·되돌릴 수 없는 조작, gunicorn 재기동, pytest 관례를 담는다.
---

# Flask 백엔드 경계 (closing-bet-demo)

Python 3.11, Flask 3.1, gunicorn(loopback 5501, `--reload` 없음), pandas·numpy, google-genai·
openai·httpx, pytest 다. pydantic 은 전이 의존성으로만 설치되어 있고 직접 쓰지 않는다. 의존성의
정본은 `requirements.txt` 이며 새 패키지는 `[INFRA-070]` 의 고정 규칙을 따른다.

이 스킬은 `dev-cycle` 을 대체하지 않는다. 시작·티어·리뷰·QA·마감은 그 절차가 정하고, 이
문서는 파이썬 코드를 만질 때 지켜야 할 경계와 읽을 자료만 정한다.

## 먼저 읽을 것

1. `CLAUDE.md` 의 「Code Philosophy — ponytail」「Environment Variables」「Important Notes」,
   `AGENTS.md` 의 「코드 스타일」「하지 않을 것」「되돌릴 수 없는 조작」. 원문이 정본이다.
2. `dev-cycle` 의 `references/tier-rules.md` §2 위험 경로. 거기 적힌 파일에 **한 줄이라도 닿으면
   T3** 다. 판정은 절 이름이 아니라 파일 목록을 `grep` 으로 대조해서 한다. 이름에 vcp 가 들어간
   `services/kr_market_vcp_background_service.py` 는 목록에 없고, 그 함수가 부르는
   `scripts/init_data.py` 는 있다. 그래서 무엇을 함께 고치느냐에 따라 티어가 갈린다. TODO 에
   적힌 티어를 그대로 믿지 말고 건드릴 파일 목록으로 다시 판정한다.
3. 바꾸려는 함수의 호출자 전부. `grep` 으로 세고 나서 고친다.

## 계층

    app/routes/*   Blueprint. HTTP 변환과 가드만 둔다. 팩토리는 app/__init__.py
    services/*     업무 흐름, 캐시, 파일·SQLite 입출력, 상태 파일
    engine/*       판정·점수·수집·LLM 호출. Flask 객체를 알지 않는다
    chatbot/*      챗봇. chatbot/core.py 가 오케스트레이터
    scripts/init_data.py   적재 파이프라인. 스케줄러와 「Refresh」 계열이 부른다

라우트에 업무 규칙을 두지 않고, engine 이 `request` 나 `jsonify` 를 import 하지 않게 한다.
인증은 `app/routes/route_guards.py` 의 `require_admin` 과 `services/identity_helpers.py` 의
`verify_identity_header` 뿐이다. 신원은 Next 의 proxy 가 서명한 헤더에서만 나온다.
`X-User-Email` 같은 브라우저 값을 신원으로 읽는 코드를 만들지 않는다.

## 재사용 사다리

새 코드를 쓰기 전에 첫 번째로 붙잡히는 단에서 멈춘다.

1. 필요한가. 추측성 요구면 만들지 않고 한 줄로 적는다.
2. 이미 있는가. `engine/constants*.py`(임계값·상수), `engine/error_handler*.py`
   (`safe_execute`, `execute_with_fallback`, `validate_range`), `engine/llm_utils*.py`
   (재시도, `extract_json_from_response`, 배치), `engine/pandas_utils*.py`(`safe_float`,
   `load_csv_file`, `sanitize_for_json`), `services/kr_market_csv_utils.py`,
   `services/file_backed_status.py`. 몇 파일 건너에 있는 것을 다시 만드는 것이 가장 흔한 낭비다.
   함수 파일 안에서 보이지 않는 재사용도 있다. `run_vcp_background_pipeline` 의 `status_state` 는
   라우트(`app/routes/kr_market.py`)가 `FileBackedStatus` 를 만들어 주입한 것이라 호출부까지
   읽어야 무엇을 이미 쓰고 있는지 보인다.
3. 표준 라이브러리나 pandas 가 하는가.
4. 그제야 최소 코드.

리터럴 임계값은 코드에 두지 않고 `engine/constants_*.py` 의 dataclass 에 이름을 붙여 둔다.
`[VCP-033]` 에서 `engine/vcp.py` 의 0.5 와 폴백의 0.5 가 따로 있던 것을
`VCPThresholds.STRONG_CONTRACTION_RATIO` 로 합친 것이 그 예다. 버그는 증상이 난 호출자가
아니라 모든 호출자가 지나는 공통 함수 한 곳에서 고친다.

## 코드 규칙

`AGENTS.md` 「코드 스타일」이 정본이다. 요약하면 파일 머리 `#!/usr/bin/env python3` 와
`# -*- coding: utf-8 -*-`, 임포트는 표준 → 서드파티 → 로컬, 인자와 반환값에 타입 힌트, 모듈
수준 `logger = logging.getLogger(__name__)`, `continue`·`return`·`raise` 앞에 로그, 로그 없는
빈 `except:` 금지, 경로는 `os.path` 와 `__file__`, 큰 숫자는 `1_000_000_000`. Enum 은 키가
영어이고 값이 한국어다.

## 데이터, 비밀, 외부 효과

- `data/` 는 git 이 추적하지 않는다. 실측할 때 읽기 전용으로만 열고 테스트는 `tmp_path` 에
  자기 자료를 만든다. 원본 `data/` 를 쓰는 테스트를 만들지 않는다.
- `.env` 는 실제 비밀이다. 변수 이름과 값의 유무만 확인하고 값은 어디에도 옮겨 적지 않는다.
  변수를 추가하면 `.env.example` 을 함께 고친다. `.env` 파일을 고쳐도 돌고 있는 워커의
  `os.environ` 은 바뀌지 않으며, 반영은 재기동뿐이다. 장 중에는 재기동하지 않는다.
- 되돌릴 수 없는 조작(설정 저장, AI 재분석, Refresh VCP, Refresh Market Gate, 챗봇 전송,
  모의 매수, 삭제 계열)을 원본 서버에 요청하지 않는다. 서브에이전트를 띄울 때는 어느 포트에
  무엇이 떠 있고 어떤 메서드를 보내면 안 되는지를 프롬프트에 적는다. 2026-09-07 에 보안 리뷰
  에이전트가 실측 중 `DELETE /api/system/env` 를 보낸 일이 있다.
- LLM 호출은 비용이다. 테스트와 하네스는 가짜 클라이언트를 끼운다.
  `tests/engine/test_vcp_ai_analyzer_refactor.py` 의 구조가 예다. 폴백 판정처럼 실패 경로는
  파싱 실패를 주입한 하네스로만 재현한다.
- gunicorn 은 `--reload` 없이 돈다. 파이썬을 고쳤으면 실측 전에 마스터에 `kill -HUP` 을 보낸다.
  생존 확인 경로는 `/api/kr/market-gate` 이고 `/api/health` 는 없다.

## 검증

    source venv/bin/activate && pytest                 # 저장소 루트에서. 전체
    pytest tests/services/test_kr_market_vcp_background_service_refactor.py -k name   # 변경 범위만

테스트는 고친 모듈의 패키지를 따라 `tests/<패키지>/test_<모듈>_refactor.py` 에 둔다. `services/`
의 모듈이면 `tests/services/` 다. `tests/conftest.py` 가 저장소 루트를
`sys.path` 에 넣으므로 테스트 파일 머리에서 경로를 만지지 않는다. 경로와 환경은
`monkeypatch` 로 바꾸고(`init_data.BASE_DIR` 을 `tmp_path` 로 두는 식), 네트워크·LLM·원본
`data/` 에 닿지 않는다. 분기·반복·파서·판정에는 검사 하나를 남기고 한 줄 변경에는 만들지
않는다. 실패하는 테스트의 기대값을 손질해 넘기지 않으며, 삭제 기준은 `dev-cycle` 의
「테스트 정책」이다.

서버 동작을 실측하려면 원본이 아니라 격리 사본에서 `SCHEDULER_ENABLED=false` 로 gunicorn 을
띄운다. 환경 구성과 증거 기록은 `closing-bet-verify` 스킬에 있다.
