# AUDIT-FE — 프론트엔드 공통 감사

**감사 일자**: 2026-09-01
**감사 범위**: `frontend/src/app/components/`, `frontend/src/lib/`, `frontend/src/hooks/`,
`frontend/src/utils/`, 그리고 어느 기능 카테고리에도 속하지 않는 앱 셸
(`frontend/src/app/layout.tsx`, `page.tsx`, `error.tsx`, `not-found.tsx`, `loading.tsx`,
`frontend/src/app/dashboard/layout.tsx`, `error.tsx`, `loading.tsx`).
참고로만 읽은 경로는 `frontend/tests/`, `frontend/next.config.js`, `frontend/package.json` 입니다.
**읽은 파일 수**: 담당 경로 소스 30개 / 약 6,808줄 (설정과 테스트 5개를 추가로 참조)

**범위에서 제외한 경로**: `frontend/src/app/chatbot/`(챗봇),
`frontend/src/app/dashboard/kr/closing-bet/`(종가베팅), `frontend/src/app/dashboard/kr/vcp/`(VCP)
는 `archive-format.md` §2 표에서 다른 카테고리에 배정되어 있으므로 감사하지 않았습니다.
`frontend/src/app/dashboard/kr/page.tsx` 와 `frontend/src/app/dashboard/kr/cumulative/`,
`frontend/src/app/dashboard/data-status/` 는 §2 표의 어느 행에도 배정되어 있지 않습니다.
이 세 경로는 이번 감사에서 다루지 않았으므로 담당자를 정하는 판단이 별도로 필요합니다.

**실측 정정 한 가지**: 착수 지시에는 49개 파일 가운데 26개에 `'use client'` 가 있다고
적혀 있었으나, 파일 첫 줄의 지시문을 기준으로 세면 25개입니다.
`frontend/src/app/not-found.tsx` 는 5행 주석에 `no 'use client' directive needed` 라는
문구가 들어 있어서 문자열 검색에 잡혔을 뿐, 실제로는 서버 컴포넌트입니다.

---

## 1. 깨진 동작

### 1.1 모의투자 매수와 매도가 실패해도 완료로 표시된다

- 위치: `frontend/src/lib/api.ts:397-413`, `frontend/src/app/components/PaperTradingModal.tsx:579-599`
- 증상: 백엔드가 주문을 거절해도 사용자에게 `"{종목명} {수량}주 매수 완료"` 경고창이
  뜨고 주문 모달이 닫힙니다. 잔고가 그대로인 것을 보고서야 실패를 알 수 있습니다.
- 원인: `paperTradingAPI.buy` 와 `sell` 은 `fetchAPI` 를 쓰지 않고 raw `fetch` 를 호출한 뒤
  `response.ok` 를 확인하지 않고 곧바로 `response.json()` 을 반환합니다. 반환 타입인
  `TradeResponse` 에 `status: 'success' | 'error'` 필드가 선언되어 있는데도
  `handleBuySubmit` 과 `handleSellSubmit` 은 그 필드를 읽지 않습니다. 두 핸들러는
  `try` 블록이 예외 없이 끝났다는 사실만으로 성공 경고창을 띄우고 `true` 를 반환합니다.
  같은 파일의 `reset`(415행), `deposit`(421행), `getTradeHistory`(431행),
  `getAssetHistory`(439행) 는 `res.ok` 를 확인하고 예외를 던지므로, 실패가 드러나지 않는
  것은 매수와 매도 두 경로에 한정됩니다.
- 영향: 예수금 부족, 보유 수량 초과, 존재하지 않는 종목 같은 정상적인 거절이 모두
  성공으로 보입니다. `BuyStockModal.tsx:82` 와 `SellStockModal.tsx:49` 의
  `if (success) onClose()` 도 항상 참이 되어 입력 화면이 닫힙니다.
- 우선순위: `P0`

### 1.2 매수 수수료와 매도 세금이 프론트엔드에만 존재해 실제 정산액과 어긋난다

