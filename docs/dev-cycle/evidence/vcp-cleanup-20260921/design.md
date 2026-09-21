# VCP 분석 경로 정리 설계

2026-09-21 사용자 요청: 남은 연관 TODO를 묶어 연속 진행하며 승인 판단도 위임.
brainstorming architectural / T3. 실제 사용자 개별 승인 응답을 생성한 것으로 기록하지 않는다.
리더가 위임 범위에서 아래 설계와 계획을 검토하고 실행한다.

## 의도와 경계

교육·개인 사용 프로젝트에서 기존 동작을 보존하면서 죽은 구현을 제거하고 결측 확신도를 실제 0과 구분한다.
VCP-005, INFRA-008을 완료 단위로 묶고 VCP-022의 확신도 경로는 같은 검증에서 보완한다.
VCP-022의 과거 모의 산출물과 당시 실행 이력 요구사항은 별도 후속으로 남으며 이 부분을 완료로 세지 않는다.
원본 .env/data/logs, 원본 3500/5501 및 live는 접근하지 않는다. 실행은 비밀 없는 소유 scratch와 OS sandbox에서만 수행한다.
원본 사용자 package.json은 보존한다. 새 의존성, 실제 LLM/수집/설정/거래/삭제는 없다.

## 선택

전체 분석기 교체는 범위와 회귀 위험이 크다. 아무것도 삭제하지 않는 선택은 죽은 경로를 남긴다.
기존 클래스·API와 실제 fallback을 유지하는 최소 삭제를 선택한다.
- 호출자 없는 _fallback_to_zai 제거.
- status 추출은 기존 클래스 메서드로 통합하되 Z.ai가 code 속성을 보지 않던 차이는 인자로 보존한다.
- Z.ai의 1회 for loop는 제거하고 모델 전환을 직접 continue/break로 표현한다. echo 2회 재시도와 JSON repair는 보존한다.
- Perplexity 허용 provider 계산의 도달 불가능한 중복 반복만 제거. 설정 교집합/순서 유지.
- init_data의 assign_grade, create_market_gate, reset_cache와 그것에만 연결된 시장/섹터 캐시 wrapper 제거.
  assign_grade 전용 테스트는 삭제된 구현만 검사하므로 함께 제거한다. 실제 등급 엔진은 변경하지 않는다.
- VCP JSON confidence는 기존 safe_confidence를 재사용한다. 결측/비수치/무한대는 None, 실제 0은 0.
  직접 원시 dict를 받는 저품질 판정은 범위 밖 거부를 유지하며 OverflowError도 저품질로 처리한다. 0~1 자동 확대 없음.

## 검증 및 완료

삭제 전 기존 fallback/MarketGate/등급 테스트로 동작을 고정하고 새 confidence 회귀를 RED→GREEN으로 실행한다.
전체 pytest/Vitest, 독립 ponytail→code-review+architect→심층 review를 거친다.
UltraQA App 대응: 실제 VCP 화면의 3개 탭에서 결측/0/75 대조, raw fallback, 오류/복구, 소유 자원 정리.
UI 데이터는 격리 API fixture가 실제 parser를 통과해 생성한다. 실제 LLM 호출은 검증하지 않는다.
VCP-005/INFRA-008 필수 검증 통과 후만 제거/아카이브. VCP-022는 잔여 요구를 유지한다.

Parser의 유한 범위 밖 수치 clamp(-1→0, 101→100)는 기존 계약 그대로다. 직접 raw dict 품질검사와 구분하며 새로운 거부정책을 추가하지 않는다.
