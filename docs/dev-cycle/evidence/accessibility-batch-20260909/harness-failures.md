# 준비·조작 오류

1. 실행비트 없는 setup/start 스크립트를 직접 호출해126. 명시적 zsh로 실행.
2. setup의 for path는 zsh PATH 특수변수를 덮어써 ln command not found127. check_path로 수정하고 이미완성된archive의 env/data부재 확인 후 의존성 링크만 생성.
3. 기동전검토에서cookie secret JS변수누락, 이전cleanup killpg0잔재, pagination/chart fixture누락을발견보완. 실제서비스코드수정없음.
4. 375px 화면에서 넓은 보유 행 ref click은 모달을열지 않아 wait25초실패. 후속스크린샷 성공이 앞선실패를덮지않도록 initial-stock-* 보존. 같은행에 focus→Enter의실제키보드진입으로모달열림확인. 모바일좌표클릭원인은미확정. 후속데스크톱행클릭과모바일키보드진입은성공.

5. 첫 scroll selector가두모달에일치해뒤쪽을선택했다. space-y-4로앞쪽모달을고른후scrollTop>0확인해최종문구전체가시성통과.
