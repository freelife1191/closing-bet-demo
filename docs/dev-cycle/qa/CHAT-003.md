# [CHAT-003] 두 SQLite 캐시 모듈을 공용 골격으로 통합 — QA 시나리오

- 대상 화면: http://localhost:3500/chatbot
- 구성 근거: /qa-only 리포트 (`.gstack/qa-reports/qa-report-chatbot-2026-09-05.md`)
  + 이번 사이클의 변경 세 파일 (`services/sqlite_ready_gate.py` 신규,
  `chatbot/runtime_stock_map_cache.py`, `chatbot/stock_context_cache.py`)
- 구성 2026-09-05 15:42 | 실행 (미실행)

## 이 항목이 화면에 닿는 경로

바꾼 것은 백엔드의 캐시 두 모듈이고 화면 코드는 한 줄도 건드리지 않았습니다. 그런데도
화면 검사가 필요한 이유는 두 캐시가 챗봇의 답변 생성에 쓰이기 때문입니다.

- `runtime_stock_map_cache` 는 `korean_stocks_list.csv` 를 읽어 만든 종목명↔티커 매핑을
  캐시합니다. 챗봇이 질문에서 「삼성전자」를 종목으로 알아보는 근거가 이 매핑입니다.
  호출자는 `chatbot/runtime_setup_service.py:128` 의 `load_stock_map` 입니다.
- `stock_context_cache` 는 종목별 가격 이력과 수급 추이와 시그널 이력을 문자열로 만들어
  캐시합니다. 챗봇이 답변에 넣는 종목 상세가 여기서 나옵니다. 호출자는
  `chatbot/stock_context.py:127` 의 `_fetch_ticker_context_text` 입니다.

두 캐시는 같은 `data/runtime_cache.db` 파일을 쓰되 테이블이 다릅니다
(`chatbot_stock_map_cache`, `chatbot_stock_context_cache`). 그래서 준비 상태를 기록하는
게이트도 따로 두어야 합니다. 한 테이블이 준비되었다는 이유로 다른 테이블까지 준비된 것으로
판정하면 없는 테이블에 질의하게 됩니다.

**챗봇에 질문을 보내는 조작은 시나리오에 넣지 않았습니다.** 실제 Gemini 호출이 일어나
비용이 발생하고 사용량 쿼터가 줄어듭니다. `archive-format.md` §8 의 마지막 조항이 이런
조작을 시나리오에서 제외하도록 정하고 있습니다. 대신 캐시가 실제로 읽히는지는 S-2 부터
S-4 까지에서 파이썬으로 직접 확인하고, 화면 쪽은 캐시 초기화가 실패하면 반드시 드러나는
지점을 봅니다.

## 사전 조건

Flask 워커가 이번 변경을 담은 코드로 떠 있어야 합니다. gunicorn 은 코드를 자동으로 다시
읽지 않으므로, 마스터 프로세스에 `HUP` 을 보내 워커를 교체한 상태여야 합니다.

    ps -eo pid,ppid,command | grep "[f]lask_app:app" | head -3   # 마스터 PID 확인
    kill -HUP <마스터 PID>

## 시나리오

### S-1. 챗봇 화면이 오류 없이 렌더된다 (회귀)
- 조작: 대화 기록이 없는 브라우저 세션으로 `http://localhost:3500/chatbot` 을 연다.
  콘솔을 읽고, 버튼 수와 포커스 가능 요소 수와 `h1` 개수를 센다.
- 기대: HTTP 200. 콘솔 오류 **0건**. 버튼 **25개**, 포커스 가능 요소 **28개**,
  `h1` **1개**, `alt` 없는 이미지 **0개**. 인사말은 「안녕하세요, 흑기사님」과
  「무엇을 도와드릴까요?」 두 줄이고, 대화 목록 자리에는 「저장된 대화가 없습니다.」가
  나온다.
- 결과:

### S-2. 종목맵 캐시가 기존 SQLite 행을 그대로 읽는다 (회귀)
- 조작: `data/runtime_cache.db` 를 임시 디렉터리로 복사한다(원본을 쓰기 모드로 열지
  않기 위해서다). 그 디렉터리를 `data_dir` 로 주고, `source_path` 에는 원본
  `data/korean_stocks_list.csv` 를, `signature` 에는 그 파일의 실제 서명을 주어
  `chatbot.runtime_stock_map_cache.load_stock_map_cache` 를 부른다.
- 기대: 캐시 **히트**. `stock_map` 과 `ticker_map` 이 각각 **1,997건**이고,
  `stock_map['삼성전자'] == '005930'`, `ticker_map['005930'] == '삼성전자'` 다.
  저장된 행의 서명 `(1770785642634316972, 58248)` 이 현재 CSV 의 서명과 같으므로
  히트가 정상이다.
- 결과:

### S-3. 종목 컨텍스트 캐시가 기존 SQLite 행을 그대로 읽는다 (회귀)
- 조작: S-2 와 같은 복사본을 대상으로
  `chatbot.stock_context_cache.load_cached_result_text` 를 세 번 부른다. 인자는 저장된
  행의 서명을 그대로 쓴다.

  | `path` | `dataset` | `ticker_padded` | `signature` |
  |---|---|---|---|
  | `data/daily_prices.csv` | `stock_history` | `005930` | `(1777948147837105742, 2456317)` |
  | `data/all_institutional_trend_data.csv` | `institutional_trend` | `005930` | `(1777948178391568766, 2915409)` |
  | `data/signals_log.csv` | `signal_history` | `009830` | `(1777948191823387294, 10446)` |