- 위치: `frontend/src/app/components/BuyStockModal.tsx:69-70`,
  `frontend/src/app/components/SellStockModal.tsx:37-39`
- 증상: 매수 화면은 `총 결제 예상 금액` 에 수수료 0.015% 를 더해서 보여 주고, 매도 화면은
  `정산 예상 금액` 에서 수수료 0.015% 와 세금 0.2% 를 빼서 보여 줍니다. 그러나 실제로
  차감되거나 입금되는 금액은 `가격 × 수량` 그대로입니다.
- 원인: 백엔드에는 수수료와 세금 개념이 아예 없습니다. `services/` 와 `app/routes/`
  전체에서 `commission`, `수수료`, `0.00015` 를 검색해도 결과가 하나도 나오지 않습니다.
  잔고 갱신은 `services/paper_trading_trade_account_mixin.py:45` 의
  `UPDATE balance SET cash = cash - ?` 한 문장이며, 여기에 전달되는 금액에는 수수료가
  섞이지 않습니다.
- 영향: 1,000만 원어치를 매도하면 화면은 9,978,000원을 받는다고 안내하지만 잔고는
  1,000만 원이 늘어납니다. 매수 화면의 `가능: N주` 표기(`BuyStockModal.tsx:198`)와
  `최대` 버튼(`BuyStockModal.tsx:92-103`)도 같은 계수 `1.00015` 를 쓰기 때문에 매수
  가능 수량이 실제보다 적게 나옵니다. 수수료율 0.00015 는 한 파일 안에서만
  69행, 96행, 100행, 108행, 113행, 198행 여섯 자리에 흩어져 있습니다.
- 우선순위: `P0`

### 1.3 사이드바 로그아웃 버튼이 세션을 끊지 않는다

- 위치: `frontend/src/app/components/Sidebar.tsx:265-279`
- 증상: 사용자 메뉴에서 `로그아웃` 을 누르면 `로그아웃 되었습니다.` 라는 성공 모달이
  뜨지만 실제로는 로그인 상태가 유지됩니다.
- 원인: 이 버튼의 `onClick` 은 `setAlertModal({ type: 'success', title: '로그아웃',
  content: '로그아웃 되었습니다.' })` 만 호출하고 `next-auth` 의 `signOut` 을 부르지
  않습니다. 같은 저장소에서 `signOut` 을 실제로 호출하는 곳은
  `SettingsModal.tsx:153` 과 `SettingsModal.tsx:248` 두 자리뿐입니다.
- 영향: 사용자가 로그아웃했다고 믿는 상태에서 세션 쿠키가 그대로 남습니다. 공용 기기에서
  다음 사용자가 이전 사용자의 세션을 이어받게 됩니다. 관리자 계정이라면
  `useAdmin` 이 계속 참을 반환하므로 관리자 전용 화면도 열린 채로 남습니다.
- 우선순위: `P0`

### 1.4 Perplexity API 키 입력값이 저장되지 않은 채로 다시 읽힌다

- 위치: `frontend/src/app/components/SettingsModal.tsx:108-119`, `130-140`
- 증상: 설정 화면에서 Perplexity 키를 입력하고 저장한 뒤 설정을 다시 열면 입력 칸이
  비어 있습니다. OpenAI 키는 같은 상황에서 값이 유지됩니다.
- 원인: `fetchEnvVars` 는 108행에서 `OPENAI_API_KEY` 와 `PERPLEXITY_API_KEY` 두 키를
  모두 마스킹 대상으로 삼아 서버 응답에서 지우고, 116행과 119행에서 두 키를 모두
  `localStorage` 에서 복원하려 합니다. 그런데 값을 `localStorage` 에 쓰는
  `handleEnvChange` 는 133행에서 `key === 'OPENAI_API_KEY'` 일 때만 저장합니다.
  읽는 쪽은 두 키를 대칭으로 다루는데 쓰는 쪽은 한 키만 다루므로,
  Perplexity 키는 복원할 원본이 존재하지 않습니다.
