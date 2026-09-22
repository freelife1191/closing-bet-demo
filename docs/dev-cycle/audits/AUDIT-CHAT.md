# AUDIT-CHAT — 챗봇 감사 (2차, 2026-09-22)

> 1차 감사(2026-09-01, `[INFRA-004]`)의 지적은 아래 「이전 감사 대조」 표로 대조했다. 이번 감사는
> 사용자가 요청한 세 가지, 곧 채팅 모드 세 갈래(AI 상담·스마트머니봇·VCP 상담)의 응답 흐름,
> SQLite 저장 계층의 동시성과 복구, 벡터 DB 유무에 초점을 두었다. 감사자는 `dev-workflow`
> 에이전트이며, 리더가 §1.1·§1.2·§1.4·§1.5·§3.1 을 원본 코드로 재확인한 뒤 기록했다.

**감사 범위**: `chatbot/` 36개 파일, `app/routes/kr_market_chatbot_routes.py`,
`app/routes/kr_market_chatbot_http_routes.py`, `services/kr_market_chatbot_request_helpers.py`,
`frontend/src/app/chatbot/`, `frontend/src/app/components/ChatWidget.tsx`,
`frontend/src/app/dashboard/kr/vcp/page.tsx` 의 상담 패널

**읽은 파일 수**: 40개 / 약 9,300줄 (전문 28개, 부분 12개)

**검증 방법**: §1.1, §1.2, §1.3 은 저장소의 실제 `data/*.json` 을 `./venv/bin/python` 으로 읽어
프롬프트 문자열을 직접 생성해 확인했다. 나머지는 코드 추적으로 확인했다.

---

## 0. 벡터 DB 조사 결과

**담당 경로를 포함한 저장소 전체에 벡터 검색이나 임베딩 저장 구현이 없다.** 다음 명령으로 `*.py`,
`*.ts`, `*.tsx`, `*.txt`, `*.json`, `*.md` 를 훑었고(`node_modules` 와 `docs/dev-cycle` 제외) 일치하는
줄이 한 건도 없었다. 리더가 `requirements.txt` 와 `frontend/package.json` 에서도 같은 결과를 확인했다.

```
grep -rniE "chroma|faiss|pinecone|qdrant|weaviate|milvus|embedding|vector_?store|pgvector|sentence_transformers|text-embedding"
```

현재 문맥 주입 방식은 전부 결정적 규칙이다. `chatbot/intent_context.py:12-16` 의 키워드 집합 다섯 개가
의도를 가르고, 그 의도에 해당하는 JSON 파일을 통째로 읽어 상위 N건을 문자열로 붙인다. 벡터 DB 도입은
제안하지 않으며, 아래 §1 과 §2 에 적은 것은 이 규칙 기반 방식에서 **실제로 관찰된** 결함뿐이다.
저장은 SQLite 두 계층(대화 이력 `chatbot_sessions`·`chatbot_messages`, 메모리)뿐이다.

---

## 1. 깨진 동작

### 1.1 섹터 변동률이 「점수」로 프롬프트에 실려 모든 섹터가 붉은색으로 표시된다

- 위치: `chatbot/payload_service.py:24-28`, `chatbot/prompts.py:136-147`, `chatbot/prompts.py:119-122`
- 증상: 오늘 자 실제 데이터로 시스템 프롬프트를 생성하면 다음과 같이 나온다.

```
## 섹터별 점수 (Market Gate)
🔴 반도체: 2.93점
🔴 증권: 1.95점
🔴 헬스케어: 1.8점
...
🔴 자동차: -0.57점

## 오늘의 시장 현황
- **KOSPI**: 7110.759765625
- **KOSDAQ**: 843.239990234375
```

