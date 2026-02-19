# project-showcase-kit 화면녹화/TTS/자막 동기화 하드닝 설계서

기준일: 2026-02-19

## 1. 목표
- `project-showcase-kit`에서 다음 문제를 구조적으로 해결한다.
- 실제 화면 녹화가 되지 않고 placeholder 영상만 생성되는 문제
- TTS + 자막 생성 실패/품질 저하 문제
- TTS/자막이 영상 길이보다 먼저 끝나거나 잘리는 문제
- 산출물이 `project` 경계를 벗어나 생성되는 문제
- 언어/스피커 정책 및 운영 문서(QUICK_START, STEP, checklist) 불일치 문제

## 2. 범위
- 대상 루트: `/Users/freelife/vibe/lecture/hodu/closing-bet-demo/project`
- 대상 패키지: `/Users/freelife/vibe/lecture/hodu/closing-bet-demo/project/project-showcase-kit`
- 대상 stage: `manifest`, `record`, `voice`, `captions`, `render`, `validate` 및 오케스트레이터(`run_stage.sh`, `run_all.sh`, `manager_cycle.sh`)
- 테스트: 단위 테스트 우선 통과 후 통합 테스트 반복
- 문서: `project/jobs/*.md`, `project/checklist/*.md` 보완

## 3. 비목표
- 파이프라인 전체 재작성(아키텍처 전면 교체)
- 새로운 외부 오케스트레이터 도입
- 기존 복원 범위 밖 stage의 기능 확장

## 4. 설계 원칙
- 점진 리팩터 방식으로 기존 stage 체인을 유지하며 정확성 강화
- 모든 출력 경로는 `project` 하위로 강제
- 실패는 조기에 감지하고 증거를 남긴다(Fail Fast + Evidence)
- 언어/스피커/동기화 규칙은 중앙 함수에서 단일 관리
- 테스트로 계약을 먼저 고정한 뒤 구현한다(TDD)

## 5. 아키텍처 개요
### 5.1 경로 경계
- 공통 경로 변수:
- `PROJECT_ROOT=/Users/freelife/vibe/lecture/hodu/closing-bet-demo/project`
- `KIT_ROOT=/Users/freelife/vibe/lecture/hodu/closing-bet-demo/project/project-showcase-kit`
- `OUT_ROOT=${PROJECT_ROOT}/out`
- 경계 검증 함수 도입:
- 모든 입력/출력 경로는 `PROJECT_ROOT` 하위인지 검사
- 경계 밖 경로는 즉시 실패

### 5.2 stage 체인(유지 + 강화)
- 기존 체인 유지: `manifest -> preflight -> sync-policy -> record -> voice -> captions -> render -> assets -> validate -> manager-report -> quality-report -> qc`
- 핵심 강화:
- `record`: Playwright 기반 실제 녹화
- `voice`: 언어별 speaker 매핑 및 멀티 산출물
- `captions`: 음성 길이 기준 타임라인 스케일 조정
- `render`: 음성/자막/씬 길이 최대값 이상으로 출력 길이 보장
- `validate`: 언어별 산출물 + 동기화 + 경로 경계 검증

## 6. 기능 설계
### 6.1 시나리오/대본(manifest) 계약
- scene 필수 필드:
- `id`, `title`, `durationSec`, `url`, `actions[]`, `narrationByLang`
- 기본 언어: `ko+en`
- 추가 옵션 언어: `ja`, `zh`
- 단일 생성: `ko`만 또는 `en`만 허용
- 내부 표준화: `target_languages` 리스트 생성 후 후속 stage 공용 사용

### 6.2 화면 녹화(record)
- Playwright를 사용해 scene별 브라우저 녹화 수행
- scene 처리 순서:
- `url` 진입 -> `actions[]` 실행 -> scene clip 저장
- 산출물:
- `${PROJECT_ROOT}/video/scenes/<scene-id>.mp4`
- `${PROJECT_ROOT}/video/evidence/record_summary.json`
- 실패 증거:
- 실패 scene id 목록, 에러 메시지, 스크린샷, trace 경로 기록

