# UI follow-up Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 승인된 FE-031·FE-028·FE-010·JONGGA-024·JONGGA-028·JONGGA-031·FE-021 7건을 구현/회귀 검증하고 실제 UI QA까지 마감한다.
**Architecture:** 기존 React 화면과 Flask 응답 추출 규칙을 고친다. 새 검색/차트 데이터 시스템이나 의존성을 추가하지 않는다. 제품 변경은 develop, 실행 검증은 git archive 기반 격리 사본에서만 한다.
**Tech Stack:** Next16.3.4/React19/Flask/pytest/Vitest, ego-browser.
**Spec:** 현재 대화에서 제안한 7건 bounded 설계 및 사용자 「승인」. 같은 승인 범위의 실행 계획은 재승인하지 않는 dev-cycle [1] 규약을 적용한다.

## Global Constraints
- 원본3500/5501/live 접속·재시작 금지. 실제 .env 값/data 내용 읽기·복사 금지.
- 실제 인증/LLM/수집/발송/설정저장/매매/삭제 금지. 가짜 계정/자료와 외부 경계 대역으로만 QA.
- root package.json은 사용자 파일: 수정/스테이징 금지. 새 의존성 및 타입 억제 금지.
- 부모가 격리 테스트와 QA 프로세스를 소유. 자식은 원본에서 테스트 실행 금지.
- source/test 작성은 소유 파일별 분리, 공용TODO/QA/git commit은 부모만. 다른 작업 변경 되돌리지 않음.
- T3 공유 리뷰: critic → ponytail → code-review+architect → deep review → 정적검사 → 첫커밋 → UltraQA → 정리 → 최종검증 → 아카이브.
- bounded 기존 화면 보완이므로 별도 architectural spec 승인 불필요. 사용자 연속 묶음 실행 요청에 맞춰 native bounded subtask를 활용하며 중복 task별 리뷰 대신 위 공유 게이트 사용.
- 명령 최대300초, 리뷰 레인 최대15분, QA 최대5회/동일실패3회. 타임아웃은 실패로 남기며 완료로 세지 않는다.

## Review Focus
1. 갱신500/네트워크/HTML/timeout이 사용자 오류로 나타나고 403 권한 동작은 보존된다(Task1).
2. 닫힌 채팅 launcher가375/900/1280에서 본문을 가리지 않고 열기/닫기가 가능하다(Task2).
3. 최신/역사 가격과 시세조회 실패가 서로 다른 기준인데 같은 문구로 위장되지 않는다(Task3).
4. AI 새판정과 오래된 nested 판정 충돌에서 카드/분석응답/사유가 같은 원천을 고른다(Task3).
5. 차트 기간 변경시 portfolio GET이 늘지 않고 이미지 로드실패도 외부링크가 유지된다(Task3/4).

### Task 1: FE-031 갱신 실패
Files: frontend/src/app/dashboard/kr/page.tsx 및 page.regression-fe-031.test.tsx, frontend/src/lib/api.ts (필요한 기존 fetchAPI export/API wrapper만).
Interfaces: 기존 krAPI.updateMarketGate와 fetchAPI 오류/timeout 계약 유지. permissionError와 일반 갱신 오류를 구분.
- [ ] 실패 테스트 먼저: updateMarketGate가 Error('갱신 실패')면 화면 alert; raw refresh 500/HTML/네트워크 및 timeout에 사용자 메시지, 재시도 성공시 해제, 403은 권한회수.
```tsx
expect(await screen.findByRole('alert')).toHaveTextContent('갱신 실패');
```
- [ ] 부모 격리 target vitest로 실패 관측(기대: 메시지 없음), 최소 구현: 일반 오류 state + 기존 alert 스타일, refresh를 기존 fetchAPI로 전달, 중복클릭/스피너 종료와 접근 가능한 갱신 이름 유지.
- [ ] 격리 target GREEN 후 전체공유 검증으로 전달. 기존 타입억제 확대 금지.