- 원인: `collect_market_context` 가 `market_gate.json` 의 `sectors[].change_pct`(퍼센트 변동률)를
  `sector_scores` 사전에 그대로 넣는다. `build_system_prompt` 는 그 값을 0에서 100 사이의 점수로
  가정해 70점 이상이면 초록, 40점 이상이면 노랑, 그 아래면 빨강을 붙이고 단위를 「점」으로 적는다.
  변동률은 언제나 한 자릿수이므로 **모든 섹터가 예외 없이 빨간색**이 된다. 같은 자리에서 환율만
  `{:,.0f}` 로 포맷되고 지수 두 개는 원시 부동소수점이 그대로 실린다.
- 영향: 모델은 반도체가 2.93% 상승한 날에도 「반도체 2.93점, 매우 약함」이라는 입력을 받는다. 시장과
  섹터 질문의 답변 방향이 실제와 반대로 유도된다. 지수값의 소수 아홉 자리는 모델이 그대로 받아 적을
  수 있다.
- 심각도: **P0**
- 최소 수정 방향: `build_system_prompt` 의 섹터 절을 없애고 `intent_detail_service.build_market_gate_context`
  가 이미 올바르게 만드는 퍼센트 표기 하나로 모은다(§2.2 와 같은 수정이다). 지수에는 `{:,.2f}` 를
  적용한다.

### 1.2 분석된 VCP 시그널이 있는데도 「시그널이 없습니다」라고 답한다

- 위치: `chatbot/signal_context.py:103-129`, `chatbot/intent_context.py:19-27`
- 재현: 오늘 자 `data/kr_ai_analysis.json` 을 그대로 읽어 확인했다.

```
VCP signals loaded: 4
VCP BUY text -> ''
VCP intent context -> '\n[VCP AI 분석 결과]\n현재 분석된 VCP 시그널이 없습니다.'
```

- 원인: `build_vcp_buy_recommendations_text` 는 `action == "BUY"` 인 시그널만 문자열에 담는다. 현재
  네 건은 모두 `gemini_recommendation.action == "HOLD"` 이므로 결과가 빈 문자열이 되고,
  `build_vcp_intent_context` 가 빈 문자열을 「분석 자체가 없음」으로 해석해 안내 문구로 바꾼다.
  「매수 추천이 없다」와 「분석이 없다」가 같은 값으로 뭉개진다.
- 영향: 같은 `kr_ai_analysis.json` 을 `services/kr_market_vcp_payload_service.py:296` 이 읽어 VCP
  화면의 표를 그린다. **사용자는 한 화면에서 네 종목의 분석 결과를 보면서, 그 옆의 상담 패널에서는
  「분석된 시그널이 없다」는 답을 받는다.** 「오늘 자 시그널 데이터가 없을 때」의 문맥 주입 자리가
  바로 여기이며, 실제로는 데이터가 있을 때도 없다고 말하고 있다.
- 심각도: **P0**
- 최소 수정 방향: `fetch_vcp_ai_analysis` 가 시그널 건수와 추천 분포를 함께 돌려주고,
  `build_vcp_intent_context` 가 「분석 0건」과 「분석 N건, 매수 추천 0건」을 다른 문구로 가른다.

### 1.3 시그널과 뉴스에 기준일이 없어 넉 달 전 자료가 「오늘」로 제시된다

- 위치: `chatbot/signal_context.py:87-100`, `chatbot/signal_context.py:34-49`, `chatbot/prompts.py:118`,
  `chatbot/prompts.py:23-31`
- 관찰: `data/kr_ai_analysis.json` 의 `signal_date` 는 `2026-05-05` 이고 `generated_at` 은
  `2026-05-05T12:06:00` 이다. 오늘은 2026-09-22 이므로 **넉 달 반이 지난 자료**다.
  `data/jongga_v2_latest.json` 의 `date` 는 `2026-09-21` 로 하루 전이다.
