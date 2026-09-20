# 공용 UI / 기간 조회
- FE028 Header 미동작 검색 input/button/shortcut 제거. 기존menu/settings 이벤트보존.
- FE010 root ChatWidget 상태유지, dashboard top3.5/right4/w9/h9, Headerpr16. launcher z100으로열린chat110에가려져모바일닫기버튼과충돌방지. 안내말풍선/timer/state삭제. 닫기focus복귀.
- FE021 제품변경없음. 실제PaperTradingAssetChart와chart라이브러리를렌더하고canvas/ResizeObserver만대역으로조회계약검증.
- 공용RED2fail/2pass→18/18pass. FE021mock dependency 실험에canvas오류/타입오류있어실제library+canvas경계대역으로수정; 마지막target-chart-native-canvas1/1오류없음. 최종전체검사필요.
- 전체UI좌표/그림은브라우저필수검증미실행.
