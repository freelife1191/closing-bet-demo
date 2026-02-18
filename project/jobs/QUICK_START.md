# QUICK START (Shell Orchestrated)

기준일: `2026-02-18`

목표: 무료/로컬 우선 파이프라인을 Shell 오케스트레이터로 실행.

## 0) 기본 원칙
- 기본 TTS 정책: `Qwen3-TTS 로컬 우선` (`qwen-local-cmd`)
- fallback: `supertonic-local -> google`
- 자막/편집/녹화: `faster-whisper` + `Remotion/ffmpeg` + `Playwright`
- 승인 게이트: A/B/C/D 필수

참고:
- `project/supertonic_readme.md`
- `project/jobs/STEP3.md`
- `project/checklist/1. Production_Workflow.md`

## 1) 사전 입력값
- 길이: `--duration-sec` (예: `auto`, `90`, `180`)
- 씬 수: `--max-scenes` (예: `6`)
- 언어: `--language` (`ko`, `en`, `ko+en`, `multi`)
- TTS 엔진: `--tts-engine` (`auto`, `auto-local`, `qwen`, `qwen-local-cmd`, `supertonic-local`, `google`)
- 썸네일 모드: `--thumbnail-mode` (`manual`, `both`)

TTS 엔진 선택 기준:
- Qwen3 설치 스킬 적용(`QWEN_LOCAL_CMD`가 Qwen3 러너로 설정됨) 시: `auto` 권장
- Qwen 설정이 없고 Google 키만 있으면: `google` 사용
- 로컬 무료 우선이면: `auto-local` (`QWEN_LOCAL_CMD` + `SUPERTONIC_ROOT` 필요)

길이 설정 기준:
- `--duration-sec` 미지정(기본 `auto`): 프로젝트 설명에 충분한 길이를 자동 추정
- `--duration-sec 180` 지정: 3분 이내 목표로 시나리오/대본/씬 길이를 자동 조정

## 2) 최초 1회 설치
```bash
cd /Users/freelife/vibe/lecture/hodu/closing-bet-demo

cd frontend
npm install
npm install -D playwright @playwright/test tsx zod dotenv
npm install remotion @remotion/captions
npx playwright install chromium
cd ..

python3.11 -m venv venv311
source venv311/bin/activate
pip install -r requirements.txt
pip install faster-whisper srt pydub soundfile requests
```

Qwen3-TTS 전용 스킬 기반 설치(범용: macOS/Linux/CPU/GPU):
```bash
bash .agent/skills/qwen3-tts-universal/scripts/install_qwen3_tts.sh \
  --project-root /Users/freelife/vibe/lecture/hodu/closing-bet-demo \
  --venv-path /Users/freelife/vibe/lecture/hodu/closing-bet-demo/.venv-qwen3-tts \
  --default-mode custom_voice \
  --model-size 0.6b \
  --language Auto \
  --speaker Vivian \
  --write-dotenv true
```

Supertonic 로컬 준비(필요 시):
- `project/supertonic_readme.md` 절차대로 별도 디렉토리에 설치
- 예시: `/Users/freelife/tools/supertonic`

## 3) 환경변수(.env) - 로컬/무료 모드
필수(권장):
```bash
SUPERTONIC_ROOT=/Users/freelife/tools/supertonic
```

선택:
```bash
SUPERTONIC_VOICE_STYLE=assets/voice_styles/F1.json
SUPERTONIC_TOTAL_STEP=5
SUPERTONIC_SPEED=1.05
# Qwen3-TTS local runner (기본)
QWEN3_TTS_VENV=/Users/freelife/vibe/lecture/hodu/closing-bet-demo/.venv-qwen3-tts
QWEN3_TTS_DEFAULT_MODE=custom_voice
QWEN3_TTS_MODEL_SIZE=0.6b
QWEN3_TTS_MODEL=Qwen/Qwen3-TTS-12Hz-0.6B-CustomVoice
QWEN3_TTS_LANGUAGE=Auto
QWEN3_TTS_SPEAKER=Vivian
QWEN3_TTS_STYLE_INSTRUCT=
QWEN3_TTS_DEVICE=auto
QWEN3_TTS_DTYPE=auto
QWEN_LOCAL_CMD="/Users/freelife/vibe/lecture/hodu/closing-bet-demo/.venv-qwen3-tts/bin/python /Users/freelife/vibe/lecture/hodu/closing-bet-demo/.agent/skills/qwen3-tts-universal/scripts/qwen3_tts_runner.py --mode custom_voice --input {text_file} --output {output_file} --model-size 0.6b --language Auto --speaker Vivian --device auto --dtype auto"
```

참고:
- 클라우드 TTS(`qwen`, `google`)를 쓸 때만 API 키가 필요
- 무료/로컬 모드(`qwen-local-cmd`, `supertonic-local`)는 API 키 불필요

## 4) 서버 실행
터미널 A:
```bash
cd /Users/freelife/vibe/lecture/hodu/closing-bet-demo/frontend
npm run dev
```

터미널 B:
```bash
cd /Users/freelife/vibe/lecture/hodu/closing-bet-demo
source venv311/bin/activate
python3 flask_app.py
```

