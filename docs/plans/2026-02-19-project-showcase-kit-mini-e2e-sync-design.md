# project-showcase-kit mini E2E 실행/검증/문서개선 설계

- 날짜: 2026-02-19
- 범위: `mini` 프로파일 1회 실실행 + 문제 수정/개선 + TTS/자막 싱크 정밀 검증 + 사용자 문서 보완

## 1. 목표

1. `project/jobs/QUICK_START.md` 기준으로 `project-showcase-kit` 파이프라인을 실제 실행해 소개영상 산출물을 만든다.
2. 단계별 산출물과 Gate(B/C/D), validation 결과를 근거 기반으로 검증한다.
3. 시나리오/대본 길이 대비 TTS+자막 싱크를 정량 기준으로 점검한다.
4. 범용 툴로 분리 배포하기 위한 부족한 부분을 통합테스트/문서/검증 로직 관점에서 보완한다.

## 2. 성공 기준

- 최종 영상 파일 생성: `project/project-showcase-kit/out/final_showcase.mp4`
- Gate C 및 validate 핵심 체크 통과
- 싱크 기준(실무):
  - 전체 길이 오차(오디오 vs 영상) `<= 0.5초`
  - 씬 경계 정렬 `100%` (`sceneBoundaryAlignedAll == true`)
  - 문장(자막 segment) 단위 최대 오차 `<= 1.0초`
- 재사용 가능한 검증 강화(테스트 또는 검증 스크립트) 최소 1건 이상 반영
- QUICK_START/STEP/checklist 문서를 실사용자 중심으로 개선

## 3. 아키텍처/실행 흐름

1. 사전 준비
- 가상환경/의존성/Playwright 브라우저 설치
- 서비스 헬스 체크 및 자동 기동

2. 파이프라인 실행
- `run_all.sh --profile mini --manifest ... --yes`
- 실패 시 전체 재시작 금지, 실패 stage만 재실행

3. 품질/싱크 검증
- Gate C 리뷰(`build_gate_c_review.py`) + 전체 validate(`validate_outputs.py`)
- 언어별 메타(`narration.json`, `subtitles.json`)를 이용한 정밀 싱크 감사 추가

4. 개선 반영
- 문제 원인별 코드 수정
- stage 재실행/재검증으로 회귀 확인

5. 범용화 관점 보강
- 통합테스트 보강
- 실행 문서/체크리스트 가독성 및 복붙 실행성 개선

## 4. 컴포넌트 책임

- 오케스트레이션: `project/project-showcase-kit/scripts/pipeline/run_all.sh`
- stage 어댑터: `project/project-showcase-kit/scripts/pipeline/run_stage.sh`
- Gate C 품질 리포트: `project/project-showcase-kit/scripts/pipeline/build_gate_c_review.py`
- 종합 validate: `project/project-showcase-kit/scripts/pipeline/validate_outputs.py`
- TTS 동기화 엔진: `project/project-showcase-kit/scripts/video/gen_voice.py`
- 자막 생성/동기화: `project/project-showcase-kit/scripts/video/gen_captions.py`

## 5. 검증 전략

### 5.1 실행 검증
- preflight 통과
- record/voice/captions/render/validate 전 단계 실행 확인
- 단계별 증적 파일 생성 여부 확인

### 5.2 싱크 정밀 검증
- 언어별 오디오 길이/타겟 길이/영상 길이 비교
- 언어별 씬 경계 정렬 여부
- 자막 segment 단위 타임라인 오차 측정

### 5.3 회귀 검증
- 문제 수정 후 실패 stage 우선 재실행
- 최종적으로 Gate C/validate 재통과 확인
- 통합테스트를 통해 동일 결함 재발 방지

## 6. 문서 UX 개선 원칙

- 초심자 기준 순서화: "처음 실행" -> "실패 시" -> "재실행"
- 명령은 복붙 가능한 완성형으로 제공
- 각 단계마다 "성공 확인 방법(파일/로그/판정 기준)" 명시
- 경로/변수 설명을 최소 개념으로 정리
- TTS/자막 싱크 기준을 숫자로 명시

## 7. 리스크 및 대응

- 환경 의존성(노드/파이썬/ffmpeg/Playwright): preflight 강화 및 오류 메시지 개선
- TTS 엔진 가용성 편차: fallback 경로 및 strict 모드 동작 명확화
- 다국어 처리 시 파일 누락: 언어별 출력/메타 존재성 검증 강화
- 휴리스틱 자막 품질 편차: 문장 단위 오차 검증 + 수동 Gate 기준 문서화

## 8. 산출물

- 실제 영상 및 증적:
  - `project/project-showcase-kit/out/final_showcase.mp4`
  - `project/video/evidence/*.json`
  - `project/video/evidence/*.md`
- 코드 개선:
  - 파이프라인/검증 스크립트 보완
  - 통합테스트 보강
- 문서 개선:
  - `project/jobs/QUICK_START.md`
  - `project/jobs/STEP1.md` ~ `project/jobs/STEP5.md`
  - `project/checklist/*.md`

## 9. 범용화 개선 제안(초안)

1. 검증 기준 프로파일화
- strict/practical/relaxed preset을 옵션화해 프로젝트별 목표에 맞게 사용 가능하도록 확장

2. 싱크 감사기 독립 모듈화
- 오디오/자막/영상 메타를 입력으로 받는 독립 `sync_audit` 모듈 제공

3. 증적 스키마 고정
- `record_summary`, `gate_c_review`, `validation_report` JSON schema를 명시해 외부 통합을 쉽게 함

4. 문서 생성 자동화
- 실행 후 체크리스트 충족 상태를 자동으로 요약해 사용자 안내 문서로 출력

