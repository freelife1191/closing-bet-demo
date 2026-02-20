# project-showcase-kit 영상 품질/싱크 고도화 설계서

기준일: 2026-02-20  
대상 저장소: `/Users/freelife/vibe/lecture/hodu/closing-bet-demo`

## 1. 목표

본 설계의 목적은 `project-showcase-kit`의 소개 영상 파이프라인을 다음 기준으로 상향하는 것이다.

1. `short/normal/detail` 3버전을 모두 고품질로 생성
2. 씬 단위 검증을 통과한 경우에만 다음 씬으로 진행
3. TTS+자막+화면 싱크를 엄격 기준으로 정렬
4. `ko+en` 동시 납품에서 영어 대본을 한국어와 완전 분리 생성
5. 최종 단계에서 홍보용 프롬프트 자산을 md로 생성

## 2. 확정된 운영 원칙

- 우선순위: 싱크 안정성 + 시나리오/연출 디테일 동시 강화
- 납품 범위: `short/normal/detail` 모두 1차 필수
- 씬 재시도: 실패 씬 최대 3회 자동 재시도
- 싱크 임계값:
  - scene 경계 오차 `<= 0.15초`
  - 자막 종료-음성 종료 오차 `<= 0.10초`
- 길이 정책: 고정 길이보다 내용/싱크 우선 가변
- 언어: `ko+en` 동시 납품
- 영어 대본: 한국어와 완전 분리 생성(자동 폴백 금지)
- 품질 판정: 자동 지표 + 수동 확인 1회 혼합
- 실행 시간 예산: 3버전 합산 120분 이내

## 3. 현재 문제 진단

### 3.1 녹화 다이내믹 부족
- 씬별 액션 다양성/강조 패턴이 낮아 화면이 정적으로 보임
- 실패 씬 국소 재녹화 루프가 약해 품질 편차 누적

### 3.2 TTS/자막 싱크 느슨함
- 자막 생성이 씬 실측 타임라인보다 전체 스케일링에 치우침
- 씬 단위 정합 검증을 통과하지 않아도 후속 단계 진행 가능

### 3.3 `en` 대본 오염
- 영어 트랙 생성 시 일부 경로에서 한국어 원문 폴백 가능
- `narrationByLang.en` 강제 정합 정책 미흡

### 3.4 홍보 자산 플레이스홀더
- 현재 `assets` 단계는 단순 placeholder 성격
- 썸네일/유튜브 설명/문서/PPT 생성 프롬프트 품질 계약 미흡

## 4. 목표 아키텍처

### 4.1 Pre-Production 계층
- `FeatureCoverageBuilder`: 기능 커버리지 SoT 추출
- `SceneScenarioPlanner`: 버전별 씬 골격/동적 액션 계획
- `DualScriptComposer`: `ko`/`en` 완전 분리 대본 생성
- `SyncBudgetCompiler`: 씬별 시간/발화/자막 예산 편성

### 4.2 Production 계층
- `SceneRunner`: 씬 단위 `record -> voice -> captions -> scene-validate`
- `SceneQualityGate`: 씬 합격 여부 판정, 실패 시 같은 씬 재시도
- 재시도 한도: scene당 최대 3회

### 4.3 Post-Production 계층
- `VersionAssembler`: 버전별/언어별 최종 렌더
- `PromoPromptStudio`: 홍보 프롬프트 md 패키지 생성
- `FinalValidator`: 3버전/2언어/증거 산출물 최종 게이트

## 5. 컴포넌트 계약

### 5.1 FeatureCoverageBuilder
입력: 코드/UI/문서 SoT  
출력: `project/video/scenarios/coverage_matrix.json`

### 5.2 SceneScenarioPlanner
입력: 커버리지 매트릭스, 버전 정책  
출력: `scene_plan_short|normal|detail.json`

### 5.3 DualScriptComposer
입력: 씬 플랜, 언어 정책(`ko+en`)  
출력: `script_<version>.ko.md`, `script_<version>.en.md`  
규칙: `en` 누락/한글 오염 기준 초과 시 실패