- 원인: `load_vcp_ai_signals` 와 `load_jongga_signals` 는 파일의 날짜 필드를 읽지도 비교하지도 않는다.
  `build_vcp_buy_recommendations_text` 와 `build_latest_news_text` 가 만드는 문자열에는 날짜가 한
  글자도 들어가지 않는다. 그런데 `build_system_prompt` 는 그 위에 `## 오늘의 시장 현황` 이라는 제목을
  붙이고, `SYSTEM_PERSONA` 는 「일반적인 지식보다 실시간 수집 데이터를 우선해」라고 지시한다.
- 영향: 사용자가 「요즘 VCP 추천 뭐 있어?」라고 물으면 모델은 5월 자료를 오늘 것으로 알고 답한다.
  뉴스도 마찬가지로 전날 파일에서 뽑히지만 「최근 뉴스」라는 제목만 붙는다. 세 모드 가운데
  종가베팅만 `build_jongga_candidates_text` 가 각 행에 `signal_date` 를 실어 주므로 부분적으로
  안전하다.
- 심각도: **P0**
- 최소 수정 방향: 각 문맥 블록의 첫 줄에 원본 파일의 기준일을 적고, 오늘과 다르면 「이 자료는 N일 전
  기준입니다」를 함께 싣는다. 파일 세 개의 로더가 이미 dict 를 읽고 있으므로 날짜 필드를 함께
  돌려주면 된다.

### 1.4 메모리 저장 경로가 잠금 없이 공유 사전을 통째로 교체한다

- 위치: `chatbot/storage_memory_manager.py:157-164`, `:166-184`, `:193-201`, `:220-229`
- 근거: `chatbot/__init__.py:8-21` 의 `get_chatbot()` 은 프로세스마다 인스턴스 하나를 만들어
  재사용하고, `KRStockChatbot.__init__` 이 그 안에 `MemoryManager` 하나를 둔다. gunicorn 워커 하나에
  스레드가 여덟 개이므로 **여덟 요청이 같은 객체를 동시에 건드린다.** `chatbot/` 전체에서
  `threading.Lock` 을 쓰는 곳은 `runtime_stock_map_cache.py:39` 뿐이고, 두 저장소 매니저에는 잠금이
  없다.
- 재현 조건: `add()` 는 `self._reload()` 로 `self.memories` 를 통째로 새 사전으로 바꾼 뒤(157-164)
  새 키를 넣고(196-199) `_save_single_entry` 가 `self.memories[owner_id][key]` 를 다시 읽는다(171).
  그 사이에 다른 스레드가 `view()` 를 부르면 `view()` 안의 `_reload()` 가 `self.memories` 를 다시
  교체하므로, 방금 넣은 키가 사라져 **`KeyError` 로 떨어진다.** `update()` 도 같은 구조이며, 이쪽은
  분리된 옛 사전을 고친 뒤 새 사전의 값을 저장하므로 **사용자가 입력한 값 대신 옛 값이 기록될 수
  있다.**
- 이 경합이 흔한 이유: `chatbot/payload_service.py:52-54` 의 `format_for_prompt` 가 모든 채팅
  요청에서 `view()` 를 부르고, `view()` 는 매번 `_reload()` 를 한다. 즉 채팅 한 건마다 공유 사전
  교체가 한 번씩 일어난다.
- 영향: `/memory add` 와 설정 화면의 프로필 저장이 동시 트래픽에서 간헐적으로 실패하거나 옛 값으로
  되돌아간다. `_execute_command` 가 예외를 삼켜 「명령어 처리 중 오류」로만 보이므로 원인을 추적하기
  어렵다.
- 심각도: **P1**
- 최소 수정 방향: `MemoryManager` 에 인스턴스 잠금 하나를 두고 `_reload` 와 쓰기 메서드 전체를
  감싼다. 더 작은 수정으로는 `_save_single_entry` 가 `self.memories` 를 다시 읽지 않고 방금 만든
  레코드를 인자로 받는 방법이 있다.

### 1.5 히스토리 전체 동기화 폴백이 다른 워커의 세션을 지운다