- 영향: 서버에는 저장되어 있으나 화면에는 빈칸으로 보이므로, 사용자는 키가 사라졌다고
  판단하고 다시 입력합니다.
- 우선순위: `P1`

### 1.5 문서 언어가 영어로 선언되어 있고 아이콘 전체가 외부 CDN 한 곳에 묶여 있다

- 위치: `frontend/src/app/layout.tsx:18`, `frontend/src/app/layout.tsx:20-23`
- 증상: 화면의 모든 문구가 한국어인데 루트 요소는 `<html lang="en">` 입니다. 또한
  Font Awesome 스타일시트를 `cdnjs.cloudflare.com` 에서 `<link>` 로 직접 불러옵니다.
- 원인: `layout.tsx` 가 초기 스캐폴딩 값을 그대로 두고 있습니다.
- 영향: 화면 낭독기가 한국어 문장을 영어 음성으로 읽고, 브라우저가 불필요한 번역을
  제안합니다. CDN 쪽 장애가 나면 저장소 전역에서 쓰는 `<i className="fas ...">` 아이콘이
  한꺼번에 사라지므로, 버튼 다수가 빈 사각형으로 보입니다.
- 우선순위: `P2`

## 2. 중복

### 2.1 `fetchAPI` 가 있는데도 열한 개 함수가 오류 처리를 따로 구현한다

- 위치: `frontend/src/lib/api.ts:9-40` (`fetchAPI`) 대 같은 파일 181, 195, 212, 229, 248,
  397, 406, 415, 421, 431, 439행
- 증상: 타임아웃과 상태 코드 처리가 함수마다 다릅니다. `fetchAPI` 는 10초 타임아웃,
  `AbortError` 변환, `error.status` 와 `error.data` 부착을 제공합니다. 그러나
  `runScreener` 를 비롯한 다섯 개 `krAPI` 함수와 여섯 개 `paperTradingAPI` 함수는
  raw `fetch` 를 쓰면서 각자 다른 방식으로 실패를 다룹니다. `runVCPScreener` 만
  409 상태를 따로 구분하고(202행), `updateMarketGate` 만 `error.error` 를 읽으며(256행),
  §1.1 에서 본 `buy` 와 `sell` 은 상태를 아예 확인하지 않습니다.
- 영향: 새 엔드포인트를 붙일 때마다 어느 방식을 따를지 매번 결정해야 하고, 실제로
  §1.1 처럼 한 곳만 확인이 빠져도 드러나지 않습니다. 타임아웃 역시 `fetchAPI` 를 거치는
  호출에만 걸리므로, 응답이 없는 주문 요청은 무한정 기다립니다.
- 우선순위: `P1`

### 2.2 모달 셸이 다섯 벌 있고 접근성 처리가 제각각이다

- 위치: `frontend/src/app/components/Modal.tsx:39-76`,
  `ConfirmationModal.tsx:26-63`, `BuyStockModal.tsx:134-136`,
  `SellStockModal.tsx:70-72`, `PaperTradingModal.tsx:608-610`
- 증상: `fixed inset-0` 오버레이와 배경 클릭 닫기, 카드 컨테이너를 그리는 코드가 다섯 벌
  있습니다. 그런데 갖춘 기능이 서로 다릅니다. `Modal.tsx` 는 Escape 키 처리(28-35행)와
  `role="dialog"`, `aria-modal`, `aria-labelledby`(46-48행)를 모두 갖췄고,
  `PaperTradingModal` 과 `StockTradeHistoryModal` 은 각자 같은 처리를 따로 구현했습니다
  (`PaperTradingModal.tsx:204-216`, `StockTradeHistoryModal.tsx:102-107`).
  반면 `BuyStockModal` 과 `SellStockModal` 은 Escape 키도 `role="dialog"` 도 없습니다.
  `ConfirmationModal` 은 `role` 과 `aria-modal` 은 있으나 Escape 키가 없습니다.
