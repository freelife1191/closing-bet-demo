# STEP4 - 구현 설계(패키지/스킬/스크립트 계약)

## 1) 구현 원칙
- 자동화는 `재시도 가능`해야 한다. (실패 씬만 재실행)
- 모든 단계는 입력/출력 경로가 고정되어야 한다.
- 모델 결과물은 항상 사람 승인 게이트를 거친다.
- 불확실 API 대신 공개 문서가 있는 도구를 우선 사용한다.

## 2) 패키지 추천(승인 후보)
아래는 후보 목록이다. 정식 채택은 `project/checklist/2. Candidate_Decisions.md`에서 승인 후 진행.
주의: Playwright/브라우저 호환성과 로컬 TTS 런타임(ONNX/모델 파일) 경로 관리를 위해 버전 고정이 필요하다.

### 2.1 Node/TS
- 녹화 자동화(권장): `playwright`, `@playwright/test`
- 편집(권장): `remotion`, `@remotion/captions`
- 실행 편의: `tsx`, `zod`, `dotenv`

### 2.2 Python
- 자막(권장): `faster-whisper` 또는 `openai-whisper`
- 자막 포맷 처리: `srt`
- 오디오 후처리: `pydub`, `soundfile`
- API 호출: `requests`
- TTS(기본): Qwen (로컬 cmd 또는 cloud API)
- TTS(fallback): Supertonic 로컬 ONNX, Google TTS

### 2.3 시스템
- 필수: `ffmpeg`

### 2.4 설치 커맨드 예시(승인 후 실행)
1. 프론트 워크스페이스 기준(Node)
```bash
# Node 22 LTS 권장
cd frontend
npm install
npm install -D playwright @playwright/test tsx zod dotenv
npm install remotion @remotion/captions
npx playwright install chromium
```

2. Python 환경
```bash
# Python 3.11+ venv 권장
python3.11 -m venv venv311
source venv311/bin/activate
pip install -r requirements.txt
pip install faster-whisper srt pydub soundfile requests
```

3. 환경 변수(.env)
```bash
# 로컬 TTS 기본
SUPERTONIC_ROOT=/path/to/supertonic
# 선택
SUPERTONIC_VOICE_STYLE=assets/voice_styles/F1.json
SUPERTONIC_TOTAL_STEP=5
SUPERTONIC_SPEED=1.05
# 클라우드 API 엔진을 쓸 때만 키 설정
# DASHSCOPE_API_KEY=...
# GOOGLE_API_KEY=...
# SUPERTONE_API_KEY=...
```

4. 로컬 확인
```bash
node -v
python3 --version
ffmpeg -version
```

## 3) 스크립트 계약(Contract)
현재 구현 상태: 아래 스크립트가 `scripts/video/`에 생성되어 있으며, 프로젝트 특화 로직(selector/tone/model)은 추가 튜닝이 필요하다.

### 3.1 `scripts/video/build_manifest.py`
- 입력: 프로젝트 경로, 목표 길이(초), 언어, 스타일
- 출력: `project/video/manifest.json`
- 조건: 길이 미지정(`auto`) 시 프로젝트 설명에 충분한 길이를 자동 추정, 지정 시 목표 길이 준수 계획 생성

### 3.2 `scripts/video/record_scenes.ts`
- 입력: `manifest.json`, 브라우저 옵션(headless/headed), 재시도 횟수
- 출력: `project/video/scenes/*.mp4`, 실패 로그, 실패 시 스크린샷
- 조건: 씬 단위 성공/실패 코드 리턴

### 3.3 `scripts/video/gen_voice.py`
- 입력: 대본, 엔진 선택(qwen/qwen-local-cmd/supertonic-local/google/auto), 발음 사전, 로컬 TTS 경로
- 출력: `project/video/audio/narration.wav`
- 조건: 음성 길이와 씬 총 길이 편차 리포트 생성

### 3.4 `scripts/video/qwen_local_tts_runner.py`
- 입력: `--input`(text file), `--output`(audio), provider command template
- 출력: 정규화된 wav + runner 메타데이터
- 조건: `QWEN_LOCAL_CMD`의 고정 인터페이스 유지

### 3.5 `scripts/pipeline/run_stage.sh`
- 입력: stage 이름(preflight/manifest/record/voice/captions/render/assets/validate/manager-report/quality-report/qc), 공통 옵션
- 출력: 단계별 산출물/로그
- 조건: stage 실패 시 non-zero 종료