검증:
- `http://localhost:3500`
- `http://localhost:5501/health`
- CLI 점검:
```bash
curl -fsS http://127.0.0.1:3500 >/dev/null && echo "frontend ok"
curl -fsS http://127.0.0.1:5501/health >/dev/null && echo "backend ok"
```

## 5) Shell 오케스트레이터 사용법
### 5.0 서비스 상태 자동 보장(권장)
중지 상태면 자동 기동하고 헬스가 준비될 때까지 대기:
```bash
./scripts/pipeline/ensure_services.sh
```

### 5.1 전체 파이프라인 한 번에 실행(권장)
```bash
cd /Users/freelife/vibe/lecture/hodu/closing-bet-demo
./scripts/pipeline/run_all.sh \
  --language ko+en \
  --duration-sec auto \
  --max-scenes 6 \
  --tts-engine auto \
  --thumbnail-mode manual \
  --auto-start-services true
```

Qwen 미설정 환경(예: Google만 설정) 실행:
```bash
./scripts/pipeline/run_all.sh \
  --language ko+en \
  --duration-sec 180 \
  --max-scenes 6 \
  --tts-engine google \
  --thumbnail-mode manual \
  --strict-tts false \
  --auto-start-services true
```

옵션:
- 서버 헬스 체크 생략: `--skip-health`
- fallback 강제 체크 완화: `--strict-tts false`

자동 승인 없이 전부 진행:
```bash
./scripts/pipeline/run_all.sh --yes --tts-engine auto --language ko+en
```

서버 자동기동 포함 사전 점검:
```bash
./scripts/pipeline/run_stage.sh preflight --strict-tts false --auto-start-services true
```

### 5.2 단계별 실행
사전 점검:
```bash
./scripts/pipeline/run_stage.sh preflight --tts-engine auto --auto-start-services true
```

Qwen 미설정 환경 사전 점검(예: Google만 설정):
```bash
./scripts/pipeline/run_stage.sh preflight --tts-engine google --strict-tts false --auto-start-services true
```

Qwen3-TTS 로컬 스모크 테스트:
```bash
bash .agent/skills/qwen3-tts-universal/scripts/smoke_test_qwen3_tts.sh \
  --project-root /Users/freelife/vibe/lecture/hodu/closing-bet-demo \
  --venv-path /Users/freelife/vibe/lecture/hodu/closing-bet-demo/.venv-qwen3-tts \
  --mode all
```

Qwen3-TTS 고급 모드(선택형 옵션) 테스트:
```bash
# Custom Voice (speaker/language/model-size/style)
.venv-qwen3-tts/bin/python .agent/skills/qwen3-tts-universal/scripts/qwen3_tts_runner.py \
  --mode custom_voice --text "옵션 테스트입니다." --output /tmp/custom.wav \
  --model-size 1.7b --speaker Sohee --language Korean --instruct "차분한 뉴스 앵커 톤"

# Voice Design
.venv-qwen3-tts/bin/python .agent/skills/qwen3-tts-universal/scripts/qwen3_tts_runner.py \
  --mode voice_design --text "This is a design test." --output /tmp/design.wav \
  --language English --instruct "Warm, confident female narrator"

# Voice Clone
.venv-qwen3-tts/bin/python .agent/skills/qwen3-tts-universal/scripts/qwen3_tts_runner.py \
  --mode voice_clone --text "클론 테스트 문장입니다." --output /tmp/clone.wav \
  --model-size 0.6b --language Korean --ref-audio /path/to/ref.wav --ref-text "레퍼런스 대본"
```

Manifest:
```bash
./scripts/pipeline/run_stage.sh manifest --language ko+en --duration-sec auto --max-scenes 6
```

녹화:
```bash
./scripts/pipeline/run_stage.sh record --headless false
```

실패 씬만 재녹화:
```bash
./scripts/pipeline/rerun_failed.sh --headless false
```

음성:
```bash
./scripts/pipeline/run_stage.sh voice --tts-engine auto --language ko+en
```

자막:
```bash
./scripts/pipeline/run_stage.sh captions
```

렌더:
```bash
./scripts/pipeline/run_stage.sh render
```

홍보 에셋(문서/프롬프트/이미지/PPT 포함):
```bash
./scripts/pipeline/run_stage.sh assets \
  --thumbnail-mode manual \
  --title "오늘 장마감 핵심 시그널" \
  --subtitle "AI가 뽑은 KR 시장 인사이트"
```

검증(실패 판정 자동):
```bash
./scripts/pipeline/run_stage.sh validate
```

QC/Signoff:
```bash
./scripts/pipeline/run_stage.sh qc \
  --gate-a approved \
  --gate-b approved \
  --gate-c approved \
  --gate-d pending
```

오케스트레이션 관리자 리포트:
```bash
./scripts/pipeline/run_stage.sh manager-report
./scripts/pipeline/run_stage.sh quality-report
```

매니저 1회 사이클(권장):
```bash
./scripts/pipeline/manager_cycle.sh --language ko+en --duration-sec auto --max-scenes 6 --tts-engine auto --thumbnail-mode manual
```

