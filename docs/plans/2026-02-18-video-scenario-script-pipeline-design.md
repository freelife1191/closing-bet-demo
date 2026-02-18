# 2026-02-18 영상 시나리오·대본·파이프라인 설계

## 1. 문서 목적
- `project-showcase-kit` 기반 영상 제작에서 시나리오/대본 품질 저하, TTS 이상음, 자막 싱크 문제, Remotion 미적용 문제를 구조적으로 해결한다.
- 프로젝트 기능 전체를 누락 없이 소개하는 3가지 버전(간소화/보통/디테일) 영상 제작 기준을 고정한다.
- 단계별 사용자 검토 게이트를 포함해 재작업 가능한 운영 절차를 표준화한다.

## 2. 입력 근거 및 분석 범위
- 필수 문서: `README.md`, `CLAUDE.md`, `AGENTS.md`
- 코드 근거:
  - 백엔드 라우트: `app/routes/common.py`, `app/routes/kr_market.py`
  - 프론트 라우트/페이지: `frontend/src/app/**/page.tsx`
  - 파이프라인: `project/project-showcase-kit/scripts/pipeline/*`, `project/project-showcase-kit/scripts/video/*`
- 확인 결과:
  - `GEMINI.md`는 현재 저장소에 없음(감사 항목으로 기록)
  - 기존 산출물에서 `manifest`와 `record_summary` 씬 수 불일치 이력 존재
  - `render.log`에 Remotion 미구성으로 skip된 이력 존재

## 3. 핵심 문제 정의
- 시나리오/대본이 기능 커버리지를 보장하지 못해 영상, TTS, 자막 품질이 함께 하락함
- `silence fallback` 또는 짧은 음성으로도 단계가 통과되어 품질 실패를 가리는 구조가 있음
- 썸네일 생성이 텍스트 품질 검증 없이 통과되어 결과가 불안정함
- Remotion이 필수 경로가 아니라 선택 경로로 처리되어 후반 편집 표준이 붕괴됨

## 4. 설계 원칙
- 근거 중심: README/코드에 없는 기능 설명 금지
- 단일 진실원천: 기능 매트릭스 기반 씬 설계
- 검증 우선: 각 stage는 증거 파일 없으면 실패 처리
- 부분 재실행: 실패 범위만 최소 재실행
- 사람 승인 게이트: 자동화와 사용자 검토를 분리

## 5. 버전 프로파일(확정)
- 간소화: 55~60초
- 보통: 90~120초
- 디테일: 180~240초

## 6. 기능 커버리지 마스터 씬
- S01 제품 미션/핵심 가치/AI 하이브리드
- S02 아키텍처 및 데이터 소스 우선순위
- S03 Overview: Market Gate/섹터/글로벌 지표
- S04 Overview KPI: VCP/종가베팅 성과와 자동 갱신
- S05 VCP 시그널 리스트 및 필터
- S06 VCP 상세 차트/AI 탭/상담
- S07 VCP 스크리너 실행/상태/권한
- S08 종가베팅 전략 메인
- S09 종가베팅 카드/AI 리포트/점수 체계
- S10 종가베팅 종목 상세 모달(재무/수급/안전성)
- S11 누적 성과 KPI
- S12 누적 성과 상세 표/분포/등급 분석
- S13 데이터 상태 및 업데이트 파이프라인
- S14 설정/알림/관리자/쿼터
- S15 모의투자(포트폴리오/거래/차트/주문)
- S16 AI 상담(세션/모델/명령어/추천질문)
- S17 스케줄러/알림 자동화(15:20, 15:40)
- S18 요약/면책/CTA

## 7. 버전별 씬 구성
- 간소화: S01, S03, S05, S08, S11, S16, S18
- 보통: S01~S06, S08~S09, S11~S12, S16, S18
- 디테일: S01~S18 전체

## 8. 시나리오/대본 규격
- 씬 필수 필드:
  - `scene_id`, `route`, `feature_refs`, `demo_actions`, `must_show_ui`
  - `narration_ko`, `narration_en`(확장 언어는 동적 추가)
  - `target_sec`, `min_sec`, `max_sec`
  - `acceptance_criteria`
- 대본 규칙:
  - 씬마다 `기능 설명 + 실제 조작 + 의미` 3요소 포함
  - 디테일 버전은 모든 씬에 실제 시연 동작 포함
  - 과장/투자확정 표현 금지, 면책 문구 고정

