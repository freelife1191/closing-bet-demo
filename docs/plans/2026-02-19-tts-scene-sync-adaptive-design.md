# TTS-Scene Sync Adaptive 설계

- 날짜: 2026-02-19
- 요청 배경: 화면 전환보다 TTS+자막이 늦어지는 체감 불일치 발생
- 우선순위: 혼합 전략(속도/대본 우선 + 초과분만 화면 유지), 한국어 기준 타임라인, 영상 길이 유연

## 1. 목표

1. 화면 전환 시점과 TTS/자막 시점을 장면 단위로 정합시킨다.
2. 시나리오/대본 설계 단계에서 미리 속도/길이 초과를 계산한다.
3. 작은 반복 테스트로 싱크 지표를 안정적으로 통과할 때까지 조정한다.

## 2. 성공 기준

- 한국어 기준으로 "다음 화면인데 이전 대사" 체감이 발생하지 않는다.
- Gate C, sync-audit, validate 모두 pass.
- 정량 기준:
  - 오디오 vs 영상 길이 오차 `<= 0.5s`
  - scene 경계 정렬 `100%`
  - cue 문장 오차 `<= 1.0s`
  - scene 단위 `speech_end <= scene_end + tolerance`

## 3. 선택한 전략 (혼합 적응형)

1. 시나리오/manifest 단계에서 scene별 길이 대비 대본 부담을 계산한다.
2. scene별 권장 TTS 속도를 먼저 적용한다.
3. 여전히 초과하는 scene만 제한적으로 scene 길이를 연장한다.
4. 한국어(`ko`)를 기준 타임라인으로 렌더와 자막 정렬을 맞춘다.

## 4. 컴포넌트 변경 대상

- `project/project-showcase-kit/scripts/video/build_manifest.py`
  - `estimatedNarrationSec`, `sceneTtsSpeedFactor`, `overflowSec`, `narrationPolicy` 생성
- `project/project-showcase-kit/scripts/video/gen_voice.py`
  - 전역 retime 중심에서 scene 단위 보정/메타 확장
  - `sceneAudioRanges`, `sceneAppliedSpeedFactor` 출력
- `project/project-showcase-kit/scripts/video/gen_captions.py`
  - scene 경계 기준 cue 분할/재배치
  - `maxCueSceneDeltaSec`, `cueOverflowCount` 출력
- `project/project-showcase-kit/scripts/video/render_video.ts`
  - 조정된 scene duration으로 `Sequence.durationInFrames` 구성
- `project/project-showcase-kit/scripts/pipeline/audit_sync_detail.py`
  - scene별 `speech_end vs scene_end` 검증 강화

## 5. 데이터 흐름

1. `manifest`
- 입력: scene target sec, 대본
- 계산: `estimatedNarrationSec`, `requiredSpeed`, `overflowSec`
- 정책: 속도 보정 가능/대본 압축 필요/scene 연장 필요 분기

2. `voice`
- scene별 합성 -> 실제 duration 측정
- `sceneAudioRanges` 생성

3. `captions`
- ASR cue를 `sceneAudioRanges`에 매핑
- 경계 초과 cue 분할/재타임

4. `render`
- scene duration을 조정 타임라인 기준으로 적용

5. `validate/sync-audit`
- 전체 길이 통과 + scene 단위 정합 동시 검사

## 6. 작게 반복하는 테스트 전략

1. 단위 테스트
- 길이 추정/속도 추천/overflow 계산
- cue scene 매핑/분할 함수

2. 소형 통합 테스트(2~3 scene fixture)
- 속도만으로 해결 케이스
- 대본 압축 필요 케이스
- scene 연장 필요 케이스

3. 실파이프라인 반복
- `manifest -> voice -> captions -> sync-audit` 반복
- 기준 충족 후 `render -> validate -> qc`

## 7. 에러 처리 정책

- 실패 리포트에 scene별 초과량을 직접 표기
- 자동 조치 힌트 제공:
  - 권장 압축률
  - 권장 speed factor
  - 권장 scene 연장 sec

## 8. 출력 계약(강화)

- `manifest.json`
  - `sceneTtsSpeedFactor`, `estimatedNarrationSec`, `overflowSec`, `narrationPolicy`
- `narration.json`
  - `sceneAudioRanges`, `sceneAppliedSpeedFactor`
- `subtitles.json`
  - `maxCueSceneDeltaSec`, `cueOverflowCount`
- `sync_audit_report.json`
  - scene별 상세 오차 테이블

## 9. 문서/운영 반영

- `project/jobs/QUICK_START.md`
  - 싱크 튜닝 루프 섹션 추가
- `project/jobs/STEP4.md`
  - 신규 출력 계약 필드 명시
- `project/jobs/STEP5.md`
  - scene 늦음 장애 대응 패턴 추가
- checklist
  - scene 단위 싱크 항목 추가

## 10. 범용화 제안

1. 정책 프리셋
- `speech_first` / `balanced` / `timing_strict`

2. 언어 정책
- 한국어 우선 기준 타임라인 + 다국어 보조 적용

3. 프로젝트별 오버라이드
- 기준값을 config 파일로 분리해 재사용성 강화