- 위치: `chatbot/storage.py:139-175`, `chatbot/storage_sqlite_history.py:500-536`, `:146-193`
- 원인: `HistoryManager._save()` 는 변경 표시가 비어 있거나(155-156) 델타 적용이 실패하면(158-160)
  `save_history_sessions_to_sqlite` 를 부른다. 그 함수는 마지막에 `_delete_stale_sessions_cursor` 를
  실행해 **이 워커의 메모리에 없는 세션을 SQLite 에서 전부 삭제한다.** `chatbot_messages` 에
  `ON DELETE CASCADE` 가 걸려 있으므로 대화 내용까지 함께 사라진다.
- 재현 조건: 워커 A 가 세션 S1 을 표시하고 `_save()` 에 들어가 SQL 을 실행한 직후, 아직
  `_pending_changed_session_ids.clear()`(171-173)가 돌기 전에 워커 A 의 다른 스레드가 S2 를 표시하면,
  그 표시가 함께 지워진다. 그다음 `_save()` 는 변경 표시가 비어 있으므로 전체 동기화 갈래로
  떨어지고, 그 시점에 워커 B 가 새로 만든 세션은 A 의 메모리에 없으므로 삭제 대상이 된다.
- 이것이 알려진 결함인 근거: 같은 성격의 결함을 메모리 쪽에서 `[CHAT-022]` 가 2026-09-07 에 고쳤다.
  그 수정의 산물인 `chatbot/storage_sqlite_memory.py:341-344` 의 설명은 「스냅샷의 행을 upsert 한다.
  스냅샷에 없는 행은 지우지 않는다. 다른 워커가 저장한 행일 수 있다」이고,
  `chatbot/storage_memory_manager.py:175-177` 의 `ponytail:` 주석은 「종전의 전체 동기화 재시도는 다른
  워커의 행을 지웠으므로 두지 않는다」고 적고 있다. **히스토리 쪽에는 같은 수정이 들어가지 않았다.**
- 영향: 사용자가 사이드바에서 보던 대화가 통째로 사라진다. 발생 조건이 좁아 재현은 드물지만 손실은
  되돌릴 수 없다.
- 심각도: **P1**
- 최소 수정 방향: `_save()` 의 폴백에서 `save_history_sessions_to_sqlite` 대신 삭제 절이 없는 upsert
  전용 경로를 쓰거나, 삭제 여부를 인자로 받아 폴백에서는 끄도록 한다.

---

## 2. 중복

### 2.1 SQLite 누락 테이블 복구 래퍼가 열네 벌 복제되어 있다

- 위치: `chatbot/storage_sqlite_history.py` 의 400-416, 545-562, 602-619, 678-698, 733-750, 778-794 /
  `chatbot/storage_sqlite_memory.py` 의 177-186, 235-246, 318-331, 387-401, 452-468, 504-519, 552-566,
  605-615
- 내용: 열네 함수가 모두 같은 골격을 가진다. 시작할 때 `ensure_chatbot_storage_schema` 를 부르고,
  본문을 중첩 함수로 감싸 `run_sqlite_with_retry` 에 넘기고, 예외를 잡아 `_is_missing_table_error`
  이면 `force_recheck=True` 로 스키마를 다시 만든 뒤 `_retried=True` 로 자기 자신을 다시 부른다.
  함수마다 다른 것은 안쪽 SQL 과 검사할 테이블 이름뿐이다.
- 영향: 재시도 횟수나 복구 조건을 바꾸려면 열네 곳을 함께 고쳐야 한다. 한 곳만 빠뜨리면 그 경로에서만
  복구가 동작하지 않는데, 평소에는 테이블이 있으므로 아무 증상도 나타나지 않는다.
- 심각도: **P2**

### 2.2 같은 섹터 자료가 한 프롬프트에 서로 다른 단위로 두 번 실린다