### Task 2: FE-028/FE-010 공용 헤더와 채팅
Files: frontend/src/app/components/Header.tsx, ChatWidget.tsx 및 해당 tests, 필요한 경우 dashboard/layout.tsx.
Interfaces: launcher 소유권과 isOpen 상태는 root-mounted ChatWidget에 그대로 둔다. dashboard 경로에서는 기존 단일 버튼을 fixed top-3.5 right-4 w-9 h-9로 놓고 Header를 pl-4 md:pl-6 pr-16으로 하여 오른쪽64px을 예약한다. event/context/portal 추가하지 않음. aria-expanded는 같은 isOpen에 유지. dashboard 밖에서는 기존 bottom-right 배치 유지, /chatbot에서는 현행 widget 숨김 유지. 열기/닫기버튼과 창내 닫기를 테스트하고 닫은 뒤 launcher 초점복귀를 확인한다. 말풍선과 전용timer/state를 제거한다. 채팅창 열림은 기존 의도적 overlay이며 이번 대상은 닫힌 launcher의 본문가림이다.
- [ ] 검색 input/mobile버튼/⌘K 모두 없음, named menu/settings 남음, 채팅 열기/닫기 회귀 작성. 제거만인 검색에 불필요한 구현 mirror 테스트는 추가하지 않고 기존 Header 계약 갱신.
```tsx
expect(screen.queryByRole('button', { name: '검색' })).toBeNull();
```
- [ ] 원본 baseline의 launcher 동작 검사 후 디자인 수정. 닫힌 launcher와 헤더 버튼의 좌표중첩은 브라우저로 검증한다. 말풍선 state/timer와 죽은 JSX도 함께 제거.
- [ ] 부모 격리 target GREEN. 375/900/1280 네 화면 스크롤중/끝에서 본문 가림 없음 및 채팅 open/close를 QA에 전달.

### Task 3: JONGGA-024/028/031 종가 표시 정확성
Files: frontend/src/app/dashboard/kr/closing-bet/page.tsx, displayHelpers.ts 및 displayHelpers.test.ts, page.regression-jongga-followup.test.tsx; app/routes/kr_market_jongga_ai_payload_helpers.py, kr_market_jongga_reanalysis_helpers.py, kr_market_jongga_normalize_helpers.py 및 tests/app/test_jongga_followup_contract.py; BuyStockModal.tsx/tests 필요시.
Interfaces: AI 정본 top-level ai_evaluation → score.ai_evaluation → score_details.ai_evaluation → legacy score.llm_reason. 후보가 비공백 문자열이면 기존호환 {action:HOLD,reason:문자열,confidence:null}로 선택한다. 객체는 BUY/HOLD/SELL action(대소문자무시) 또는 비공백 문자열 reason 중 하나가 있을 때 유효하다. 빈객체/배열/숫자/null/공백문자열/invalid-action-only/confidence-only는 건너뛴다. reason이 있되 action이 invalid면 HOLD로 표현한다. reason 내용 자체에 placeholder 마법문자열 판정을 도입하지 않는다. action-only 객체는 선택하고 기존 llm_reason으로 사유를 보완할 수 있다. confidence0은 값없음과 구분한다. TS displayHelpers에 동일 후보 선택함수를 두고 score_details 타입의 ai_evaluation을 unknown으로 수용해 검사한다. 사유는 선택한 판정 reason 우선, legacy llm_reason 호환. confidence0 보존, 입력객체 수정 금지(추출기).
- [ ] 상충된 새HOLD/옛BUY, reason-only legacy, 빈/malformed 평가, confidence0 회귀 작성.
```python
assert _extract_jongga_ai_evaluation({'ai_evaluation': {'action':'HOLD','reason':'new'}, 'score': {'ai_evaluation': {'action':'BUY','reason':'old'}}})['reason'] == 'new'
```
- [ ] 부모 target RED 확인 후 추출/카드/본문 동일순서 적용; 재분석 결과를 fixture로 주입하여 UI와 실제 Python 변환을 함께 대조한다. 실제 LLM 호출 안 함.
- [ ] 고정 polyline 장식 제거, 등락률 숫자/실제 확대 차트 진입 보존. 확대 이미지는700px 원본폭으로 가로스크롤 가능, 키보드초점/설명과 실패 외부링크 유지. 불필요한 시계열 조회 추가 안 함.
- [ ] 가격 출처 응답/정규화 추적. 카드 신호일 종가는 entry_price+signal_date로 일치시키며 latest current_price는 신호일 가격이라고 부르지 않음. 매수모달 성공/실패 문구는 실제 API 응답의 출처를 보수적으로 표현(조회 성공이 거래소 실시간성 보장은 아님). 자료파일 재계산 안 함.
- [ ] 부모 Python/Vitest target GREEN, browser 최신/역사·시세성공/실패·AI충돌·차트스크롤/실패 행 준비.

### Task 4: FE-021 기간 조회 회귀
Files: frontend/src/app/components/PaperTradingModal.regression-fe-021.test.tsx. 기존 PaperTradingModal.test.tsx는 차트 컴포넌트를 mock하므로 별도파일에서 실제 PaperTradingAssetChart를 렌더하고 네트워크와 canvas 라이브러리만 대역 처리한다.
Interfaces: 현행 기간버튼은 자산이력만 갱신. 제품 코드 변경은 실제 결함 재현시에만.
- [ ] 초기 portfolio 조회수 저장→3개월→asset days90 요청 추가/portfolio 수 그대로→1개월도 동일 테스트.
```tsx
const before = vi.mocked(paperTradingAPI.getPortfolio).mock.calls.length;
fireEvent.click(screen.getByRole('button', { name: '3개월' }));
await waitFor(() => expect(paperTradingAPI.getAssetHistory).toHaveBeenCalledWith(90));
expect(paperTradingAPI.getPortfolio).toHaveBeenCalledTimes(before);
```
- [ ] baseline GREEN이면 이미 해소된 동작임을 기록; 회귀 테스트 실패가 있으면 원인확인 후 범위내 수정.