## 9. 다국어 TTS/자막 설계
- 기본 의무: `ko`, `en` 동시 생성
- 확장: 설정으로 `ja` 및 임의 언어 추가
- 산출 구조:
  - 대본: `script_<lang>.md`
  - 음성: `narration_<lang>.wav`, `narration_<lang>.json`
  - 자막: `subtitles_<lang>.srt`, `subtitles_<lang>.json`
- 품질 정책:
  - 기본 모드에서 `silence fallback` 금지
  - 음성 길이/문자수/무음 비율 임계치 검증
  - 자막 cue 경계와 씬 경계 동기화 검증

## 10. 오케스트레이션 설계(공식 Remotion 스킬 반영)

### 10.1 적용 전략
- 기존 `psk` 파이프라인은 `preflight~captions` 및 검증/게이트 담당으로 유지한다.
- `render` 단계는 공식 Remotion 스킬(`https://github.com/remotion-dev/skills`)을 우선 사용한다.
- 즉, **하이브리드 구조**:
  - Orchestration/Gate/Validation: `psk-video-orchestration-manager` 체계
  - Final Composition: 공식 Remotion 스킬 체계

### 10.2 정책
- `strict_remotion=true`:
  - Remotion 미설치/미구성/렌더 실패 시 즉시 실패
  - ffmpeg fallback은 최종본 승인 경로로 인정하지 않음
- `strict_remotion=false`:
  - 긴급 미리보기 용도로만 ffmpeg fallback 허용

### 10.3 단계
- Stage A: preflight
- Stage B: manifest/script
- Stage C: scene record
- Stage D: multilingual voice/captions
- Stage E: Remotion render(공식 스킬)
- Stage F: assets(썸네일/카피)
- Stage G: validate/manager-report/quality-report
- Stage H: qc signoff

## 11. 썸네일 품질 설계
- 프롬프트 3안 + 네거티브 프롬프트 고정
- 텍스트 검증:
  - 타이틀/서브타이틀 정확 일치
  - 글자 깨짐/오탈자/잘림 검출 시 실패
- 실패 시 프롬프트 변형 A/B 재생성 루프 적용

## 12. 승인 게이트(확정)
- Gate A: 공통 시나리오/대본 1회 승인(선행)
- Gate B: 씬 커버리지/화면 시연 승인
- Gate C: 언어별 TTS/자막 싱크 승인
- Gate D: 버전별 최종본 승인

## 13. 자동 검증 지표
- Scene completeness: manifest 씬 수 = 실제 녹화 씬 수
- Feature coverage: 기능 매트릭스 누락 0
- Audio integrity: 무음 fallback 금지, 길이/무음 비율 기준 통과
- Caption integrity: cue 수, 씬 경계 일치, 언어별 파일 존재
- Duration budget: 각 버전 목표 길이 범위 충족
- Render policy: strict 모드에서 Remotion 산출물 필수

## 14. 실패 복구 전략
- record 실패: 실패한 scene만 재녹화
- voice/captions 실패: 해당 언어만 재생성
- render 실패: 원인 분류 후 render 이전 최소 단계만 재실행
- assets 실패: 썸네일/카피 단계만 재실행
- 모든 실패는 `project/video/evidence/*`에 기록

## 15. 운영 절차
1. 기능 매트릭스 갱신
2. 공통 시나리오/대본 작성
3. Gate A 승인
4. 버전별 manifest 생성
5. scene/voice/captions/render 실행
6. validate + manager + quality 보고서 생성
7. Gate B/C/D 승인
8. 릴리즈

## 16. 완료 기준(Definition of Done)
- 3버전 영상 길이 기준 충족
- `ko`, `en` TTS/자막 정상 생성(추가 언어 확장 가능)
- 기능 커버리지 누락 0
- strict 모드 기준 Remotion 최종 렌더 성공
- 썸네일 텍스트 품질 검증 통과
- validation/manager/signoff 증거 완비

## 17. 잔여 리스크
- 환경별 ffmpeg 필터/폰트 차이로 자막 번인 품질 편차 가능
- 외부 API(TTS/시장데이터) 일시 장애 시 일부 재시도 필요
- `GEMINI.md` 부재로 문서 커버리지 불완전(코드/README 기준으로 보완)

## 18. 다음 단계
- 본 설계를 기준으로 구현 작업 계획 문서(`writing-plans`)를 작성한다.
