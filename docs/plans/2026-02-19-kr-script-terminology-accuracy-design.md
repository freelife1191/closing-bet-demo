# KR 대본 용어 정확도 개선 설계

**작성일:** 2026-02-19  
**대상 프로젝트:** `closing-bet-demo` (`project-showcase-kit` 파이프라인)

## 1. 배경

기존 대본/자막 생성 흐름에서 다음 문제가 확인되었다.

- 제품명/용어가 프로젝트 실제 문구와 어긋나는 경우가 발생
- 한국어 발음/변환 과정에서 오역 또는 깨진 표현이 발생 (`마켓 게이` 사례)
- 생성 직후 용어 검증이 없어 Gate A 이전에 결함이 누적될 수 있음

## 2. 확정 결정사항

아래 정책을 이번 개선의 고정 규칙으로 적용한다.

- 공식 제품명: `KR Market Package`
- 수정 범위: 원천(설정/스크립트/스킬/검증)만 수정, 기존 산출물 자동 수정 금지
- 검증 시점: `manifest` 단계에서 즉시 검증(fail-fast)
- 영어 UI 용어 정책: 영어 원문만 허용(한글 병기/의역 금지)

## 3. 접근안 비교

### 안 A. 정적 용어집 단일 검증
- 장점: 단순, 안정적
- 단점: 화면/README 변경 시 수동 유지보수 부담 큼

### 안 B. 동적 추출 단일 검증
- 장점: 변경 추적 자동화
- 단점: 노이즈 포함으로 오탐 위험 큼

### 안 C. 하이브리드(채택)
- 구성: 정적 용어집(브랜드/금지어/핵심 용어) + 동적 추출(UI/README 기준어)
- 장점: 정확도와 유지보수 균형, 오역 차단에 유리
- 단점: 초기 구현 난이도 증가

## 4. 아키텍처

### 4.1 기준 데이터 계층 (Source of Truth)
- 화면 기준: `frontend/src/app/**`
- 문서 기준: `README.md`
- 장면 카탈로그 기준: `project/project-showcase-kit/config/scene_catalog.yaml`
- 고정 규칙:
  - 브랜드명 정확 매칭: `KR Market Package`
  - 금지 오역 패턴: 예) `마켓 게이`
  - 영어 UI 용어 원문 강제: 예) `Market Gate`, `Overview`, `Candidates`

### 4.2 생성 계층
- 기존 `build_manifest.py`는 대본/manifest 생성 역할 유지
- 생성 책임과 검증 책임을 분리

### 4.3 검증 계층
- 신규 검증 스크립트가 생성 결과를 검사
- 검사 대상:
  - `project/video/manifest.json`의 `narration*`, `must_show_ui`, `title`
  - `project/video/script.md` 및 언어별 script
- 실패 정책: `ERROR` 1건 이상이면 exit code 1

## 5. 데이터 흐름

1. `run_stage.sh manifest` 실행
2. `build_manifest.py`가 manifest/script 생성
3. 신규 용어 검증 스크립트 실행
4. 위반 시:
   - `manifest` 단계 즉시 실패
   - `project/video/evidence/term_validation_manifest.json` 리포트 기록
5. 통과 시 이후 단계(record, voice, captions...) 진행

## 6. 에러/리포트 정책

### 6.1 Severity
- `ERROR`: 즉시 실패
  - 브랜드명 불일치
  - 금지 오역 탐지
  - 영어 UI 용어 비원문 치환
- `WARN`: 통과 가능, 리포트 기록
  - 의미 왜곡은 없으나 문체/띄어쓰기 후보 이슈

### 6.2 리포트 형식
`project/video/evidence/term_validation_manifest.json`

필드 예시:
- `severity`
- `rule_id`
- `scene_id` 또는 `file`
- `offending_text`
- `expected`
- `suggestion`

## 7. 테스트 전략

### 7.1 단위 테스트
- 브랜드명 정확 매칭 통과/실패
- 금지어(`마켓 게이`) 탐지 실패
- 영어 용어 원문 정책 통과/실패
- 리포트에 위치 정보(scene/file)가 남는지 검증

### 7.2 통합 테스트
- 정상 카탈로그 입력 시 `manifest` 성공
- 의도적 위반 입력 시 `manifest` 실패 + 리포트 생성 확인
- 기존 산출물 자동 수정이 일어나지 않는지 확인

## 8. 스킬 개선 범위

신규 스킬을 추가해 아래 절차를 강제한다.

1. 생성 전: 기준 용어집/규칙 확인
2. 생성 후: 검증 리포트 확인
3. 실패 시: 수정 지점/권장 치환 제시

## 9. 비목표(Non-Goals)

- 기존 `project/video/script*.md`, `manifest*.json`, `captions/*.srt` 자동 재작성
- TTS 발음 품질 자체를 자동 교정하는 모델 변경
- 투자 표현/카피 전략 전면 개편

## 10. 완료 조건

- `manifest` 단계에서 용어 오역이 fail-fast로 차단된다.
- 공식 제품명/영어 원문 규칙 위반이 자동 검출된다.
- 검증 리포트로 수정 포인트가 재현 가능하게 남는다.
- 원천만 수정 정책이 지켜진다.
