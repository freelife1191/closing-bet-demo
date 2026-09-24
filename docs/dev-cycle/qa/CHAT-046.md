# [CHAT-046] 챗봇 VCP 요약의 BUY 판정이 `gpt_recommendation` 을 보지 않는다 — QA 기록

- 대상: `chatbot/signal_context.py` 의 `_vcp_verdicts`·`_is_vcp_buy`·`build_vcp_buy_recommendations_text`(Gemini·GPT 판정 모두 표기, 실패 기록 건너뜀, Perplexity 제외), `chatbot/prompts.py` 문구
- 단계(phase): 시나리오 구성 완료 | 실행 대기
- 구성 2026-09-24 11:47 | 실행 (미실행)
- 검증 기준 커밋: (첫 커밋 뒤 기입)
- 구성 근거: 설계 승인(11:43), 호출 경로는 `[CHAT-045]` 와 같다(챗봇 VCP 의도 → `build_vcp_intent_context` → `fetch_vcp_ai_analysis` → `load_vcp_ai_payload` → `build_vcp_analysis_summary_text`). 수집 행은 세 추천 칸을 모두 갖고(`engine/vcp_ai_orchestration_helpers.py:36`), 재분석이 새로 넣는 행은 추천 칸만 갖는다
- QA 엔진(engine): Claude Code. 결과는 LLM 에 넘기는 문맥 문자열이며 화면에 직접 보이지 않는다. 챗봇 전송은 실제 LLM 호출과 쿼터 소모가 따르므로 실행하지 않는다. browser_applicability: not_applicable(근거: 바뀐 값은 LLM 입력 문자열뿐이고, 그 문자열을 만드는 함수 경로 전체를 하네스로 호출한다)
- 하네스: scratchpad `chat046qa_harness.py`. 검증 기준 커밋의 `git archive` 사본을 코드로 쓰고, 빈 임시 `data` 에 수집 모양 캐시 네 파일을 만든다. 행은 KT(Gemini 실패 N/A·GPT BUY, 65점), 한화3우B(Gemini HOLD·GPT BUY, 72점), 삼성전자(Gemini HOLD·Perplexity BUY, 80점), SK하이닉스(둘 다 BUY, 90점)다. 이어 `update_vcp_ai_cache_files` 로 카카오(GPT BUY 만, 점수 없음)를 넣고 `fetch_vcp_ai_analysis`·`build_vcp_intent_context` 를 부른다. 대조는 수정 전 커밋 `f2eb1c8` 사본
- 원본 `data/`·`logs/`·3500·5501·운영 주소는 건드리지 않고, 실제 LLM·발송은 하지 않는다
- 필수 여부(required): S-1~S-3 예
- 결과: (미실행)

## 시나리오

### S-1. Gemini 가 실패하거나 관망이어도 GPT BUY 가 매수 목록에 들어간다 (핵심)
- 조작: 하네스 1회
- 기대: 머리글 「분석 5건 … 매수 추천 4건」. `- **KT**: 65점 (GPT 매수)`(Gemini 실패 기록은 표기 없음), `- **한화3우B**: 72점 (Gemini 관망 · GPT 매수)` 와 사유 「GPT-HANWHA …」, `- **카카오** (GPT 매수)`. 수정 전 사본은 KT·한화3우B·카카오가 빠지고 매수 추천 건수가 다르다
- 실제: (미실행)

### S-2. Perplexity 판정은 쓰지 않는다
- 조작: S-1 과 같은 실행
- 기대: 삼성전자가 목록에 없고 「PPLX-SAMSUNG」 문자열이 출력 어디에도 없다. 수정 전 사본에서는 Gemini HOLD 가 있어 역시 빠진다(대조로만 기록)
- 실제: (미실행)

### S-3. 두 AI 가 모두 BUY 인 행과 의도 문맥
- 조작: S-1 과 같은 실행
- 기대: `- **SK하이닉스**: 90점 (Gemini 매수 · GPT 매수)` 와 사유 「GEM-HYNIX …」. `build_vcp_intent_context` 가 「[VCP AI 분석 결과]」 뒤에 같은 요약을 담는다
- 실제: (미실행)
