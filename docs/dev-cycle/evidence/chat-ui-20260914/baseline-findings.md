# 수정 전 실측

기준 ac4ed20의 격리사본으로 관찰했다. baseline.png를 열어1280×577에서카드하단을absolute빠른조회가덮는것을확인했다. baseline-mobile.png에서명령팝업위에버튼/모델선택줄이겹친다.

baseline-focus.txt: 접힌메뉴에서Tab2회뒤 activeElement가숨은대시보드홈 A다. baseline-resize-tree.txt: 모바일메뉴를연후desktop→mobile왕복하면여전히메뉴닫기버튼이있다. 최초desktop로드→mobile전환만으로오버레이가뜬다는기존기록은이번환경에서재현되지않았으며, 이차이를구분한다.

baseline브라우저/서버종료후수정사본으로검증한다. 최초관찰은최종UltraQA완료증거로세지않는다.