- 영향: 주문 입력 화면에서 Escape 키가 듣지 않고, 화면 낭독기가 두 주문 모달을 대화상자로
  인식하지 못합니다. 접근성을 한 번 더 손볼 때 다섯 자리를 모두 찾아야 합니다.
- 우선순위: `P1`

### 2.3 익명 세션 ID 발급과 사용량 조회가 세 곳에 흩어져 있다

- 위치: `frontend/src/app/components/Sidebar.tsx:59-63`,
  `frontend/src/app/components/ChatWidget.tsx:237-242`,
  `frontend/src/app/chatbot/page.tsx:455-463`
- 증상: `localStorage` 의 `browser_session_id` 를 읽고 없으면
  `'anon_' + crypto.randomUUID()` 로 만들어 저장하는 코드가 세 벌 있습니다.
  사용량 조회도 `Sidebar.tsx:66` 과 `SettingsModal.tsx:49` 두 곳에서 각각
  `/api/kr/user/quota` 를 부릅니다.
- 원인: 공용 헬퍼를 두지 않고 필요한 자리마다 직접 작성했습니다. 그 결과 이스케이프
  처리도 갈립니다. `useAdmin.ts:35` 는 이메일에 `encodeURIComponent` 를 적용하는데
  `Sidebar.tsx:66` 과 `SettingsModal.tsx:49` 는 적용하지 않습니다.
- 영향: `+` 가 들어간 이메일 주소로 로그인하면 사용량 조회 두 곳만 잘못된 값을
  질의합니다. 세 번째 사본은 챗봇 카테고리 소관이므로, 통합하려면 그쪽과 경계를
  맞춰야 합니다.
- 우선순위: `P1`

## 3. 과잉 설계

### 3.1 `secureStorage.ts` 는 호출자가 없고, 정작 실제 키는 평문으로 저장된다

- 위치: `frontend/src/utils/secureStorage.ts:1-43`, `frontend/package.json:18-19`,
  `frontend/src/app/components/SettingsModal.tsx:137`
- 증상: 43줄짜리 암호화 저장 모듈이 있으나 저장소 어디에서도 불러 쓰지 않습니다.
  `SecureStorage` 를 검색하면 자기 자신을 참조하는 28행과 36행 외에 결과가 없습니다.
  이 모듈 하나 때문에 `crypto-js` 와 `@types/crypto-js` 두 의존성이 남아 있습니다.
- 원인: 모듈이 제공하려던 기능을 실제 코드가 쓰지 않는 방향으로 정착했습니다.
  `SettingsModal.tsx:137` 은 OpenAI API 키를 `localStorage.setItem` 으로 평문 저장합니다.
- 영향: 설령 이 모듈을 쓰더라도 보호 효과가 없습니다. 4행의 키가
  `NEXT_PUBLIC_STORAGE_SECRET` 이라서 클라이언트 번들에 그대로 실리고, 환경변수가 없으면
  하드코딩된 `'closing-bet-demo-secret-key'` 로 떨어집니다. 지금은 지우는 편이
  정확한 상태를 남깁니다.
- 참고: `zustand` 와 `react-icons` 두 의존성도 `frontend/src` 전체에서 한 번도
  임포트되지 않습니다. 다만 `frontend/package.json` 은 §2 표에서 인프라 카테고리에
  배정되어 있으므로, 의존성 제거 자체는 그쪽과 조율할 사항입니다.
- 우선순위: `P1`

### 3.2 랜딩 페이지 713줄 전체가 상태 하나 때문에 클라이언트 컴포넌트다

- 위치: `frontend/src/app/page.tsx:1`, `:7`, `:319-331`
- 증상: 첫 줄에 `'use client'` 가 붙어 있어 713줄 전체가 클라이언트 번들에 실립니다.
  그런데 이 파일이 쓰는 클라이언트 기능은 7행의
  `useState<'vcp' | 'supply' | 'closing'>('closing')` 하나이며, 이를 바꾸는 지점도
  319행, 325행, 331행 세 개의 탭 버튼뿐입니다. 나머지는 모두 정적 마크업입니다.
