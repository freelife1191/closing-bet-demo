# 후속4건 독립 검토 지적

code-review: REQUEST CHANGES (1 MEDIUM)
- closing-bet/page.tsx913/1534: rawD-only를분석자료없음으로오안내. 원자료없음/표시가능D제외/사용자필터0분리, D-only회귀추가필요.
- 포맷·단위·zero계약·모바일/툴팁나머지적합. 신규보안문제없음.

architect: BLOCK (1 HIGH,1 MEDIUM)
- 상세화면foreign/institution/individual >=0이면+접두사와format(0,'-')가결합해'+-'출력. >0에서만+,0중립색,실제상세0/fallback회귀필요.
- rawsignals→D제외eligible→화면필터visible 경계를명시, D-only+활성비등급필터에서도원인을유지해야함.
- 원단위/반올림/전체테마/CSS나머지일치.

위문서는두독립판정의요약이며승인으로변환하지않았다. 최종영향재검토는별도기록한다.
