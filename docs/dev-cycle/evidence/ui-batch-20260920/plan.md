# 공용 UI와 종목 화면 Implementation Plan

> For agentic workers: superpowers:subagent-driven-development. 저장소 dev-cycle의 리뷰·QA·커밋 순서를 따른다. 독립 파일은 소유권을 나눠 병렬화하고 공유 페이지는 순차 통합한다.

**Goal:** 승인된 FE-032·030·036·037·017 다음 JONGGA-023·026·029·FE-016을 두 묶음으로 완료.
**Architecture:** 기존 ModalShell/Tooltip/settingsEnv를 보완하고 종가/VCP 화면에서 재사용한다. 새 의존성 없음. 기존 업무 API/거래/인증/시크릿 정책 불변.
**Tech Stack:** Next16.3.4/React19, Vitest, pytest, ego-browser.
**Spec:** 2026-09-20 직전 대화의 9건 설계표와 사용자 「승인」. 상세 요구사항은 TODO의 해당9절. 동일 범위 보완에 재승인 없음.

## Global Constraints
- 두 묶음 각각 T3 보수적 공유 검토. 실제 .env 값·원본 data 내용을 읽거나 변경하지 않는다. 기존 root package.json 보존.
- 원본3500/5501 및 live HTTP·재시작 금지. 검사/QA는 git archive 임시 사본 + 합성 응답, 외부 네트워크·원본 쓰기 sandbox 차단.
- 실제 인증/login/logout/설정저장/알림/LLM/수집/거래/삭제 금지. 브라우저 전용 로컬 fixture만 사용하며 인증 경로도 시작부터 막는다.
- 부모가 검사와 커밋/QA를 소유. 구현 에이전트는 코드/테스트만 변경, 다른 에이전트 변경을 되돌리지 않는다. 스킬/lintrule 억제 변경 금지.
- Next 번들 02/03/05, composition-patterns·react-best-practices를 적용. 375×812/1280×720 및 경계폭 실측. 명령300초, 리뷰15분, QA5회/동일실패3회 한도.

### Task 1: 설정 입력과 공용 이름 (FE-032, FE-017 일부)
Files: components/SettingsModal.tsx, settingsEnv.ts, Header.tsx, Sidebar.tsx, ChatWidget.tsx 및 인접 회귀.
- [x] 테스트에서 masked token이 input value가 아닌 고정placeholder인지, 새값 편집·미편집 보존 payload인지 RED 확인.
```ts
expect(screen.getByLabelText('TELEGRAM_BOT_TOKEN')).toHaveValue('');
expect(screen.getByLabelText('TELEGRAM_BOT_TOKEN')).toHaveAttribute('placeholder', '저장되어 있습니다. 바꾸려면 새 값을 입력하세요');
```
- [x] apiKeyFieldProps를 저장된 환경값용 이름으로 확장하여 모든 마스킹 가능 텍스트필드에 적용. 서버 PLAIN_ENV_KEYS/AI_PROVIDER는 이미 정상: 새 마스킹 정책을 만들지 않는다. 보조 설명보다 기존 라벨명 유지·id/htmlFor 일치를 우선한다.
- [x] 삭제 아이콘·헤더 홈/아이콘·Sidebar 충전 팝오버·위젯 열기에 구체적인 이름. 데이터 저장 동작/권한 유지.
- [x] 부모 targeted GREEN과 masked/empty/new/비관리자 회귀 확인.

### Task 2: 모달 수명주기 (FE-030·036)
Files: components/Modal.tsx, ConfirmationModal.tsx, BuyStockModal.tsx, SellStockModal.tsx, PaperTradingModal.tsx, StockTradeHistoryModal.tsx 및 인접 회귀.
Interface: 기존 ModalShell props 유지, role?: 'dialog'|'alertdialog', initialFocusRef?: React.RefObject<HTMLElement|null> 지원. portal의 각 최상단 소유 컨테이너만 활성화한다. 화면 담당자는 이 interface로 호출.
- [x] 모달 진입 초점/Tab·ShiftTab 순환/Escape 한 겹/trigger 복귀/중첩 닫기/StrictMode 정리 RED.
```ts
expect(screen.getByRole('alertdialog')).toContainElement(document.activeElement as HTMLElement);
expect(screen.getByRole('button', {name:'취소'})).toHaveFocus();
```
- [x] 기존 셸을 body portal로 배치; 열린 최상단만 focus 활성, 배경 inert와 body overflow 이전값 보존/복원. 닫힌 trigger가 제거되었으면 안전한 fallback. React 재렌더 onClose 변경으로 초기초점 재설정 금지.
- [x] Confirmation은 alertdialog/취소초점. 중첩순서·오버레이 클릭은 맨위만 처리. 고정32px오프셋은 portal 이후 실측으로 원인/결과 대조.
- [x] 존재하지 않는 animate-in/fade-in/zoom-in/slide-in/animate-scale-in을 기존 animate-fade-in 또는 기존transition으로 정리. reduced motion 존중. 회귀 GREEN.

### Task 3: Tooltip 경계 (FE-037)
Files: components/Tooltip.tsx 및 Tooltip.test.tsx.
Interface: 기존 children/content/size/align/position/as 유지. 새 의존성 없이 열린 tooltip만 실측·배치. 모달 안 tooltip은 확정한 [data-modal-layer] 비클리핑 host를 사용하여 inert와충돌하지 않는다.
- [x] 위 공간부족→아래, 좌우클램프, 스크롤/resize 재배치, Escape/언마운트 정리 RED.
```ts
expect(popup.getBoundingClientRect().left).toBeGreaterThanOrEqual(8);
```
- [x] 위치계산은 viewport 및 clipping을 고려. screen보다 긴 내용은 화면 내 maxheight와 읽을 수 있는 스크롤 제공. hover/focus로 열고 popup으로 이동해도 유지, 설명접근성 연결; 모든 wrapper에 불필요한 Tab stop 추가 금지.
- [x] 부모 unit GREEN, 실제375/modal첫줄/edge hover 실측.