- 원인: 경계를 파일 단위로 잡았습니다. `next-best-practices` 는 클라이언트 경계를
  상호작용이 실제로 일어나는 지점까지 내리도록 권합니다.
- 영향: 첫 진입 화면의 자바스크립트 전송량이 필요 이상으로 큽니다. 탭 전환 부분만
  작은 클라이언트 컴포넌트로 떼어내면 나머지는 서버 컴포넌트로 남습니다.
- 참고: `ClosingBetCriteriaModal.tsx:1` 과 `VCPCriteriaModal.tsx:1` 도 훅과 이벤트
  처리기가 하나도 없는데 `'use client'` 가 붙어 있습니다. 다만 두 파일은 클라이언트인
  `Modal.tsx` 를 통해서만 렌더링되므로 지시문을 지워도 번들 크기는 달라지지 않습니다.
- 우선순위: `P2`

### 3.3 세션 상태를 파생 상태로 한 번 더 복사한다

- 위치: `frontend/src/app/components/SettingsModal.tsx:37-38`, `226-240`
- 증상: `isGoogleLoggedIn` 과 `googleUserInfo` 두 상태가 `useSession` 이 이미 주는
  `status` 와 `session.user` 를 `useEffect` 안에서 그대로 옮겨 담습니다.
- 원인: 렌더링 중에 계산할 수 있는 값을 상태로 승격했습니다.
- 영향: 세션이 갱신될 때마다 렌더링이 한 번 더 일어나고, 두 값이 원본과 어긋날 여지가
  생깁니다. `status === 'authenticated'` 를 그 자리에서 읽으면 두 상태가 필요 없습니다.
- 우선순위: `P2`

### 3.4 동작하지 않는 장식용 조작부가 남아 있다

- 위치: `frontend/src/app/components/Header.tsx:63-77`, `:80-86`,
  `frontend/src/app/components/Sidebar.tsx:260-263`,
  `frontend/src/app/components/SellStockModal.tsx:20`, `:119-121`
- 증상: 헤더 검색창은 상태도 변경 처리기도 없어서 입력해도 아무 일이 일어나지 않으며
  `⌘K` 안내 문구도 대응하는 단축키가 없습니다. 종 모양 알림 버튼은 실제로는 설정 창을
  열고, 읽지 않은 알림을 뜻하는 붉은 점이 항상 표시됩니다. 사이드바의
  `도움말 & 지원` 버튼에는 `onClick` 이 없습니다. `SellStockModal.tsx:20` 의
  `useState<'quantity'>('quantity')` 는 값이 하나뿐이고 `setMode` 를 부르는 곳이 없으며,
  119행부터 121행까지는 주석만 든 빈 `div` 입니다.
- 영향: 사용자가 동작을 기대하고 눌렀다가 아무 반응이 없는 지점이 네 곳 생깁니다.
- 우선순위: `P2`

## 4. 비대한 파일

### 4.1 `PaperTradingModal.tsx` 가 책임 여덟 가지를 한 파일에서 진다

- 위치: `frontend/src/app/components/PaperTradingModal.tsx` (1,140줄)
- 책임 목록: 포트폴리오 조회(135행), 거래내역 조회(146행), 자산 히스토리 조회와
  기간 필터(155-170행), Escape 키 처리(204-216행), `lightweight-charts` 동적 로딩과
  차트 생성 및 정리와 이동평균 계산(218행 이후), 입금(524행), 계좌 초기화(541행),
  매수와 매도 오케스트레이션(579-599행), 그리고 네 개 탭의 마크업 전체입니다.
- 영향: 상태 훅만 열여덟 개이고, 차트 초기화 하나를 고치려 해도 파일 전체를 훑어야
  합니다. 매수와 매도 결과 처리(§1.1)가 차트 코드 사이에 묻혀 있는 것이 이 구조의
  직접적인 결과입니다.
