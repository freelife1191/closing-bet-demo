# QA2 capture 수정 영향 리뷰

## ponytail 원문
Lean already. Ship.

## code-reviewer 최종 메시지 원문
QA2 2파일 영향 재검토: window keydown capture=true 등록/해제가 대칭이고, document/modal bubble 처리보다 먼저 hasOpenDialog=true를 판정해 listener 사이 flushSync에도 drawer를 보존합니다. variant 2경로 및 전체 488/69, typecheck/lint/build 증거와 SHA 일치. 추가 finding 없음, APPROVE.

## architect 메시지 원문
QA2 두파일 영향 verdict `CLEAR`. window keydown을 capture=true로 등록/해제 대칭(page.tsx:209-218)하여, dialog 열린 Escape에서 window가 먼저 hasOpenDialog=true로 no-op하고 document ModalShell만 닫음. document 처리 중 flushSync로 React가 window listener를 교체해도 capture phase가 이미 지나 새 listener가 같은 이벤트 bubble에 재실행되지 않음. 일반 drawer Escape/초점복원은 기존 테스트 유지(:87-98), flush 없음/있음 두 variant와 두번째 Escape drawer닫힘+refocus를 test:100-132가 고정. 최신 두 SHA manifest 일치, qa2 69/488, lint0err190/build3/type0 증거 확인. 현재 drawer 내부에는 별도 Escape 소비가 필요한 input/popover가 없어 capture 전환의 추가 충돌도 확인되지 않음.

## T3 deep-review 메시지 원문
마지막 영향 리뷰 **APPROVE**. `frontend/src/app/chatbot/page.tsx:216-217`의 keydown 등록/해제가 모두 capture=true로 대칭이며, dialog가 닫히고 document→window 사이에 React 렌더가 flush돼도 window capture 판정은 그보다 먼저 실행되어 drawer를 닫지 않습니다. 회귀 `page.regression-chat-019-010.test.tsx:100-132`는 일반 전파와 listener 사이 `flushSync` 변형을 모두 검사하고 첫 Escape=dialog만, 두 번째 Escape=drawer+초점복원을 확인합니다. 최신 6 SHA가 review-input과 일치하고 Vitest 69/488, typecheck 0, lint 0 errors, build 3/3 증거 확인. 새 문제 없음.