### 6.3 TTS(voice)
- 언어별로 개별 음성 생성:
- `${PROJECT_ROOT}/out/audio/narration.<lang>.wav`
- `${PROJECT_ROOT}/out/audio/narration.<lang>.json`
- speaker 매핑(고정):
- `ko -> Sohee`
- `en -> Serena`
- `ja -> Ono_Anna`
- `zh -> Vivian`
- 기타 -> `Vivian`
- 기본 모드:
- strict TTS를 기본으로 두고, fallback은 명시 옵션에서만 허용

### 6.4 자막(captions)
- 언어별 자막 생성:
- `${PROJECT_ROOT}/out/captions/subtitles.<lang>.srt`
- `${PROJECT_ROOT}/out/captions/subtitles.<lang>.json`
- 동기화 규칙:
- `audioDuration`을 기준으로 scene 타임라인을 스케일
- `lastCaptionEnd >= audioDuration` 보장(허용 오차 포함)
- 마지막 cue drift 방지용 정규화 적용

### 6.5 렌더(render)
- 언어별 최종 영상 생성:
- `${PROJECT_ROOT}/out/final_showcase.<lang>.mp4`
- 대표 영상:
- `${PROJECT_ROOT}/out/final_showcase.mp4` (첫 언어 산출물 복사/링크)
- 출력 길이 규칙:
- `renderDuration >= max(sceneTotal, audioDuration, captionsEnd)`

### 6.6 검증(validate)
- 필수 검증:
- 경로 경계 준수
- 기본 산출물 존재
- 언어별 추가 산출물 존재
- `caption_covers_voice`
- `render_covers_voice`
- 결과:
- `${PROJECT_ROOT}/video/evidence/validation_report.json|md`

## 7. 데이터 플로우
1. `manifest`가 scene/url/actions/narrationByLang를 생성
2. `record`가 scene mp4와 evidence를 생성
3. `voice`가 언어별 wav/meta를 생성(스피커 매핑 포함)
4. `captions`가 언어별 srt/json을 생성하고 길이 정합
5. `render`가 언어별 final mp4 생성
6. `validate`가 존재성/동기화/경계 정책을 판정

## 8. 오류 처리 정책
- `record`: scene 하나라도 실패 시 stage 실패
- `voice`: strict 모드에서 엔진 실패 시 stage 실패
- `captions`: 길이 정합 실패 시 stage 실패
- `render`: 길이 규칙 위반 시 stage 실패
- `path guard`: 경계 밖 출력 감지 즉시 실패

## 9. 테스트 전략
### 9.1 단위 테스트(선행)
- 언어 파싱/기본값/단일 생성/확장 생성
- speaker 매핑 함수
- 경로 경계 검증 함수
- captions 타임라인 스케일 로직
- render 길이 계산 로직
- record action 파서/실패 증거 기록

### 9.2 통합 테스트(반복)
- 기본: `ko+en`
- 단일: `ko`, `en`
- 확장: `ko+en+ja+zh`
- 각 케이스별 `record->voice->captions->render->validate` 검증
- 최소 2회 반복으로 flaky 여부 점검

## 10. 문서 보완 범위
- `project/jobs/QUICK_START.md`
- 언어/스피커/옵션 설정 위치 정리
- 기본/단일/확장 실행 예시
- 실패 원인/대응(Playwright/TTS/동기화) 추가
- `project/jobs/STEP1~STEP5.md`
- 단위 테스트 선행 + 통합 반복 절차 강화
- `project/checklist/1. Production_Workflow.md`
- 언어별 speaker 및 `project/out` 산출물 검증 항목 추가
- `project/checklist/2. Candidate_Decisions.md`
- 기본언어/추가언어/단일 생성 정책 확정 반영

## 11. 완료 기준(Definition of Done)
- 단위 테스트 전부 통과
- 통합 테스트 시나리오 전부 통과
- `validation_report.status == pass`
- 언어/스피커/길이 동기화/경로 경계 조건 모두 만족
- QUICK_START/STEP/checklist가 실제 코드 동작과 일치