- 위치: `chatbot/prompts.py:136-147`, `chatbot/intent_detail_service.py:65-73`
- 내용: 시장 의도 질문에서는 `build_market_gate_context` 가 `- 반도체: 2.93% (Bullish)` 를 만들고,
  같은 요청의 `build_system_prompt` 가 `🔴 반도체: 2.93점` 을 만든다. 두 문자열이 한 프롬프트 안에
  함께 들어가며, 하나는 맞고 하나는 틀리다.
- 영향: §1.1 의 잘못된 표기를 고치러 온 사람이 올바른 쪽을 먼저 발견하면 결함이 없다고 판단할 수
  있다.
- 심각도: **P1** (§1.1 과 함께 고친다)

---

## 3. 과잉 설계

### 3.1 살아 있는 종목 조회 경로가 언제나 빈 목록을 보고, 동작하는 구현은 호출자가 없다

- 위치: `chatbot/__init__.py:8-21`, `chatbot/core.py:115-124`, `chatbot/data_service.py:44-48`,
  `chatbot/data_service.py:58-69`, `chatbot/stock_query_service.py:91-99`,
  `chatbot/stock_query_service.py:37-62`, `chatbot/core_data_access_mixin.py:151-164`
- 내용: `get_chatbot()` 은 `KRStockChatbot("default_user")` 를 `data_fetcher` 없이 만든다. 저장소
  전체에서 `data_fetcher` 를 넘기는 곳은 `tests/chatbot/test_data_service.py` 뿐이다. 그래서
  `get_cached_data` 는 항상 `fetch_mock_data()` 로 떨어지고, 그 함수가 돌려주는 `vcp_stocks` 는
  **빈 목록**이다. 그 결과 다음 네 가지가 모두 죽어 있다.

  - `_detect_stock_query` 가 빈 목록을 훑으므로 언제나 `None` 을 돌려주고, `payload_service.py:66-71`
    의 `[종목 조회 컨텍스트]` 절이 한 번도 붙지 않는다.
  - `prompts.py:150-160` 의 `## VCP 상위 종목 (수급 기반)` 절이 한 번도 생성되지 않는다.
  - `prompts.py:188-195` 의 웰컴 메시지 Top 3 가 한 번도 표시되지 않는다.
  - `intent_context.py:85` 의 관심종목 요약이 언제나 빈 문자열을 돌려준다.

  반대로 `detect_stock_query_from_stock_map`(37-62)은 티커와 종목명을 실제 종목 맵으로 찾아 최근 5일
  주가와 수급, VCP 시그널 이력을 붙이는 **동작하는 구현**인데, 저장소에서 부르는 곳이 테스트뿐이다.
  9월 9일 `[CHAT-005]` 가 이 구현의 private 래퍼를 「미사용 표면」으로 지웠으나, 그 판단은 호출자가
  없다는 사실에 근거했고 살아 있는 경로가 늘 빈 목록을 본다는 사실은 그때 다루지 않았다.
- 영향: 웰컴 메시지가 스스로 예시로 드는 두 질문(`prompts.py:197` 의 「오늘 뭐 살까?」와 「삼성전자
  어때?」)이 둘 다 아무 문맥도 싣지 못한다. 앞의 질문은 `intent_context.py:12-16` 의 키워드 다섯 집합
  어디에도 걸리지 않아 의도 문맥이 빈 문자열이 되고, 뒤의 질문은 의도 문맥도 종목 문맥도 비어 순수한
  페르소나만 남는다. VCP 상담 모드도 같은 사정이다. `frontend/src/app/dashboard/kr/vcp/page.tsx:1129-1131`
  이 `[종목명(티커)] ` 접두를 붙여 보내지만 서버는 그 종목의 어떤 자료도 싣지 않는데,
  `VCP_PERSONA`(`prompts.py:50-77`)는 「축소 횟수, 기간, 변동성」과 「AI 종합 점수」를 근거로 답하라고
  지시한다.