- 우선순위: `P1`

### 4.2 `SettingsModal.tsx` 가 서로 무관한 설정 여섯 종류를 함께 담는다

- 위치: `frontend/src/app/components/SettingsModal.tsx` (1,068줄)
- 책임 목록: 프로필 편집, 서버 환경변수 조회와 저장(100-140행), 관심 종목 목록
  관리(57-92행), 구글 로그인과 로그아웃(226-249행), 알림 채널 시험 발송(269-313행),
  계정 초기화(142-163행)입니다. 탭 네 개가 이 여섯 가지를 나눠 담고 있으나 상태와
  효과는 모두 한 컴포넌트에 모여 있습니다.
- 영향: 관심 종목 저장 효과(82-92행)와 환경변수 조회 효과(94-98행)가 같은 `isOpen`
  의존성으로 얽혀 있어서, 한쪽을 손대면 다른 쪽의 실행 시점이 함께 움직입니다.
- 우선순위: `P2`

## 5. 검증 공백

### 5.1 주문 금액 계산 분기에 대응하는 검사가 없다

- 위치: `frontend/src/app/components/BuyStockModal.tsx:60-70`, `92-129`,
  `frontend/src/app/components/SellStockModal.tsx:32-41`
- 증상: 수량 모드와 금액 모드를 가르는 분기, 최대 매수 가능 수량 계산, 증감 버튼의
  상한 처리, 수수료와 세금 계산이 모두 검사 없이 남아 있습니다. 유일한 컴포넌트 검사인
  `PaperTradingModal.test.tsx` 는 Escape 키(72행), ARIA 속성(97행), 입금 한도(117행)
  세 가지만 다룹니다.
- 원인: 저장소 규약(`CLAUDE.md` 의 ponytail 절)은 분기와 점수 계산에 검사를 하나씩
  남기도록 정하고 있으나, 이 계산부에는 적용되지 않았습니다.
- 영향: §1.2 의 불일치가 도입 시점에 걸러지지 않았습니다. `BuyStockModal.tsx:60` 의
  `fetchedPrice || stock.current_price || stock.entry_price || stock.price || 0` 처럼
  가격이 0으로 떨어지는 경계도 검사 대상이 없습니다. 이 경우 198행의
  `Math.floor(portfolio.cash / (price * 1.00015))` 가 `Infinity` 가 되어
  `가능: ∞주` 라고 표시됩니다.
- 우선순위: `P1`

### 5.2 `src/lib/api.ts` 에 대응하는 검사 파일이 없다

- 위치: `frontend/src/lib/api.ts:9-40`
- 증상: 저장소의 모든 HTTP 호출이 지나가는 파일인데 `api.test.ts` 가 존재하지 않습니다.
- 원인: 검사 파일 열네 개 가운데 아홉 개가 화면 단위이고, 나머지 다섯 개는
  업그레이드 기준선 검사입니다.
- 영향: 타임아웃 경로(12행), `AbortError` 를 `Request timed out` 으로 바꾸는 변환(35행),
  `response.ok` 가 거짓일 때 `error.status` 와 `error.data` 를 붙이는 경로(24-32행)가
  모두 검사 없이 남아 있습니다.
- 우선순위: `P1`

### 5.3 기존 검사 두 개가 동작 대신 소스 문자열을 확인한다

- 위치: `frontend/tests/nextjs-features/error-pages.test.ts:26-56`,
  `frontend/tests/smoke/upgrade-smoke.test.ts:36-60`
- 증상: `readFileSync` 로 소스 파일을 읽어 `expect(errorContent).toContain('오류가
  발생했습니다')` 처럼 문자열이 들어 있는지 확인합니다. 화면을 렌더링해 동작을 보지
  않으므로, 문구를 유지한 채 로직이 깨져도 통과합니다. `upgrade-smoke.test.ts:57-60` 은
  검사 안에서 `npm run build` 를 실행합니다.