## 6) 산출물/검증 포인트
- Manifest: `project/video/manifest.json`, `project/video/script.md`
- 녹화: `project/video/scenes/*.mp4`, `project/video/evidence/record_summary.json`
- 음성: `project/video/audio/narration.wav`, `project/video/audio/narration.json`
- 자막: `project/video/captions/subtitles.srt`
- 최종본: `out/final_showcase.mp4`, `project/video/evidence/render.log`
- 홍보 패키지:
  - `project/video/assets/thumbnail_prompt.md`
  - `project/video/assets/thumbnail_preview.png`
  - `project/video/assets/copy.md`
  - `project/video/assets/release_notes.md`
  - `project/video/assets/promo_brief.md`
  - `project/video/assets/promo_deck.pptx` (미설치 시 `promo_deck_fallback.md`)
- 검증: `project/video/evidence/validation_report.json`, `project/video/evidence/validation_report.md`
- 승인: `project/video/evidence/signoff.md`, `project/video/evidence/signoff.json`

검증 실패 기준(자동 fail):
- `scene_files_by_id` 실패(Manifest 기준 씬 누락)
- `record_summary` 실패(녹화 실패 잔존)
- `final_video_black_ratio` 임계 초과
- `audio_engine`이 `silence` 또는 메타데이터 누락
- `audio_silence_ratio` 임계 초과

## 7) AI 상호작용 프롬프트(복붙)
오케스트레이터:
```text
QUICK_START.md 기준으로 단계별 실행 상태를 모니터링하고, 실패 단계만 재실행 계획을 제시해줘.
```

씬 검수:
```text
record_summary.json과 scene mp4 기준으로 실패 원인을 scene별로 정리하고, manifest 수정안을 제안해줘.
```

자막 검수:
```text
subtitles.srt를 검토해 싱크 이슈가 의심되는 구간만 타임코드로 보고해줘.
```

## 8) Skill 사용(전문화 버전)
- 통합 사용 가이드: `.agent/skills/SKILLS_GUIDE.md`
- 스킬별 canonical 실행 진입점: `.agent/skills/SKILLS_GUIDE.md`의 `7) 스킬별 Canonical Run 문서`
- `.agent/skills/scene-script-architect/SKILL.md`
- `.agent/skills/scene-record-and-capture/SKILL.md`
- `.agent/skills/scene-tts-qwen/SKILL.md`
- `.agent/skills/qwen3-tts-universal/SKILL.md`
- `.agent/skills/scene-subtitle-builder/SKILL.md`
- `.agent/skills/video-mastering-editor/SKILL.md`
- `.agent/skills/promo-asset-studio/SKILL.md`
- `.agent/skills/video-copywriter-docs/SKILL.md`
- `.agent/skills/logo-thumbnail-prompt-designer/SKILL.md`
- `.agent/skills/pipeline-output-validator/SKILL.md`
- `.agent/skills/video-orchestration-manager/SKILL.md`
- `.agent/skills/video-quality-researcher/SKILL.md`

기존 통합 스킬:
- `.agent/skills/video-manifest-planner/SKILL.md`
- `.agent/skills/playwright-scene-recorder/SKILL.md`
- `.agent/skills/video-postproduction-remotion/SKILL.md`
- `.agent/skills/video-qc-gatekeeper/SKILL.md`
- `.agent/skills/video-pipeline-orchestrator/SKILL.md`
- `.agent/skills/video-tts-local-free/SKILL.md`

호출 예시:
```text
playwright-scene-recorder 스킬 규칙으로 녹화 실행하고 실패 씬만 재시도해줘.
```

오케스트레이션 매니저 호출 예시:
```text
video-orchestration-manager 스킬로 전체 사이클 실행하고 manager_report.md 기준으로 실패 원인/재실행 계획/사용자 승인 요청안을 작성해줘.
```

품질 개선 리서처 호출 예시:
```text
video-quality-researcher 스킬로 validation_report.json, manager_report.json, narration.json을 분석해 must-fix/nice-to-have를 분리하고 각 항목별 검증 커맨드까지 작성해줘.
```

QC 게이트키퍼 호출 예시:
```text
video-qc-gatekeeper 스킬 규칙으로 Gate A~D 증적을 점검하고 signoff.json 기준으로 릴리즈 가능 여부를 판정해줘.
```

## 9) 실패 시 즉시 조치
- 서비스 다운/응답 없음: `./scripts/pipeline/ensure_services.sh`
- `preflight` 실패: 메시지 기준으로 의존성/서버/환경변수 먼저 복구
- `qwen` 실패: `--tts-engine supertonic-local`로 재실행
- 로컬 Qwen 실패: `QWEN_LOCAL_CMD` 확인 후 `--tts-engine qwen-local-cmd` 재실행
- 녹화 실패: `./scripts/pipeline/rerun_failed.sh`
- 자막 문제: `./scripts/pipeline/run_stage.sh captions` 재실행
- 렌더 실패: `render.log` 확인 후 `./scripts/pipeline/run_stage.sh render`