- 심각도: **P1**
- 최소 수정 방향: `_detect_stock_query` 를 `detect_stock_query_from_stock_map` 으로 연결한다. 그 경로는
  `self.stock_map` 과 실제 CSV 를 쓰므로 죽은 mock 캐시와 무관하게 동작한다. 그러면 `fetch_mock_data`
  와 `detect_stock_query_from_vcp_data` 를 함께 지울 수 있다.

### 3.2 (잔존) 순수 위임 믹스인 계층과 레거시 호환 경로

- 위치: `chatbot/core_data_context_mixin.py:14-19`(20줄짜리 빈 상속 클래스), `chatbot/core_payload_mixin.py`,
  `chatbot/core_intent_context_mixin.py`, `chatbot/core_data_access_mixin.py`, `chatbot/core.py:27-37`,
  `chatbot/core.py:184-198`, `app/routes/kr_market_chatbot_http_routes.py:140-145`
- 상태: 1차 감사 §3.2 가 지적한 것 가운데 `close()` 의 초기화 잔재는 `[CHAT-005]` 가 제거했다
  (`core.py:151-154` 확인). 그러나 믹스인 평탄화는 그 항목이 명시적으로 범위 밖으로 두었고,
  `_CompatGenerativeModel` 셔임과 `_run_legacy_model_chat` 우회 경로, `legacy_sync_mode` 도 그대로 남아
  있다. **잔존**으로 표시하며 새 항목으로 올리지는 않는다. 결함이 아니라 흐름 파악 비용이고, §1 과
  §3.1 을 고치는 쪽이 먼저다.

---

## 4. 비대한 파일

### 4.1 `HistoryManager` 한 클래스가 여덟 가지 책임을 진다

- 위치: `chatbot/storage.py:39-493` (`HistoryManager` 455줄)
- 내용: 한 클래스가 다음을 모두 담고 있다. SQLite 적재와 저장(125-175), 레거시 JSON 스냅샷의 간격
  제어와 원자적 쓰기(103-123), 파일 서명 비교로 워커 간 재적재 판정(75-101, 177-190), 정제된 메시지의
  LRU 캐시(273-286, 466-488), 세션 목록의 LRU 캐시(192-228, 392-424), 변경·삭제·전체삭제 델타
  장부(212-228), 세션 CRUD 와 소유자 판정(288-424), 메시지 CRUD 와 자동 제목과 50건 상한(426-464).
- 영향: §1.5 의 결함은 「델타 장부」와 「저장」과 「재적재」 세 책임이 서로의 상태를 잠금 없이 건드리는
  자리에서 나왔다. 세 책임이 한 클래스에 있어 경계가 보이지 않는다.
- 심각도: **P2**

---

## 5. 검증 공백

### 5.1 프롬프트 최종 문자열과 스토리지 동시성을 확인하는 검사가 없다

- 위치: `tests/chatbot/test_payload_service.py:79-86`, `tests/chatbot/test_intent_context.py:24-28`,
  `tests/chatbot/test_history_manager_sync.py`(테스트 16건), `tests/chatbot/test_storage_sqlite.py`(1,280줄)
- 내용은 두 갈래다.

  **첫째, 단위 테스트는 통과하는데 화면에서만 드러나는 갈래다.**
  `test_collect_market_context_overrides_sector_scores_from_market_gate` 는 `sector_scores["반도체"] == 1.2`
  를 단언해 §1.1 의 입력을 정상으로 고정한다. 그 값이 어떤 문자열로 렌더되는지는 아무도 확인하지
  않는다. `test_build_vcp_intent_context_uses_fallback_when_empty` 는 빈 문자열이 안내 문구로 바뀌는
  §1.2 의 동작을 사양으로 못 박는다. pytest 2,560건과 vitest 641건이 모두 통과하는데 사용자는 VCP
  화면에서 네 종목의 분석을 보면서 상담 패널에서 「분석된 시그널이 없다」는 답을 받는다.
  `build_system_prompt` 가 실제로 만드는 문자열 전체를 고정 입력으로 대조하는 테스트가 한 건도 없다.

  **둘째, 동시성 갈래다.** `test_history_manager_sync.py` 의 16건은 전부 단일 스레드에서 파일 서명과
  캐시 무효화를 확인한다. 두 스레드가 같은 매니저를 동시에 건드리는 검사, `_save()` 의 전체 동기화
  폴백이 어떤 행을 지우는지 확인하는 검사, `MemoryManager.add` 중간에 `_reload` 가 끼어드는 상황을
  재현하는 검사가 모두 없다. 그래서 §1.4 와 §1.5 는 고친 뒤에도 다시 무너지는 것을 막을 장치가 없다.
