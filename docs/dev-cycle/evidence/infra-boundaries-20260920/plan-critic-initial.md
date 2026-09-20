# REJECT → 안전 경계 보완

ui_architect: 전체 restart_all.sh 실행/source는 의존성 설치·포트 종료·서버 기동으로 이어진다. 정확한 pkill 줄만 추출해 가짜 pkill argv 캡처로 실행하도록 명시해야 한다. 실제 kill/pkill/lsof/ss나 dummy 종료도 실행하지 않는다. 나머지 계약은 충분. 계획과 QA P1에 반영.