- 영향: 검사가 통과한다는 사실이 화면이 동작한다는 뜻이 되지 못합니다. 빌드를 검사
  안에서 돌리기 때문에 vitest 실행 시간이 빌드 시간만큼 늘어납니다.
- 경계: 이 지적은 백로그의 `[FE-001]` 과 겹치지 않습니다. `[FE-001]` 은
  `tests/baseline/` 아래 두 파일의 낡은 버전 고정 검사를 다루고, 여기서 지적하는 것은
  `tests/nextjs-features/` 와 `tests/smoke/` 아래 두 파일의 검증 방식입니다.
- 우선순위: `P2`

## 요약

| 관점 | 발견 | 그중 P0 | P1 | P2 |
|---|---|---|---|---|
| 깨진 동작 | 5 | 3 | 1 | 1 |
| 중복 | 3 | 0 | 3 | 0 |
| 과잉 설계 | 4 | 0 | 1 | 3 |
| 비대한 파일 | 2 | 0 | 1 | 1 |
| 검증 공백 | 3 | 0 | 2 | 1 |
| 합계 | 17 | 3 | 8 | 6 |

---

# 2부: TODO 항목 초안

일련번호는 `docs/dev-cycle/` 전체에서 `FE` 약어의 최대 번호가 `FE-002` 임을 확인한 뒤
`FE-003` 부터 매겼습니다. 티어는 `tier-rules.md` §3 절차로 판정했습니다.

### [FE-003] 모의투자 주문 실패 처리와 정산 금액을 실제와 맞춘다
- 카테고리: 프론트엔드 공통 | 티어: T2 | 우선순위: P0 | 근거: AUDIT-FE §1.1, §1.2, §5.1
- 건드릴 파일은 `frontend/src/lib/api.ts`, `PaperTradingModal.tsx`, `BuyStockModal.tsx`,
  `SellStockModal.tsx` 네 개이며 위험 경로에 닿지 않아 `T2` 입니다. 다만 수수료와 세금을
  프론트엔드에서 걷어내는 대신 백엔드에 도입하는 쪽을 고르면
  `services/paper_trading_trade_account_mixin.py` 가 `tier-rules.md` §2 의 위험 경로이므로
  그 시점에 `T3` 으로 올립니다.
- [ ] `paperTradingAPI.buy` 와 `sell` 을 `fetchAPI` 로 옮겨 상태 코드를 확인하게 만듦
- [ ] `handleBuySubmit` 과 `handleSellSubmit` 이 응답의 `status` 를 읽고 실패를 표시하도록 수정
- [ ] 수수료와 세금을 프론트엔드 표기에서 걷어낼지 백엔드에 도입할지 결정하고 한쪽으로 통일
- [ ] 수수료율 상수 여섯 자리를 한 곳으로 모음
- [ ] 매수 가능 수량과 정산 금액 계산에 vitest 검사 추가
- [ ] 가격이 0일 때 `가능: ∞주` 로 표시되는 경계 처리

### [FE-004] 사이드바 로그아웃과 사용자 표시를 실제 세션에 연결한다
- 카테고리: 프론트엔드 공통 | 티어: T2 | 우선순위: P0 | 근거: AUDIT-FE §1.3, §3.3
- 인증에 닿으므로 `tier-rules.md` §1 마지막 문단에 따라 `/security-review` 를 추가합니다.
- [ ] `Sidebar.tsx` 의 로그아웃 버튼이 `signOut` 을 호출하도록 수정
- [ ] `localStorage` 의 `user_profile` 과 `next-auth` 세션 가운데 어느 쪽을 표시의 기준으로
      삼을지 정하고 사이드바 표기를 그 기준에 맞춤
- [ ] `SettingsModal` 의 `isGoogleLoggedIn` 과 `googleUserInfo` 파생 상태 제거
- [ ] 로그아웃 후 관리자 전용 화면이 닫히는지 확인
- [ ] `/security-review` 실행