### Task 4: 화면 통합 (FE-030·036·017 나머지)
Files: dashboard/kr/closing-bet/page.tsx, dashboard/kr/vcp/page.tsx, dashboard/data-status/page.tsx 및 관련 회귀.
- [x] 별도 상세/차트 오버레이를 Task2 ModalShell로 옮겨 기존 크기/내용/닫기 유지; 제목id·닫기이름·Escape 확보. page에 중복Escape핸들러 남기지 않는다.
- [x] FE017 TODO 지정 버튼/선택상자/링크 이름, disabled 매수 사유를 터치·키보드에서도 읽히는 안내로 제공. 실제 매수 트리거 금지.
- [x] 모달 여섯종·상세모달·중첩·tab/escape/복귀·배경scroll·32px여백 시나리오 unit/브라우저 확인.
- [x] 1차5건: ponytail→code-review+architect→T3review; pytest/Vitest/lint/build/typecheck, 첫구현commit, UltraQA행렬, ego-browser·NextMCP, 수정영향 재검수·정리·아카이브.

### Task 5: 종목 표시 (JONGGA-023·026·029·FE-016)
Files: closing-bet/page.tsx, closing-bet/displayHelpers.ts, vcp/page.tsx, kr/formatMarketAmount.ts 및 인접 회귀.
- [x] 빈자료와 필터0구분, 엔진선정수와 표시수구분, themes는 전체signals기준, 신호기준시점 tooltip 일치 RED.
- [x] 1조2400억/1조2600억 구분, 음수/0/억반올림 경계 테스트. 두 기존함수를 공용 helper로 합침; 조단위 억 표시·그이하 기존반올림·음수절대값기준 대칭. noData 표기는 호출부 계약 보존.
```ts
expect(formatMarketAmount(1_240_000_000_000)).toBe('1조 2400억');
expect(formatMarketAmount(3_276_004_650)).toBe('33억');
```
- [x] HOLD확신도 라벨 nowrap와 배지행 wrap,375 VCP과거날짜 버튼/종가필터 줄 wrap 및날짜 최소폭. 지표/신호계산 불변.
- [x] 2차4건: 1차와 동일 리뷰/정적/QA/마감. 375,1250,1280,1285,1440폭 합성실측, 초기화/필터0/전체테마 보존. 원본과소유런타임 정리증거 확인후 TODO제거.

## 판정과 순서
계획 critic OKAY 전 구현 금지. Task1/2/3은 공유파일이 없어 병렬, Task4는 Task2 interface확정후 단독 page 소유. Task5는 1차 검증/완료 후 같은page를 넘겨 받는다. 원본 API 오류에 대한 별도 사용자 보고는 발생주소가 미확정이며 이 승인범위에 임의로 넣지 않는다.

## Critic 보완 및 사용자 지시 우선순위
1. 항목별 qa/FE-032.md, FE-030.md, FE-036.md, FE-037.md, FE-017.md, JONGGA-023.md, JONGGA-026.md, JONGGA-029.md, FE-016.md를 작성하여 공유보고서와 각 필수행(U1/U2/U9; U3/U4/U5/U7/U9; U7/U9; U6/U9; U8/U9; D1/U9; D2/U9; D3/U9; D3/U8/U9 순)을 연결한다. iteration/cleanup/판정을 ID별명시. 공통gate 실패시 관련 ID 전부유지, 독립항목만완료가능하며 현재필수실패를optional로낮추지 않는다.
2. portal 계약 확정: ModalShell은 body 직접자식인 `[data-modal-layer]` host를만들고 `data-modal-active="true"`를 최상단에만둔다. host는 전체화면fixed이며 overflow visible, dialog card만 scroll/clip. Tooltip은 trigger.closest('[data-modal-layer]')를 portal target으로 사용하고 없으면body. 좌표는fixed viewport기준; modal host에는transform/filter를두지않는다. tooltip이 속한 비활성모달은 열림을유지하지 않는다. 이계약을두실행자에게동일하게전달하고파일별병렬작성한뒤통합검증한다.
3. FE032 security-review 추가. 실제.env읽지않고 git ls-files .env*와tracked파일diff,합성sentinel DOM/로그노출·클라이언트공개번들검사를한다. 기존마스크응답/비편집payload보존은합성unit로검증. 민감값placeholder부분노출금지.
4. driver 지적 미채택: 사용자가 2026-09-18 명시적으로 브라우저는ego-browser로진행하도록지시했고 이번9건설계도ego로승인했다. 사용자지시는스킬기본값에우선하므로agent-browser로되돌리지않는다. 같은DOM/이미지/요청/콘솔/NextMCP증거를ego로수집한다.
5. Header/ChatWidget의이미있는이름은유지하고회귀대조만한다. disabled매수에는항상보이는구체적사유텍스트를aria-describedby로연결하여터치에서hover없이읽게한다. 애니메이션은TODO대상모달들과Task4별도상세/차트모달에남은죽은클래스만정리하고다른앱영역을임의확장하지않는다.

브라우저정적자산경계: 제품/테스트서버외부네트워크차단유지. 실제화면이요청하는cdnjs FontAwesome와ssl.pstatic.net의종목차트이미지는읽기전용정적자산으로취급하며, 그이미지시장수치를합성API검증결과로주장하지않는다. 모든제품API/인증은57620gateway를통해합성서버만사용.

최종: 필수12/12·정리·독립verifier PASS/APPROVE 후9개TODO를아카이브했다. 잔여29건(P1 8/P2 21).