### 3.6 `scripts/pipeline/run_all.sh`
- 입력: 전체 파이프라인 옵션
- 출력: Gate A~D 승인 흐름 + 최종 signoff
- 조건: Gate 반려 시 즉시 중단

### 3.7 `scripts/pipeline/rerun_failed.sh`
- 입력: `record_summary.json`
- 출력: 실패 씬만 재녹화
- 조건: 실패 씬이 없으면 종료 코드 0

### 3.8 `scripts/pipeline/ensure_services.sh`
- 입력: frontend/backend 포트, 대기 시간
- 출력: 서비스 헬스(기본 `127.0.0.1:3500`, `127.0.0.1:5501/health`) 보장
- 조건: 다운 상태면 자동 기동 후 타임아웃 내 정상 응답이 없으면 실패

### 3.9 `scripts/pipeline/manager_cycle.sh`
- 입력: `run_all.sh` 인자 동일
- 출력: 전체 실행 + `manager_report` + `quality_research`
- 조건: 액션 필요 상태면 non-zero 종료

### 3.10 `scripts/pipeline/build_manager_report.py`
- 입력: validation/record_summary/signoff
- 출력: `manager_report.json`, `manager_report.md`
- 조건: 이슈가 있으면 `needs_action`

### 3.11 `scripts/pipeline/write_quality_research.py`
- 입력: validation/manager_report/audio metadata
- 출력: `quality_research.md`
- 조건: must-fix / nice-to-have 분리

### 3.12 `scripts/video/gen_captions.py`
- 입력: 오디오, 대본(선택), 언어
- 출력: `project/video/captions/subtitles.srt`, `project/video/captions/subtitles.json`
- 조건: SRT 포맷 검증 + 샘플 타임코드 로그

### 3.13 `scripts/video/render_video.ts`
- 입력: `manifest.json`, 영상/오디오/자막 경로
- 출력: `out/final_showcase.mp4`
- 조건: 실패 시 ffmpeg 폴백 경로 실행

### 3.14 `scripts/video/gen_promo_assets.py`
- 입력: 제품 핵심 메시지, 썸네일 프롬프트 템플릿, 썸네일 모드(manual/placeholder/both)
- 출력: `thumbnail_prompt.md`, `thumbnail_preview.png`, `copy.md`, `release_notes.md`, `promo_brief.md`, `promo_deck.pptx`(+ fallback)
- 조건: 한글 텍스트 렌더 품질은 자동 확정하지 않고 3안 비교 후 사람 승인

## 4) 권장 Agent Skills(신규)
아래 스킬은 `.agent/skills/`에 생성해 둔다.

1. `psk-video-manifest-planner`
- 역할: 코드/README 기반 씬 설계와 대본 생성
- 산출물: `manifest.json`, `script.md`

2. `psk-playwright-scene-recorder`
- 역할: 씬 자동 조작/녹화/재시도
- 산출물: 씬별 mp4, 실패 스크린샷, trace

3. `psk-video-postproduction-remotion`
- 역할: Remotion props 생성 및 최종 렌더
- 산출물: `out/final_showcase.mp4`

4. `psk-video-qc-gatekeeper`
- 역할: 승인 게이트 체크 및 증적 파일 수집
- 산출물: `project/video/evidence/signoff.md`, `project/video/evidence/signoff.json`

5. `psk-video-orchestration-manager`
- 역할: 단계 오케스트레이션, 실패 루프 관리, 사용자 승인 요청
- 산출물: `project/video/evidence/manager_report.md`

6. `psk-video-quality-researcher`
- 역할: 품질 지표 분석과 개선안 제시
- 산출물: `project/video/evidence/quality_research.md`

## 5) 인간 개입 최소화 전략
- 로그인은 초기 1회 수동 수행 후 Playwright `storageState` 재사용
- 각 씬 길이를 8~20초로 제한하여 재촬영 비용 최소화
- 음성/자막은 자동 생성 후 샘플 20초만 먼저 검수하고 전체 렌더
- 실패 로그가 없는 자동화는 실패로 처리

## 6) 승인 전 금지 사항
- 미검증 API 시그니처를 코드에 하드코딩 금지
- 라이선스 미확인 TTS 모델을 상용 산출물에 사용 금지
- 컴플라이언스 고지 문구 없이 투자 관련 영상 배포 금지
