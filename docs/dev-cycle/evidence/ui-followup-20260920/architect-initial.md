## 요약

**Architectural Status: `BLOCK`**

갱신 오류 경계, 신호일 종가 표시, 실제 차트 전환, FE-021 조회 경계는 계획과 맞습니다. 그러나 채팅 위젯은 dashboard 밖 데스크톱에서 닫기 경로를 잃고, Python AI 추출기는 malformed `reason`을 그대로 통과시켜 TypeScript 계약과 VCP 런타임을 깨뜨릴 수 있습니다.

## 분석

### HIGH — dashboard 밖 데스크톱에서 열린 채팅을 포인터로 닫을 수 없습니다

ChatWidget은 root에 마운트되어 dashboard 밖 화면에도 존재합니다(layout.tsx:25). 열린 패널은 데스크톱에서 `bottom-24 right-6 z-[110]`이고(ChatWidget.tsx:454), dashboard 밖 launcher도 같은 `bottom-6 right-6` 위치지만 `z-[100]`입니다(ChatWidget.tsx:681).

따라서 launcher는 패널 뒤에 가립니다. 패널 내부 닫기 버튼은 `md:hidden`이라 데스크톱에서는 사라집니다(ChatWidget.tsx:479). 키보드 초점이 launcher에 남아 있으면 Enter로 닫을 수 있지만, 포인터 사용자는 닫을 수 없습니다. 이는 “dashboard 밖 기존 bottom-right 배치 유지”와 열기/닫기 보장 계약을 위반합니다(plan.md:39).

**수정:** dashboard launcher만 header용 위치를 사용하고, dashboard 밖 launcher는 기존 `z-[120]`도 함께 유지하십시오. `/` 데스크톱 경로에서 열기 후 launcher가 panel보다 높은 computed z-index를 가지며 다시 닫히는 회귀가 필요합니다.

### HIGH — Python과 TypeScript AI 정규화 결과가 malformed 입력에서 갈립니다

TypeScript 정규화는 `reason`이 문자열이 아니면 버리고 정상화된 필드만 새 객체로 만듭니다(displayHelpers.ts:33). 반면 Python은 action만 유효하면 원본 candidate 전체를 펼쳐 반환합니다(kr_market_jongga_ai_payload_helpers.py:41).

예를 들어 `{action: "BUY", reason: {text: "bad"}}`는 TypeScript에서 `reason`이 제거되지만 Python에서는 객체 그대로 `gemini_recommendation.reason`에 남습니다. 이 응답 타입은 `reason: string`을 약속하고(api.ts:132), VCP 검증기는 곧바로 `reason.trim()`을 호출하므로 런타임 오류가 납니다(aiHelpers.ts:50). 상세 패널도 reason을 직접 렌더링합니다(vcp/page.tsx:2007).

또한 계획은 `score_details.ai_evaluation`을 `unknown`으로 받아 검사하도록 했지만 현재 화면 인터페이스는 여전히 `AiEvaluation | null`로 신뢰합니다(page.tsx:107, plan.md:49).

**수정:** Python도 raw candidate를 펼치지 말고 정규화된 `action`, 문자열 `reason`, 허용된 confidence/model만 조립하십시오. 세 frontend 후보 필드는 `unknown`으로 선언하고 resolver 뒤에서만 `JonggaAiEvaluation`로 좁히십시오. 유효 action + 객체/숫자 reason 케이스를 Python과 TypeScript 양쪽에 추가해야 합니다.

### MEDIUM — 시세 조회가 영구 대기하면 실패 상태에 도달하지 않습니다

BuyStockModal의 시세 요청은 raw `fetch`이며 timeout/abort가 없습니다(BuyStockModal.tsx:82). `priceLookupFinished`는 promise의 `finally`에서만 true가 되므로(BuyStockModal.tsx:101), 응답이 멈추면 화면은 계속 “시세 조회 중”으로 남고 저장 가격으로 주문 가능한 상태가 지속됩니다(BuyStockModal.tsx:119,225).

**권고:** 기존 `fetchAPI`의 10초 timeout 계약을 사용하거나 로컬 AbortController를 추가해 timeout도 명시적인 실패/저장가격 상태로 수렴시키십시오.

## Root Cause

두 BLOCK 모두 위치 또는 타입의 소유권이 분리된 데서 생깁니다.
- 채팅 위치는 route에 따라 갈리지만 z-index는 공통값으로 덮었습니다.
- AI 후보 우선순위는 Python과 TypeScript에 중복 구현했지만 정규화 출력 계약을 공유하지 않습니다.

## Recommendations
1. dashboard 밖 launcher의 z120 복원 및 실제 `/` 데스크톱 close 회귀 추가 — 낮은 노력, 높은 영향.
2. Python AI 출력의 필드별 정규화와 frontend 후보 타입 unknown 적용 — 중간 노력, 높은 영향.
3. 시세 조회 timeout 추가 — 낮은 노력, 중간 영향.
4. Python/TypeScript에 동일 malformed 사례 표를 두어 두 구현의 판정을 지속적으로 맞춤 — 낮은 노력, 장기 안정성 향상.

## Trade-offs
| 선택 | 장점 | 단점 |
|---|---|---|
| route별 launcher z-index 복원 | 기존 비dashboard 동작을 최소 변경으로 복구 | route 조건에 스타일 분기가 하나 더 생김 |
| 패널 내부 닫기 버튼을 항상 표시 | launcher 위치와 무관한 닫기 경로 | 데스크톱에서 닫기 제어가 중복됨 |
| AI 필드 strict 정규화 | API 타입 보장, VCP 런타임 오류 차단 | 알 수 없는 원본 필드를 일부 버림 |
| raw candidate 보존 | 미래 필드 호환 | malformed 필드가 UI 경계까지 전파됨 |

현재 소스 SHA는 review2 manifest와 일치합니다. 다만 제공된 최신 Vitest review2는 29건 실패 상태이며 부모가 테스트 locator/timing을 보완 중이므로, 위 코드 BLOCK과 별개로도 아직 완료·승인 상태가 아닙니다.

---
부모: 링크 표시만 파일명/줄로 전사함. 첫 HIGH의 가림 원인은 panel bottom96/launcher bottom24+h56이면16px비중첩이므로 이의제기했다. 최종판정은후속review와실측근거참조. 실제 malformed 출력 결함은수정한다.
