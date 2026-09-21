# QA 실행 이력

- cycle1: fixture 카드 score 세부값 누락을 보완(제품수정없음). owned fixture48546만 종료후50901로기동.
  기동준비확인전탐색으로gateway9건 ConnectionRefusedError(HTTP502). auth/session·auth/_log·dates/latest·quota 포함.
  당시브라우저console수집JSON은{}여서 오류없음증거로쓰지않음. 동일Space18유지, readiness GET200확인후재탐색.
- cycle2: Page.addScriptToEvaluateOnNewDocument 관측배열이 다음ego invocation의navigation뒤undefined.
  observer배열.length 접근에서 TypeError: Cannot read properties of undefined (reading 'length'), exit1.
  제품화면은정상이나검증하네스실패로보존. 완료판정하지않음.
- cycle3: 현재page에명시적으로error/unhandledrejection/console.error observer설치.
  reload없이실제리포트다시불러오기버튼/모달닫기재열기로 known→legacy→invalid→error→known검사전체재실행.
  초기navigation오류는 observer범위밖이므로 Next get_errors/configErrors/sessionErrors 빈배열로별도확인.
  browser-matrix.mjs exit0, browser-recovery.mjs exit0. 최종행렬모든errors/consoleErrors빈배열.
  expected5033건(StrictMode모달요청+보강fetch)은의도한실패시나리오이며복구200확인.
- 각실패는별도원인1회. 제품코드는첫커밋9c69e9a이후변경없음.
- 최종직접열람8PNG는image-review.json 목록. 초기/진단캡처는최종시각판정에서제외.
