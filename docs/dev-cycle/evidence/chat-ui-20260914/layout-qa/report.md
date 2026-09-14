# CHAT-019·010 Layout QA 보조 보고

- 검증 기준: `b86358f00b56c536cad17dd4db9d149d1a408a60` (`../qa-source.json`)
- 대상: 부모 소유 격리 앱 `http://127.0.0.1:57601` → fixture `57602`
- 브라우저: `chat-layout-20260914/qa`, scratch의 `layout-profile`
- 안전 경계: 원본 3500/5501·live·설정/거래/삭제·실제 LLM을 조작하지 않았다. 일반 합성 질문
  `QA 일반 질문` 한 건만 fixture에 전송해 drawer의 세션 항목을 만들었다. 삭제 버튼은
  확인 모달을 여는 데만 쓰고 확인/삭제는 누르지 않았다.

## S1 — 통과

- 1280×577: 빈 화면의 네 카드·빠른 조회 툴바와 명령 팝업의 다섯 행을 실제 화면에서
  읽었다. `s1-1280-empty.png`, `s1-popup.png`를 직접 열어 겹침이 없음을 확인했다.
  같은 popup snapshot의 `/clear all` box는 y=364.40625~408.40625, 툴바 `시장 현황`
  box는 y=425.40625~457이어서 분리됐다.
- 1440×900: 실제 빈 화면은 `s1-1440-empty-only.png`이며 직접 열어 확인했다.
  명령 팝업 다섯 행은 `s1-1440-popup-snapshot.txt`에서 확인했다.
  `s1-1440-empty.png`는 이름과 달리 팝업이 열린 화면이므로 빈 화면 증거로 쓰지 않는다.
- 375×812: `s1-375-empty.png`, `s1-375-popup.png`를 직접 열어 카드 네 장, 툴바,
  명령 다섯 행이 읽히고 겹치지 않음을 확인했다. popup은 툴바보다 앞의 정상 흐름에
  배치되어 있으며, 화면 스크롤 후에도 snapshot의 네 카드와 다섯 명령이 계속 접근 가능했다.
- VCP ChatWidget: `s1-widget-command-snapshot.txt`에서 `/clear 현재 세션 메시지 삭제`,
  `/clear all 내 대화와 메모리 프로필 삭제`가 chatbot 화면과 일치함을 확인했다.

## S2 — 실패

- 메뉴를 접은 뒤 `대시보드 홈` 등 탐색 링크는 snapshot에서 사라졌고, Tab 한 번의
  active element는 `메뉴 닫기`였다. 숨은 링크를 Tab으로 건너뛰었다.
- 대화 항목을 선택하면 drawer가 닫히고 active element가 `메뉴 열기`로 돌아갔다.
  직접 닫기도 같은 초점 복귀를 확인했다.
- **실패:** drawer 안의 `QA 일반 질문 삭제`로 `대화 삭제` 확인 모달을 연 뒤,
  모달 내부 `취소`에 명시적으로 초점을 맞춰 Escape를 눌렀다. 그 첫 Escape 뒤
  `s2-escape-focus-first-snapshot-retry.txt`에는 모달뿐 아니라 `메뉴 닫기`도
  사라졌다. 요구사항인 “첫 Escape는 모달만 닫고, 두 번째 Escape가 drawer를 닫음”을
  실제 브라우저에서 만족하지 못한다.

## S3 — 통과

- desktop→mobile: `s3-desktop-snapshot.txt`에는 mobile drawer가 없고,
  `s3-desktop-to-mobile-snapshot.txt`에는 `메뉴 열기`만 있어 잔류 overlay가 없다.
- mobile open→desktop→mobile: 열린 drawer(`s3-mobile-open-snapshot.txt`)가 desktop
  전환 뒤 사라지고(`s3-mobile-to-desktop-snapshot.txt`), 재차 mobile 전환 뒤
  `메뉴 열기`만 남았다(`s3-desktop-to-mobile-again-snapshot.txt`).

## 하네스·정리

- 설치된 CLI는 `viewport 1280x577`이 아니라 `set viewport 1280 577` 문법이다.
  초기에 생긴 `Unknown command: viewport`는 제품 실패가 아니다.
- 연속 캡처 중 한 번 `s1-1440-popup-screenshot.txt`가 30초 timeout이 났다.
  session의 `get url`/snapshot은 재기동 후 정상 복구했고, 기존 성공 이미지와
  1440 snapshot을 사용했다. 이 timeout은 화면 결함으로 분류하지 않는다.
- `s1-375-popup-clearall-box.txt`는 ref 갱신 뒤 `FLASH`를 읽은 잘못된 box라서
  판정에 사용하지 않았다. PNG 직접 열람을 정상 근거로 썼다.
- `cleanup-close.txt`로 이 browser session을 종료했고, 정확한
  scratch `layout-profile`은 휴지통으로 이동해 경로 부재를 확인했다. 57601/57602와
  부모 profile/fixture는 중지·재시작·삭제하지 않았다.
