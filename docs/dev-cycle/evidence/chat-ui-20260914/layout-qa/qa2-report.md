# CHAT-019·010 QA2 실제 UI 재검증

- 기준: `174795bf37f9f6f60515687c5a3ba69f49467c5e`;
  `../qa-source-v2.json`의 production 여섯 파일 SHA와 fixture SHA를 사용했다.
- 대상: 부모 소유의 격리 `127.0.0.1:57601` 및 fixture `57602`
  (프로세스 94911/94910). 서비스와 부모 browser/fixture는 중지·재시작하지 않았다.
- 브라우저: `chat-layout-20260914/qa`, scratch `layout-profile`.
- 합성 세션: 실제 chatbot UI에서 `QA2 일반 질문` 한 건만 전송했다.
  `qa2-seed-requests.txt`의 `POST /api/kr/chatbot 200`은 허용된 fixture/가짜 LLM 경계다.
  삭제 확인, 설정 저장, 거래, 수집, 실제 LLM은 실행하지 않았다.

## S2 — 통과

1. 모바일 drawer에서 메뉴를 접으면 `qa2-menu-collapsed-snapshot.txt`에 탐색 링크가
   나타나지 않았다. Tab 한 번 뒤 active element는 `메뉴 닫기`
   (`qa2-menu-collapsed-active.txt`)여서 inert 링크를 건너뛰었다.
2. 직접 닫기와 대화 항목 선택은 각각 drawer를 닫고 active element를
   `메뉴 열기`로 돌렸다
   (`qa2-direct-close-active.txt`, `qa2-select-active.txt`).
3. `QA2 일반 질문 삭제`를 눌러 확인 모달만 열고, 모달의 `취소`에 실제로 초점을
   맞췄다. 첫 Escape 뒤 모달은 사라졌지만 `메뉴 닫기`가 남았다
   (`qa2-escape-first-snapshot.txt`). `qa2-escape-first.png`를 직접 열어
   열린 drawer를 확인했다. 두 번째 Escape 뒤 drawer가 닫히고 active element가
   `메뉴 열기`가 됐다
   (`qa2-escape-second-snapshot.txt`, `qa2-escape-second-active.txt`).

## S3 — 실패

- desktop→mobile은 통과했다. desktop snapshot에는 drawer가 없고
  (`qa2-s3-desktop-snapshot.txt`), mobile 전환 뒤 `메뉴 열기`만 있었다
  (`qa2-s3-desktop-mobile-snapshot.txt`).
- **실패:** mobile에서 drawer를 연 뒤
  desktop→mobile로 왕복했다. desktop에서는 drawer가 보이지 않았으나
  (`qa2-s3-mobile-desktop-snapshot.txt`), 다음 mobile snapshot에
  `메뉴 닫기`와 drawer 내용이 다시 남았다
  (`qa2-s3-final-snapshot.txt`). 실제 UI에서 열린 drawer 상태가 복귀한 것이다.
  재시도하지 않았다.

## 로그·정리

- `qa2-final-errors.txt`에는 페이지 오류가 없었다. console에는 Next 개발 환경의
  HMR/React DevTools 정보만 남았다.
- `qa2-cleanup-close.txt`로 이 session을 종료했다. 정확한 scratch
  `layout-profile`만 휴지통으로 이동했고 경로 부재와 해당 namespace/profile
  프로세스 부재를 확인했다. 제품 파일은 수정하지 않았다.
