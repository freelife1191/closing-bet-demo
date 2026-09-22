# [CHAT-031] 프롬프트가 싣는 시장·시그널 값과 기준일 바로잡기 — QA 시나리오

- 대상: `chatbot/prompts.py` `build_system_prompt` 의 시장·섹터 절, `chatbot/payload_service.py` `collect_market_context`,
  `chatbot/intent_detail_service.py` `build_market_gate_context`, `chatbot/signal_context.py` 의 문맥 텍스트,
  `chatbot/data_service.py` `fetch_vcp_ai_analysis`. 챗봇 화면(`/chatbot`)에서 보내는 모든 메시지의 시스템 프롬프트와 의도 문맥
- 구성 근거: `[CHAT-031]` 의 근거·QA 줄(AUDIT-CHAT 2차 §1.1~§1.3, §2.2) + 설계 승인(「시스템 프롬프트 한 곳」) + 실제 `data/`
  파일로 만든 프롬프트의 읽기 전용 하네스 출력
- 구성 2026-09-22 20:22 | 실행 2026-09-22 20:25~20:30 (1회차)
- 검증 기준 커밋: `4462816` (첫 커밋). 실행은 그 커밋과 같은 작업 트리에서 했다(코드 리뷰 회신을 기다리는 동안 실행했고,
  커밋까지 바뀐 것은 리뷰 참고 사항인 `core_data_access_mixin.py` 의 docstring 한 줄뿐)
- QA 엔진(engine): Claude Code. 사용자 진입 흐름이 챗봇 화면이므로 브라우저 실측을 필수로 두었다. 원본 챗봇으로는 전송하지
  않았다(LLM 비용과 로그가 생기는 되돌릴 수 없는 조작). 대신 `[VCP-032]` 의 격리 사본(scratchpad `jongga041-scratch`, 이번
  변경을 rsync 로 복사, `.env` 없음)에 QA 전용 진입점 `qa_flask_app.py` 를 두어 `engine.genai_client.build_genai_client` 를
  가짜 클라이언트로 바꿨다. 가짜 클라이언트는 모델이 받을 프롬프트에서 데이터 절(「## 시장 현황」「## 섹터 등락률」
  「[Market Gate 상세 분석]」「[VCP AI 분석 결과]」「[최근 뉴스]」「[종가베팅 추천 종목]」「[질의 의도 가이드]」)만 골라 답변으로
  되돌린다. 그래서 화면에 보이는 답변이 곧 모델이 받은 데이터다. gunicorn(1 worker, `SCHEDULER_ENABLED=false`,
  `GOOGLE_GENAI_USE_VERTEXAI=true`·`GOOGLE_CLOUD_PROJECT=qa-stub` 는 쿼터 가드의 「서버 키 있음」 판정용 더미, 57831)과
  Next(`API_URL` → 57831, 57821)를 띄웠다. 사본 `data/` 는 읽기만 했고(챗봇 저장소·사용량 DB 는 사본에 쓰임), 원본 `data/`·
  3500·5501·운영 주소는 건드리지 않았다. 브라우저는 gstack `browse`(HeadlessChrome), `localhost` 로 열었다. 익명 사용자
  (`usage_key=anon_…`, 무료 티어)로 네 메시지를 한 대화에서 보냈다
- 단계(phase): 시나리오 구성 완료 | 실행 완료
- 반복(iteration): 1회
- baseline 상태: 사본 자료 기준 `market_gate.json` dataset_date 2026-09-22, KOSPI 7110.759765625, 반도체 change_pct 2.93 ·
  `kr_ai_analysis.json` signal_date 2026-05-05, 시그널 4건 전부 HOLD · `jongga_v2_latest.json` 2026-09-21, 8건. 고치기 전
  같은 자료로 만든 프롬프트는 「## 섹터별 점수」 아래 「🔴 반도체: 2.93점」, 「- **KOSPI**: 7110.759765625」, 시장 의도 문맥에
  섹터가 퍼센트로 한 번 더, VCP 의도 문맥은 「현재 분석된 VCP 시그널이 없습니다」 였다(pytest RED 7건)
- 필수 여부(required): 예
- 결과: 통과 (필수 2/2, 인접 2/2)
- 증거: 아래 각 시나리오의 「실제」 줄(browse `js` 출력 원문) · 스크린샷 scratchpad `chat031-s1-sector.png` · 격리 Flask 로그의
  `[QUOTA] … stream_has_error=False` 4줄 · `pytest -q -p no:cacheprovider` 2589 통과 2 skipped(두 번, 래퍼 삭제 전후) ·
  vitest 전체는 frontend 무변경이라 `[VCP-032]` 의 exit 0 유지
- 정리(cleanup): 격리 gunicorn(57831)·Next(57821) 종료, browse 서버 정지. `qa_flask_app.py` 는 사본에만 있고 저장소에 없음.
  저장소에는 이번 항목의 파일만 남음

## 검사 대상에 관한 전제

섹터는 시스템 프롬프트의 「## 섹터 등락률 (Market Gate)」 절 한 곳에 `🟢 반도체: +2.93%` 형식(부호로 색)으로 실리고, 시장 의도
문맥 「[Market Gate 상세 분석]」 에는 색상·상태·총점·사유만 남는다. 시장 현황 제목은 「## 시장 현황 (Market Gate 기준 날짜)」
이고 지수는 소수 둘째 자리·천 단위 구분이다. VCP 의도 문맥은 「분석 N건 (기준일 X, D일 경과), 매수 추천 M건」 머리글 뒤 BUY
목록이며 M 이 0 이면 「매수 추천 종목 없음」, 분석이 하나도 없을 때만 종전 「현재 분석된 VCP 시그널이 없습니다」 다. 뉴스·종가베팅
문맥의 첫 줄은 「(기준일 X, D일 경과)」 다.