### [FE-005] HTTP 호출 경로를 `fetchAPI` 로 통일하고 세션 조회 중복을 없앤다
- 카테고리: 프론트엔드 공통 | 티어: T2 | 우선순위: P1 | 근거: AUDIT-FE §2.1, §2.3, §5.2
- `api.ts` 열한 개 함수와 컴포넌트 세 개를 건드리므로 300줄에 근접합니다. 구현 후
  `git diff --stat` 이 300줄을 넘으면 `T3` 으로 올립니다.
- [ ] `krAPI` 와 `paperTradingAPI` 의 raw `fetch` 열한 곳을 `fetchAPI` 로 이관
- [ ] 409 응답 구분과 `error.error` 읽기 같은 개별 처리를 `fetchAPI` 위에서 표현
- [ ] `browser_session_id` 발급을 공용 헬퍼 하나로 모음. 챗봇 카테고리의 사본은
      해당 카테고리와 경계를 맞춘 뒤 정리
- [ ] 사용량 조회 두 곳에 `encodeURIComponent` 적용
- [ ] `src/lib/api.test.ts` 를 만들어 타임아웃, `AbortError`, 실패 상태 코드 분기 검사

### [FE-006] API 키 저장 경로를 정리하고 죽은 코드를 걷어낸다
- 카테고리: 프론트엔드 공통 | 티어: T2 | 우선순위: P1 | 근거: AUDIT-FE §1.4, §3.1
- 삭제 위주라서 줄 수로는 `T1` 에 해당할 수 있으나, 의존성이 함께 빠지면서 번들 구성이
  달라지므로 `tier-rules.md` §1 의 의존성 관련 조항 취지에 따라 `T2` 로 둡니다.
- [ ] `src/utils/secureStorage.ts` 삭제
- [ ] `crypto-js`, `@types/crypto-js`, 그리고 미사용인 `zustand` 와 `react-icons` 제거.
      `frontend/package.json` 은 인프라 카테고리 소관이므로 그쪽과 조율
- [ ] `PERPLEXITY_API_KEY` 를 읽는 쪽과 쓰는 쪽의 비대칭 해소
- [ ] API 키를 클라이언트에 남길지 서버에만 둘지 결정하고 한쪽으로 정리
- [ ] `npm run build` 와 vitest 전체 통과 확인

### [FE-007] 모달 셸을 통합하고 대형 클라이언트 컴포넌트를 나눈다
- 카테고리: 프론트엔드 공통 | 티어: T3 | 우선순위: P1 | 근거: AUDIT-FE §2.2, §3.2, §4.1
- `PaperTradingModal.tsx` 1,140줄 분해만으로 300줄을 넘기므로 `T3` 입니다.
- [ ] 다섯 벌의 모달 셸을 `Modal.tsx` 하나로 모으고 Escape 키와 ARIA 속성을 한 자리에서 보장
- [ ] `PaperTradingModal.tsx` 에서 자산 차트를 별도 컴포넌트로 분리
- [ ] `PaperTradingModal.tsx` 에서 입금과 계좌 초기화를 별도 컴포넌트로 분리
- [ ] `src/app/page.tsx` 의 탭 전환부만 클라이언트 컴포넌트로 떼어내고 나머지를 서버 컴포넌트로 환원
- [ ] `SellStockModal` 의 단일 값 상태와 빈 오버레이 제거
- [ ] agent-browser 로 모의투자 화면과 랜딩 화면을 실측. Next.js 가 16.1.6 이므로
      `frontend-skills.md` §3 에 따라 `npm run build` 결과를 함께 확인

**항목으로 만들지 않은 발견**: §1.5(문서 언어와 CDN 의존), §3.4(장식용 조작부),
§4.2(`SettingsModal` 분해), §5.3(소스 문자열 검사)은 우선순위가 `P2` 이고 위의 다섯 항목과
작업 영역이 겹치므로, 해당 파일을 여는 사이클에서 함께 처리하는 편이 낫다고 판단해
독립 항목으로 세우지 않았습니다.