### Task 5: 공유 검증과 마감
- [ ] 부모 격리 사본에 허용파일만 sync. 소스SHA와 base31a2d93, root package SHA 보존.
- [ ] pytest/Vitest 전체, type-check/lint/test:build 실행 및 exit/log 보존. RED와 harness오류를 GREEN으로 덮어쓰지 않음.
- [ ] ponytail→code-review+architect→deep review, 파일별SHA와 판정원문 보존. 변경후 영향 레인 재검토.
- [ ] UltraQA 행렬을 qa/batch-ui-followup-2026-09-20.md와7개wrapper에 작성, allowed path staging→diff check exit0 확인후 첫커밋. TODO 유지.
- [ ] 기존 ui-batch fixture/gateway를 새 evidence/scratch 경로로 복제·수정. 모든 API는 합성서비스. JONGGA028/031은 실제 Python 변환기와 합성 입력을 연결하여 UI대역만의 검증과 구분.
- [ ] ego-browser 한 TaskSpace, 실제앱 화면으로 행렬실행. screenshot 직접열람·요청로그·Next오류확인.
- [ ] 소유PID명령/cwd 대조후 종료, scratch제거, task.finish({keep:[]}) 정확히1회. 원본파일 보존대조.
- [ ] 독립 최종검증 후 통과한7건만 archive/월별통계갱신 및 TODO제거 커밋. 미통과면 항목유지.

## 검토 반영 / 정확한 검증 경로
- critic initial REJECT: root/widget 경계·AI유효성·QA매핑·읽기목록 누락. 위 Task2/3 계약을 구체화함. 원문은 plan-critic-initial.md 보존.
- 사전문서: frontend/AGENTS.md, frontend-skills.md, Next 번들 05-server-and-client-components.md, 06-fetching-data.md, 07-mutating-data.md, 10-error-handling.md. layout 수정시02-project-structure.md/03-layouts-and-pages.md. React effects는 vercel-react-best-practices; Header/Widget의 소유권은 보존하므로 새 composition 경계 설계는 없음.
- 공유보고서 docs/dev-cycle/qa/batch-ui-followup-2026-09-20.md. 개별wrapper docs/dev-cycle/qa/FE-031.md(R1,R2,S1), FE-028.md(H1,S1), FE-010.md(H1,H2,S1), JONGGA-024.md(J1,J2,S1), JONGGA-028.md(A1,A2,S1), JONGGA-031.md(P1,S1), FE-021.md(P2,S1).
- 격리 Next57721 /_next/mcp get_compilation_issues/get_errors와 browser screenshot/요청로그로 오류판정. 실제목록에서 도구확인후 호출.
- 각 ID는 매핑된 모든 필수행과 공유정적검사/리뷰/정리를 충족해야 마감. 부분실패는 해당ID 유지; 공유S1실패는 전부유지. 과거자료처리·외부호출은 금지.

## 통합 회귀에서 확인한 기존 호환 제약
- JONGGA004/016은 ai_evaluation이 전혀 없고 score.llm_reason만 있는 카드에 추천을 새로 만들지 않도록 AI분석대기/미산출을 보장한다. 이 기존회귀는 삭제/약화하지 않는다. Task3의 frontend helper는 유효한 세후보가 전부없으면 null, body만 legacy사유를 표시한다. 후보가있을때의 사유보완과명시판정 top→score→details 일치는 유지한다. Python의기존legacy-onlyHOLD응답호환은유지한다. 이차이는기존자료표시의호환경계이며신규LLM판정추정은아니다.

## 독립 리뷰 보완 범위
- Python AI 출력은 원본candidate전체복사대신 action/문자reason/finite number·문자·null confidence/문자model만조립한다. bool·NaN·Inf·JS숫자범위초과정수는전달하지않는다. TS도같은경계.
- BuyStockModal 시세조회는기존fetchAPI10초timeout·HTTP오류처리사용. positive finite number만사용하고실패·값없음·timeout은저장가격안내. 실제주문/잔고정책은변경없다.
- dashboard밖launcher는원래z120보존, dashboardheaderlauncher만z100. panel과launcher비중첩의기하관계를무시한초기리뷰원인주장은실측과후속판정으로정정한다.

심층 리뷰 보완: frontend/src/lib/api.ts와 api.body-timeout.test.ts. 실제 Response/ReadableStream을 사용해 headers 즉시·body 정체의200/500 응답에서 제한 시간이 유지되는지 검증한다. 조기 clearTimeout 제거 및 return await response.json()으로 공용10초/개별120초의 전체 응답 수신 경계를 보장한다.
