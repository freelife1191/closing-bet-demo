# INFRA-071 Implementation Plan

**Goal:** 현재 뉴스 수집과 실제 AI 분석을 복구하고 실패 시 기존 리포트를 보존한다.
**Architecture:** 기존 뉴스 parser/cache와 generator 예외 경계만 수정한다. 새 서비스/의존성/인증 우회 없음.
**Tech Stack:** Python requests, BeautifulSoup, pytest, 기존 Gemini 엔진.
**Spec:** 이번 대화의 bounded 설계: 현재 네이버 구조 지원, 빈 캐시 재시도, 시장별 실패 저장 차단.
**승인:** 사용자의 “원인 파악해서 문제 해결해” 및 앞선 “승인도 알아서 진행하고 완료해줘” 범위. 추가 승인 요청 없이 수행.
**Tier:** T3(generator_runtime_mixin 위험 경로). writing-plans 적용. 기존 root package.json 보존.

## Tasks
- [x] 현행 HTTP410/네이버 검색 DOM 변경/다음 빈 페이지를 직접 재현한다.
- [x] 현재 DOM 합성 회귀와 빈 캐시 복구 RED→GREEN. base.py/news_scrape_helpers.py/news.py 및 관련 테스트만 수정한다.
- [x] 시장별 실패/부분 실패가 저장 전 전파됨을 tmp 데이터 회귀로 검증한다. 정상 후보 없음은 기존 동작 유지.
- [x] Ponytail→code+architect→T3 리뷰. 독립 검토는 각 단계 최대10분.
- [x] 격리된 전체 pytest/Vitest 검사, 원본 서비스 재기동 및 실제 분석1회, ego-browser 실제 결과 확인.
- [x] 증거/QA/아카이브 마감. 필수 미통과는 TODO 유지.

## Review Focus
- 뉴스 제목에서 접근성 “새 창 열림”/본문 중복 제외, 언론사 매칭, 구형 DOM 호환.
- 빈 캐시 재시도와 정상 양성 캐시 재사용. 기존 빈 캐시 고정 테스트는 변경된 요구사항에 맞춰 변경하고 사유 기록.
- 일부 시장 실패도 전체 성공으로 발행하지 않는다. 정상 조건 미달0건과 구분한다.
- 실제 API 비용은 사용자 승인됨. 알림/매매/시크릿 수정은 금지. 기존 서비스3500/5501은 root만 조작.
- KRX 자격 증명은 없는 채로 유지하며, 뉴스 문제와 독립임을 검증. 자격 증명 없는 실제 KRX 성공을 주장하지 않는다.

추가 확정 원인: 기본 헤더 br 요청→Content-Encoding:br 57153bytes/기사0, gzip요청→332447bytes/기사10. 설치 의존성 추가 없이 gzip/deflate만 광고한다. 실제 비교로 검증함.

설계 명시: 필터통과 후보의 뉴스가 전부 없으면 실제 무뉴스와 수집실패를 현재 구분할 수 없으므로 AllCandidatesFilteredError는 실패로 보수적으로 처리하고 기존자료 보존. Phase1 NoCandidatesError만 정상0건. 명시 회귀 추가.
