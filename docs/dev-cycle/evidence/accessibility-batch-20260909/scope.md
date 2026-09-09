# FE-034·FE-040 검토 범위

사용자는 직전 제안한 제목·breadcrumb 및375×812 빈표4곳을 포함해 연관 라운드 연속 진행을 요청했다.
Bounded/T2: 구현5파일, 회귀2새파일+기존FE024 확장. 300줄 미만, 위험 경로 없음.
제목h1→h2→h3→h4 연속 계층. 독립 상세/차트 모달 기존 제목 보존.
Header nav/ol/li/aria-current와 홈 링크이름; 시각배치와모바일숨김유지.
빈표 안내는 overflow 밖 카드폭, 문구/조건/데이터행/거래동작불변. 새공용추상화없음.
기준f7801ff, review-input.json의 tracked/untracked 모든 소스/테스트 해시.
회귀FE03413통과, FE0403통과+인접24통과. 전체검사 부모진행중.
과잉설계→code-reviewer+architect 독립검토. reviewer 각15분, QA60분상한.
Next 번들05 server/client,03 layouts/pages 읽음. TDD실제RED→GREEN.

리더 해석: 기존 colSpan 빈 행 자체는 유효한 HTML이며 리뷰 원문의 invalid 표현은 채택하지 않는다. 실제 결함은 min-width 표 중심으로 인한 모바일 가시성이다. polling 주석 관찰은 검토범위밖 비차단으로 기록하고 제품수정에 섞지 않는다.
전체 pytest2281/2skip, Vitest446/64, typecheck0, lint0errors/199warnings 통과.