### 5.4 SyncBudgetCompiler
입력: scene plan + dual scripts  
출력: `sync_bundle_<version>.json`

### 5.5 SceneRunner + SceneQualityGate
입력: sync bundle, scene assets  
출력: `scene_gate_report.json` 및 실패 씬 증거 디렉터리

### 5.6 VersionAssembler
출력: `final_showcase.<version>.<lang>.mp4` (`lang=ko,en`)

### 5.7 PromoPromptStudio
출력:
- `thumbnail_prompt_nanobanana_pro.md`
- `youtube_description_prompt.md`
- `project_overview_doc_prompt.md`
- `ppt_slide_prompt_gemini.md`

## 6. 데이터 흐름

`coverage -> scene_plan -> dual_script(ko/en) -> sync_bundle -> scene_runner(loop) -> version_assemble -> final_validate -> promo_prompts`

핵심은 씬 단위 루프이며, 합격 씬만 다음 씬으로 이동한다.

## 7. 품질 게이트

### 7.1 씬 게이트
- `scene_av_boundary_delta_sec <= 0.15`
- `scene_caption_voice_end_delta_sec <= 0.10`
- `action_execution_rate >= 0.95`
- `static_frame_ratio <= 0.35`
- `en` 한글 오염률 임계 초과 시 fail

### 7.2 버전 게이트
- 모든 씬 pass
- 캡션/보이스/렌더 종료 정합 유지
- 용어 감사 `ERROR=0`
- `ko/en` 결과물 모두 존재

### 7.3 전체 게이트
- `short/normal/detail` 전부 pass
- 런타임 120분 내
- 홍보 프롬프트 md 세트 완성

## 8. 실패/복구 정책

- 실패 씬은 `scene_failures/<version>/<scene_id>/`에 로그/스냅샷/비디오 저장
- 전체 파이프라인 재시작 금지, 실패 씬만 국소 재처리
- 3회 실패 누적 시 `manual_review_required`로 승격

## 9. 산출물 구조

### 9.1 시나리오/싱크
- `project/video/scenarios/scene_plan_short.json`
- `project/video/scenarios/scene_plan_normal.json`
- `project/video/scenarios/scene_plan_detail.json`
- `project/video/scenarios/sync_bundle_short.json`
- `project/video/scenarios/sync_bundle_normal.json`
- `project/video/scenarios/sync_bundle_detail.json`
- `project/video/scenarios/script_short.ko.md`
- `project/video/scenarios/script_short.en.md`
- (normal/detail 동일 패턴)

### 9.2 증거
- `project/video/evidence/scene_gate_report.json`
- `project/video/evidence/version_gate_report.json`
- `project/video/evidence/runtime_budget_report.json`

### 9.3 최종 영상
- `project/out/final_showcase.short.ko.mp4`, `.en.mp4`
- `project/out/final_showcase.normal.ko.mp4`, `.en.mp4`
- `project/out/final_showcase.detail.ko.mp4`, `.en.mp4`

### 9.4 홍보 프롬프트
- `project/video/assets/thumbnail_prompt_nanobanana_pro.md`
- `project/video/assets/youtube_description_prompt.md`
- `project/video/assets/project_overview_doc_prompt.md`
- `project/video/assets/ppt_slide_prompt_gemini.md`

## 10. 스킬 구조 개선 방향

- `psk-showcase-scenario-orchestrator`: 씬/싱크/게이트 중심으로 계약 강화
- `psk-promo-asset-studio`: 프롬프트 md 4종 생성 계약 강화
- 각 `SKILL.md`에 시스템 프롬프트 규칙(톤/형식/금지어/검증 기준) 명시

## 11. 수용 기준(DoD)

- 3버전 × 2언어 결과물 생성
- 씬 게이트 임계값 충족
- `en` 대본 한국어 오염 없음
- 씬 실패 국소 재처리 루프 동작
- 홍보 프롬프트 md 4종 생성 완료