## 시나리오

### S-1. 시장 질문의 프롬프트가 섹터를 퍼센트로 한 번만 싣고 기준일을 말한다 (회귀)
- 조작: `localhost:57821/chatbot` 을 열고 「오늘 섹터 어때?」 를 보낸다.
- 기대: 답변(= 모델이 받은 데이터 절)에 「## 시장 현황 (Market Gate 기준 2026-09-22)」, 「- **KOSPI**: 7,110.76」,
  「🟢 반도체: +2.93%」, 「[Market Gate 상세 분석]」 아래 색상·상태·총점·사유. 「2.93점」·「섹터별 점수」·「섹터 동향」 없음,
  「반도체」 는 한 번만. 콘솔 오류 0건.
- 필수 여부(required): 예
- 실제: `hasMarketTitle: true` · `kospi: true`(「KOSPI: 7,110.76」) · `sector: true`(「🟢 반도체: +2.93%」) · `scoreText: false`
  · `oldSectorTitle: false` · `sectorTrend: false` · `semiCount: 1` · `marketGateDetail: true`. 답변 원문(마크다운 렌더 뒤):
  「시장 현황 (Market Gate 기준 2026-09-22) / KOSPI: 7,110.76 / KOSDAQ: 843.24 / 환율: 1,360원 / Market Gate: 🟡 YELLOW /
  섹터 등락률 (Market Gate) / 🟢 반도체: +2.93% 🟢 증권: +1.95% … 🔴 자동차: -0.57% / [Market Gate 상세 분석] 색상: YELLOW
  상태: 중립 (Neutral) 총점: 55 사유: 시장 양호 (Technical) / [질의 의도 가이드] Market Gate 상태를 중심으로 …」.
  `browse console --errors` → 「(no console errors)」. 스크린샷 `chat031-s1-sector.png`.
- 결과: 통과
- 증거: browse `js`·`console --errors` 출력 원문, 스크린샷
- 정리(cleanup): 없음

### S-2. VCP 질문의 문맥이 「분석 없음」 대신 건수·기준일·매수 추천 0건을 말한다 (회귀)
- 조작: 같은 대화에서 「VCP 매수 추천 알려줘」 를 보낸다.
- 기대: 답변에 「[VCP AI 분석 결과]」 아래 「분석 4건 (기준일 2026-05-05, 140일 경과), 매수 추천 0건」 과 「- 매수 추천 종목
  없음 (분석 결과가 전부 HOLD/SELL)」. 「현재 분석된 VCP 시그널이 없습니다」 없음.
- 필수 여부(required): 예
- 실제: `s2_vcpBlock: true` · `s2_vcpHeader: true` · `s2_noBuy: true` · `s2_oldNoSignal: false`. 답변 원문에 「[VCP AI 분석
  결과] 분석 4건 (기준일 2026-05-05, 140일 경과), 매수 추천 0건 / 매수 추천 종목 없음 (분석 결과가 전부 HOLD/SELL) / [질의
  의도 가이드] VCP 데이터에 근거해 …」.
- 결과: 통과
- 증거: browse `js` 출력 원문
- 정리(cleanup): 없음

### S-3. 종가베팅 질문의 문맥이 기준일과 경과일로 시작한다 (인접)
- 조작: 같은 대화에서 「종가베팅 추천 종목 알려줘」 를 보낸다.
- 기대: 답변에 「[종가베팅 추천 종목]」 아래 「(기준일 2026-09-21, 1일 경과)」 와 「- **삼성전기** (009150): S급」.
- 필수 여부(required): 아니오 (인접)
- 실제: `s3_block: true` · `s3_asOf: true` · `s3_first: true`. 답변 원문에 「[종가베팅 추천 종목] (기준일 2026-09-21, 1일 경과)
  / 삼성전기 (009150): S급, 점수 10점 (2026-09-21) / AI 분석: ① 뉴스/재료 분석: …」.
- 결과: 통과
- 증거: browse `js` 출력 원문
- 정리(cleanup): 없음

### S-4. 뉴스 질문의 문맥도 기준일로 시작한다 (인접)
- 조작: 같은 대화에서 「오늘 뉴스 있어?」 를 보낸다.
- 기대: 답변에 「[최근 뉴스]」 아래 「(기준일 2026-09-21, 1일 경과)」 와 `- [출처] 제목` 줄.
- 필수 여부(required): 아니오 (인접)
- 실제: `s4_block: true` · `s4_asOf: true`. 뉴스 줄은 「[한국경제TV] AI 서버에 '60만개' 들어간다…」 「[이코노뉴스] 코스피,
  1%대 상승에 7000선 회복…」 등으로 보였고, `- ` 머리표만 마크다운 렌더가 목록 기호로 바꿔 `innerText` 정규식(`- [출처]`)이
  거짓이었다(원문 자체는 `- [출처] 제목` 형식, S-3 과 같은 하네스 출력으로 확인).
- 결과: 통과
- 증거: browse `js` 출력 원문
- 정리(cleanup): 없음

## 프레임워크 관점

- `/_next/mcp` `get_compilation_issues` → `{"issues": []}` · `get_errors` → `{"configErrors": [], "sessionErrors": []}`
- 격리 Flask 로그: `INTERNAL_IDENTITY_SECRET` 비어 있음 경고와 「Scheduler is disabled」, 그리고 네 요청의 `[QUOTA]
  use_free_tier=True, stream_has_error=False` 뿐. 오류·Traceback 없음

## 이월한 발견

- 없음.
