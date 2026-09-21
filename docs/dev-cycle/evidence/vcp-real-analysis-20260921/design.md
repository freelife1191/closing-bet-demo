# VCP 실제 분석·구형 템플릿 경계 설계

VCP-022 나머지라운드, brainstorming architectural/T3. 사용자2026-09-21 연속작업·승인판단위임에따라리더가범위를결정한다.
기존confidence부분은95cab19/UltraQA8/8로완료했으므로반복구현하지않는다.

## 사실과 완료 범위

현재 common 전체갱신은 create_signals_log의실제VCP분석 뒤에 KrAiAnalyzer의무작위모의분석을저장할수있다. 단독CLI/user-key경로도같은mock생산자를사용한다.
과거20260211의실제실행명령/순서는기록없이확정할수없다. 당시행위자귀속을지어내지않는다.
이비상용프로젝트의완료범위는 재발가능한생산/덮어쓰기경로제거,원본보존,구형템플릿응답차단,실제VCP실행검증으로확정한다.
특정과거요청의포렌식귀속은완료조건에서제외한설계결정이며,확정했다고체크하지않는다. 실패한QA행을나중에optional로내리는것이아니다.

## 대안과 선택

모든marker없는과거분석을숨기는방식은정상역사분석도대거잃는다. 새provenance스키마를전경로에추가하는대신기존구형생산자의정확한출력형식을제외한다.
단어·BUY·확신도만으로mock이라고추정하지않는다. GPT의정확한고정템플릿문장과Gemini의전체섹션/2driver/risk/완성hypothesis가정적템플릿과일치하는경우만신뢰할분석사유로보지않는다.
이는출력형식정책이지생성주체증명이아니다. 같은일반용어를쓴다른정상사유는유지한다.
원본data파일은읽거나수정하지않고,API응답의캐시복사본에서만제외한다. CSV병합·원시AI응답모두같은규칙을쓴다.

## 실행 설계

- GeminiStrategy/GPTStrategy의random구현은비활성None으로바꾼다. 가용성도false이며구형호환심볼은유지한다.
- 관리자 AI Analysis 단계는선택한날짜CSV→기존build_ai_batch_payload→기존VCPMultiAIAnalyzer/run_async_analyzer_batch를쓴다.
- 전체갱신에VCP Signals가함께있으면그단계가이미분석했으므로같은날짜저장분석을검증·재사용하고추가LLM호출/덮어쓰기하지않는다.
- 단독분석은새유효provider결과만기존dated캐시에병합한다. None/실패/무대상은기존자료를지우지않는다. 과거날짜분석은최신파일을건드리지않는다. 날짜는파일접근전에엄격검증한다.
- scripts.create_kr_ai_analysis는같은관리자단계의얇은진입점이된다. CLI all에서create_signals_log뒤의중복분석호출을제거한다.
- 사용자가현재UI에서사용하지않는구형 /reanalyze/gemini와create_kr_ai_analysis_with_key는종료응답을반환한다. 개인키를공용키로조용히바꾸거나지원하지않는경로에서쿼터를차감하지않는다. 현재VCP화면의실패AI재분석/API는유지한다.
- signal_tracker_ai_helpers는VCP판정의직접생산경로이므로dev-cycle위험목록에넣는다. 코드재작성은필요없으며기존builder재사용이선택근거다.

## 경계와 검증

원본.env/data/logs/3500/5501/live/실제LLM·수집·계정·거래·삭제금지. 기존NumPy1.26.4/pykrx1.2.3의비밀없는소유scratch에서검증한다.
TDD: 구형생산차단·정확한템플릿만차단·캐시불변·실제analyzer입력·부분실패보존·과거/최신분리·중복호출0·종료API쿼터0.
전체pytest/Vitest/type/lint/build, ponytail→code-review/architect→T3심층/보안리뷰, UltraQA App+ego 실제VCP모달/원시fallback 검증.
정상legacy자료유지와실패후복구를함께확인한다. 브라우저는같은Space20재사용,마지막에finish1회.