- 심각도: **P1**

---

## 요약

| 관점 | 발견 | 그중 P0 | P1 | P2 |
|---|---|---|---|---|
| 깨진 동작 | 5 | 3 | 2 | 0 |
| 중복 | 2 | 0 | 1 | 1 |
| 과잉 설계 | 1 (+잔존 1) | 0 | 1 | 0 |
| 비대한 파일 | 1 | 0 | 0 | 1 |
| 검증 공백 | 1 | 0 | 1 | 0 |
| **합계** | **10** | **3** | **5** | **2** |

## 이전 감사 대조

| 이전 항목 | 현재 상태 |
|---|---|
| §1.1 세션 전환 결함 | **완료** (`[CHAT-001]`, 커밋 3dce4ce). `useChatStream.ts:117-128, 269-282` 이 ref 로 판정한다 |
| §1.2 스트리밍 토큰 사용량 공백 | **완료** (`[CHAT-002]`). `chat_handlers.py:187-188` 이 이벤트를 방출한다 |
| §1.3 모든 슬래시 명령의 임시 판정 | **완료** (`[CHAT-002]`). `session_access.py:25` 가 `_EPHEMERAL_COMMANDS` 를 참조한다 |
| §1.4 의도 지시문이 종가베팅에만 적용 | **완료** (`[CHAT-002]`). `payload_service.py:102-104` 가 의도와 무관하게 붙인다 |
| §2.1 두 SQLite 캐시 모듈 중복 | **완료** (`[CHAT-003]`, `services/sqlite_ready_gate.py` 도입) |
| §2.2 파서 이중화 / §4.1 페이지 비대 | **완료** (`[CHAT-004]`). `page.tsx` 가 1,718줄에서 1,101줄로 줄고 훅 네 개로 갈렸다 |
| §3.1 죽은 프롬프트 상수와 래퍼 | **완료** (`[CHAT-005]`). 다만 `fetch_mock_data` 는 남았고 §3.1 이 밝히듯 지금은 유일한 실행 경로다 |
| §3.2 위임 믹스인과 레거시 경로 | **잔존** (위 §3.2) |
| §5.1 챗봇 화면 회귀 테스트 부재 | **완료**. `frontend/src/app/chatbot/` 에 회귀 테스트 일곱 개가 생겼다 |
| `[CHAT-028]` 메모리 부팅 적재 | **제거로 닫힘**(`[INFRA-036]`). 재등록하지 않는다 |

### 백로그 반영

`[CHAT-031]`(§1.1·§1.2·§1.3·§2.2, P0), `[CHAT-032]`(§3.1), `[CHAT-033]`(§1.4·§1.5·§5.1),
`[CHAT-034]`(§2.1), `[CHAT-035]`(§4.1)를 `docs/dev-cycle/TODO.md` 에 등록했다. §3.2 는 잔존으로만
표시하고 항목으로 올리지 않았다. `[CHAT-035]` 는 `[CHAT-033]` 이 끝난 뒤에 시작한다. 체크박스는
감사 근거에서 나온 방향이지 확정 설계가 아니며, 실제 설계는 그 항목의 라운드가 시작될 때
`superpowers:brainstorming` 이 정한다.