- 기대: 세 건 모두 **히트**. 반환 문자열의 길이가 차례로 **270**, **283**, **15** 다.
  첫 건은 `- 2026-05-04: 종가 232,500` 으로 시작하고, 셋째 건은 `과거 VCP 포착 이력 없음`
  이다.
- 결과:

### S-4. 서명이 달라지면 캐시를 쓰지 않는다 (회귀)
- 조작: S-3 과 같은 조회를 하되 `signature` 에 **현재** CSV 파일의 서명을 준다.
  `daily_prices.csv` 는 `(1788508861907600614, 10333779)`,
  `all_institutional_trend_data.csv` 는 `(1788508893591988254, 3836102)` 다.
- 기대: 두 건 모두 **미스**(`None`). 캐시에 저장된 행의 서명과 다르므로 그 행을 쓰면
  안 된다. 여기서 히트가 나오면 낡은 값을 챗봇 답변에 싣게 된다.
- 결과:

### S-5. 챗봇 초기화 API 두 개가 정상 응답한다 (인접)
- 조작: `curl http://localhost:5501/api/kr/chatbot/welcome` 과
  `curl http://localhost:5501/api/kr/chatbot/suggestions` 를 부른다.
- 기대: 둘 다 HTTP **200**. `welcome` 의 `message` 는 「안녕하세요! **스마트머니봇**
  입니다」로 시작한다. `suggestions` 의 `suggestions` 배열은 **5건**이고 각 항목에
  `title` 과 `prompt` 와 `desc` 와 `icon` 이 들어 있다. 목록의 종목은 그날의 분석
  결과에 따라 달라지므로 건수와 필드 구성만 본다.
- 결과:

### S-6. 모델 선택 드롭다운이 설정된 세 모델을 보여 준다 (인접)
- 조작: 하단 「FLASH」 버튼을 눌러 드롭다운을 연다.
- 기대: 항목 **3개**가 `gemini-3.5-flash-lite`, `gemini-3.7-flash`, `gemini-3.6-flash`
  순서로 나오고 `gemini-3.7-flash` 가 선택 표시를 달고 있다. 이 목록은 환경 변수
  `CHATBOT_AVAILABLE_MODELS` 에서 오므로 백엔드가 살아 있어야 채워진다.
- 결과:

### S-7. 사이드바 링크 일곱 개가 모두 유효하다 (인접)
- 조작: 사이드바의 링크를 훑어 대상 주소를 읽는다.
- 기대: **7개**이고 각각 `/`(스마트 머니 봇), `/dashboard/kr`(Overview),
  `/dashboard/kr/vcp`(VCP 시그널), `/dashboard/kr/closing-bet`(종가베팅),
  `/dashboard/kr/cumulative`(누적 성과), `/chatbot`(AI 상담),
  `/dashboard/data-status`(데이터 상태)를 가리킨다. 끊어진 링크는 0개다.
- 결과:

### S-8. 추천 질문과 빠른 조회 버튼이 그대로다 (인접)
- 조작: 본문의 추천 질문 카드와 하단의 빠른 조회 버튼을 센다. 누르지는 않는다.
  누르면 곧바로 메시지가 전송되어 Gemini 호출이 일어난다.
- 기대: 추천 질문 카드 **4개**로 「마켓게이트 상태와 투자 전략」, 「AI 분석 기반 매수
  추천 종목」, 「오늘의 S/A급 종가베팅 추천」, 「최근 주요 뉴스와 시장 영향」이다.
  빠른 조회 버튼 **5개**로 「시장 현황」, 「VCP 추천」, 「종가 베팅」, 「뉴스 분석」,
  「내 관심종목」이다.
- 결과:

## 이월한 발견

1단계 리포트가 지적한 세 건은 전부 프런트엔드 화면의 결함이고, 이번 항목이 고치기로 한
백엔드 캐시 통합과는 다른 자리입니다. 고치려면 `frontend/src/app/chatbot/page.tsx` 를
건드려야 하므로 범위 밖으로 판단해 백로그로 올렸습니다.

- ISSUE-001 「입력 영역의 버튼 세 개에 접근 가능한 이름이 없다」 → `[CHAT-007]` 에
  체크박스로 합쳤습니다. 그 항목이 이미 같은 파일의 키보드·스크린 리더 접근성을 다루고
  있어서 따로 세우면 같은 파일을 두 번 건드리게 됩니다. 보내기 버튼(`fa-paper-plane`)과
  모바일 햄버거 버튼(`fa-bars`)은 `title` 조차 없고, 파일 첨부와 음성 입력은 `title` 만
  있어 접근성 트리에서는 이름이 비어 있습니다.
- ISSUE-002 「데스크톱 폭에서 모바일 폭으로 줄이면 사이드바가 본문을 덮는다」 →
  `[CHAT-010]`. 초기 렌더는 정상이고 뷰포트가 바뀌는 순간에만 사이드바의 열림 상태가
  정리되지 않습니다.
- ISSUE-003 「대화 기록이 있을 때 React key 경고가 두 건 난다」 → `[CHAT-011]`.
  대화가 없으면 콘솔이 깨끗하므로 대화 목록을 렌더하는 자리의 문제입니다.

## 실행 결과

(`/qa` 실행 후에 채웁니다.)
