# QUICK START (restored-full-stage)

기준일: 2026-02-20

이 가이드는 `project-showcase-kit` 파이프라인을 **`/Users/freelife/vibe/lecture/hodu/closing-bet-demo/project` 경계 안에서만** 실행/검증하는 빠른 실행 가이드다.

## 0) 핵심 정책
- 모든 산출물은 `project` 하위에 생성한다.
- 최종 산출물 경로:
  - `project/out/audio/*`
  - `project/out/captions/*`
  - `project/out/final_showcase*.mp4`
- 기본 언어는 `ko+en`
- 기본 시나리오 버전은 `normal`(약 2분)
- 추가 언어 옵션으로 `ja`, `zh` 지원
- 단일 언어 생성(`ko` 또는 `en`) 지원
- 다국어 실행 전 `manifest` 재생성 권장(언어별 `narrationByLang` 보장)
- 언어별 Speaker 정책:
  - Qwen(`qwen-local-cmd`): `ko -> Sohee`, `en -> Serena`, `ja -> Ono_Anna`, `zh -> Vivian`, 기타 `Vivian`
  - Supertonic(`supertonic-local`): `ko -> Sarah`, `en -> Jessica`
- Supertonic 엔진은 정책상 `ko/en`만 허용한다.

## 1) 준비
```bash
cd /Users/freelife/vibe/lecture/hodu/closing-bet-demo

python3 -m venv project/project-showcase-kit/.venvs/verify
source project/project-showcase-kit/.venvs/verify/bin/activate
pip install -r project/project-showcase-kit/requirements-dev.txt
```

환경 파일:
- `project/project-showcase-kit/.env`를 사용한다.
- `project-showcase-kit` 파이프라인은 workspace 루트 `.env`를 읽지 않는다.
- `QWEN_LOCAL_CMD`는 `project/project-showcase-kit/skills/...` 경로를 사용해야 하며 `.agent/...` 경로는 사용하지 않는다.

참고:
- Qwen 로컬 구성 스킬: `psk-qwen3-tts-universal`
- Supertonic 로컬 구성 스킬: `psk-supertonic-tts-universal`
- Remotion 후반편집 스킬: `psk-video-postproduction-remotion`
- 스킬 전체 사용법: `project/project-showcase-kit/docs/SKILLS_GUIDE.md`

## 2) 설정 방법 (어디서 어떻게)
우선순위: `CLI 옵션 > 환경변수(.env) > config 파일 > 기본값`

### 2-0. 엔진 선택 설정 (Qwen vs Supertonic)
- 즉시 선택(권장): `--tts-engine qwen-local-cmd` 또는 `--tts-engine supertonic-local`
- 기본 엔진 고정(환경변수): `TTS_ENGINE_DEFAULT=qwen-local-cmd|supertonic-local`
- 현재 기본값: `TTS_ENGINE_DEFAULT=supertonic-local`
- Supertonic 설치 스크립트로 자동 wiring 시 `SUPERTONIC_LOCAL_CMD`가 설정된다.

### 2-1. 언어 설정
- 기본(권장): `--language ko+en`
- 단일 생성:
  - `--language ko`
  - `--language en`
- 확장 생성:
  - `--language ko+en+ja+zh`
- 엔진별 제한:
  - `qwen-local-cmd`: `ko/en/ja/zh` 포함 다국어 가능
  - `supertonic-local`: `ko/en`만 허용 (`ja/zh` 지정 시 실패)

### 2-2. Speaker 설정
- 기본 Speaker는 엔진별 언어 정책이 자동 적용된다(수동 설정 불필요).
- Qwen 정책:
  - `ko -> Sohee`
  - `en -> Serena`
  - `ja -> Ono_Anna`
  - `zh -> Vivian`
- Supertonic 정책:
  - `ko -> Sarah`
  - `en -> Jessica`
- `qwen-local-cmd`/`supertonic-local` 템플릿에 기존 `--speaker`가 있어도 stage에서 언어별 값으로 재주입한다.

### 2-3. 추가 옵션
- TTS 엔진: `--tts-engine qwen-local-cmd|qwen|google|supertonic-local|auto|auto-local`
- 기본 엔진 환경변수: `TTS_ENGINE_DEFAULT=qwen-local-cmd|supertonic-local`
- 캐시 모드: `--cache-mode auto|refresh` (기본 `auto`)
- 캐시 재사용 제어(하위 호환): `--reuse-existing true|false` (기본 `true`)
- 시나리오 버전: `--scenario-version short|normal|detail` (기본 `normal`)
- 시나리오 파일 강제 지정: `--scenario-file <path>`
- 시나리오를 manifest에 반영할지 제어: `--manifest-from-scenario auto|true|false` (기본 `auto`)
- 녹화 기준 URL: `--base-url http://127.0.0.1:3500`
- 로컬 Qwen 타임아웃: `--qwen-local-timeout-sec <sec>` (strict=true 기본 600초)
- 로컬 Supertonic 타임아웃: `SUPERTONIC_LOCAL_TIMEOUT_SEC=<sec>` (기본 300초)
- Supertonic 러너 설정: `SUPERTONIC_ROOT`, `SUPERTONIC_LOCAL_CMD`, `SUPERTONIC_SARAH_STYLE`, `SUPERTONIC_JESSICA_STYLE`
- TTS 엄격 모드: `--strict-tts true|false`
- 번인 자막: `--burn-in-captions true|false` (기본 `true`, env `PSK_BURN_IN_CAPTIONS`)
- 헤드리스 녹화: `run_stage.sh record --headless true|false`
- 서비스 자동 기동: `--auto-start-services true|false`
- Health check 생략: `--skip-health`

### 2-4. TTS 스킬 설정 절차
- Qwen:
```bash
bash project/project-showcase-kit/skills/psk-qwen3-tts-universal/scripts/install_qwen3_tts.sh \
  --project-root /Users/freelife/vibe/lecture/hodu/closing-bet-demo \
  --write-dotenv true
```
- Supertonic:
```bash
bash project/project-showcase-kit/skills/psk-supertonic-tts-universal/scripts/install_supertonic_tts.sh \
  --project-root /Users/freelife/vibe/lecture/hodu/closing-bet-demo \
  --write-dotenv true
```

### 2-5. Remotion 스킬 절차
- 스킬 문서: `project/project-showcase-kit/skills/psk-video-postproduction-remotion/SKILL.md`
- 실행 명령: `project/project-showcase-kit/skills/psk-video-postproduction-remotion/commands/run.md`
- 검증 명령: `project/project-showcase-kit/skills/psk-video-postproduction-remotion/commands/validate.md`
- 복구 명령: `project/project-showcase-kit/skills/psk-video-postproduction-remotion/commands/recover.md`
- 스모크: `project/project-showcase-kit/skills/psk-video-postproduction-remotion/scripts/smoke.sh`

## 3) 테스트 검증
```bash
# 1) 스모크(빠른 확인)
python3 -m pytest -q \
  project/project-showcase-kit/tests/pipeline/test_docs_quick_start_contract.py \
  project/project-showcase-kit/tests/pipeline/test_voice_supertonic_engine_policy.py \
  project/project-showcase-kit/tests/pipeline/test_tts_comparison_report.py

# 2) 전체 회귀
python3 -m pytest -q project/project-showcase-kit/tests
```

기대 결과:
- `X passed` 형태로 종료되고 실패 0건
- `tests/pipeline/test_pipeline_runtime_units.py` 포함 전체 통과
- 참고: 전체 회귀에는 실제 `qwen-local-cmd` 추론이 포함되어 CPU 환경에서 장시간 소요될 수 있다.

## 4) 파이프라인 실행 예시
### 4-0. 표준 흐름 (시나리오 생성 -> manifest 반영)
```bash
./project/project-showcase-kit/scripts/pipeline/run_stage.sh showcase-scenario \
  --manifest project/video/manifest.json \
  --language ko+en

./project/project-showcase-kit/scripts/pipeline/run_stage.sh manifest-from-scenario \
  --manifest project/video/manifest.json \
  --script-out project/video/script.md \
  --scenario-version normal \
  --language ko+en
```

핵심:
- `showcase-scenario`는 `scenario_short/normal/detail.md` + `tts_plan_*` + `caption_plan_*` 생성
- `manifest-from-scenario`는 선택한 시나리오를 실제 실행 manifest에 반영
- `run_all.sh` 기본은 `--manifest-from-scenario auto`이므로 기본 manifest(`project/video/manifest.json`) 사용 시 자동 반영

### 4-0b. 씬 게이트 선검증(`scene-runner`)
```bash
./project/project-showcase-kit/scripts/pipeline/run_stage.sh scene-runner \
  --manifest project/video/manifest.json
```

정책:
- 씬 실패 시 최대 3회 자동 재시도(최대 3회)
- 씬 경계 싱크 오차 기준: `0.15초`
- 자막 종료-음성 종료 오차 기준: `0.10초`
- 씬 리포트: `project/video/evidence/scene_runner_report.json`

### 4-1. 보통(Standard, 2분) 제작 (기본 Supertonic)
```bash
./project/project-showcase-kit/scripts/pipeline/run_all.sh \
  --language ko+en \
  --scenario-version normal \
  --manifest-from-scenario auto \
  --strict-tts true \
  --burn-in-captions true \
  --skip-health \
  --auto-start-services false
```

### 4-2. 간소화(Short) 제작
```bash
./project/project-showcase-kit/scripts/pipeline/run_all.sh \
  --language ko+en \
  --scenario-version short \
  --manifest-from-scenario true \
  --strict-tts true \
  --burn-in-captions true \
  --skip-health \
  --auto-start-services false
```

### 4-3. 디테일(Detail) 제작
```bash
./project/project-showcase-kit/scripts/pipeline/run_all.sh \
  --language ko+en \
  --scenario-version detail \
  --manifest-from-scenario true \
  --strict-tts true \
  --burn-in-captions true \
  --skip-health \
  --auto-start-services false
```

### 4-4. 3버전 일괄 제작 + 버전별 산출물 보관
```bash
for VERSION in short normal detail; do
  ./project/project-showcase-kit/scripts/pipeline/run_all.sh \
    --language ko+en \
    --scenario-version "${VERSION}" \
    --manifest-from-scenario true \
    --strict-tts true \
    --burn-in-captions true \
    --skip-health \
    --auto-start-services false

  cp project/out/final_showcase.mp4 "project/out/final_showcase.${VERSION}.mp4"
  cp project/video/manifest.json "project/video/manifests/manifest.${VERSION}.json"
  cp project/video/script.md "project/video/manifests/script.${VERSION}.md"
done
```

### 4-5. 단일 언어 실행 (Supertonic)
```bash
# 한국어만
./project/project-showcase-kit/scripts/pipeline/run_all.sh \
  --language ko \
  --scenario-version normal \
  --manifest-from-scenario true \
  --tts-engine supertonic-local \
  --strict-tts true \
  --skip-health \
  --auto-start-services false

# 영어만
./project/project-showcase-kit/scripts/pipeline/run_all.sh \
  --language en \
  --scenario-version normal \
  --manifest-from-scenario true \
  --tts-engine supertonic-local \
  --strict-tts true \
  --skip-health \
  --auto-start-services false
```

### 4-6. 확장 실행 (한국어+영어+일본어+중국어, Qwen)
```bash
./project/project-showcase-kit/scripts/pipeline/run_all.sh \
  --language ko+en+ja+zh \
  --scenario-version normal \
  --manifest-from-scenario true \
  --tts-engine qwen-local-cmd \
  --qwen-local-timeout-sec 600 \
  --strict-tts true \
  --burn-in-captions true \
  --skip-health \
  --auto-start-services false
```

### 4-7. Qwen vs Supertonic 비교 리포트 생성
```bash
python3 project/project-showcase-kit/scripts/video/compare_tts_engines.py \
  --manifest project/video/manifest.json \
  --language ko+en
```
생성 파일:
- `project/video/evidence/tts_comparison_report.json`
- `project/video/evidence/tts_comparison_report.md`

설명:
- `--strict-tts true`에서는 선택한 엔진 결과만 허용하고 fallback을 차단한다.
- `--strict-tts false`에서만 `system-tts` fallback을 허용한다.
- 언어별 Speaker 정책 자동 적용(Qwen: `ko=Sohee,en=Serena,ja=Ono_Anna,zh=Vivian` / Supertonic: `ko=Sarah,en=Jessica`)
- 렌더 결과(`project/out/final_showcase*.mp4`)에는 자막 트랙(`mov_text`)이 포함된다.

## 5) 결과 확인
```bash
cat project/video/evidence/validation_report.json
cat project/video/evidence/term_audit_report.json
cat project/video/audio/narration.json
cat project/video/evidence/render_meta.json
ls -la project/video project/video/audio project/video/evidence project/out project/out/audio project/out/captions
ffprobe -v error -show_entries stream=index,codec_type,codec_name -of json project/out/final_showcase.mp4
```

통과 기준:
- `validation_report.json`의 `status`가 `pass`
- `term_audit_report.json`의 `status`가 `pass`
- `project/video/audio/narration.wav` 파일 존재
- `project/video/audio/narration.json`의 `tracks[].speaker`가 언어정책과 일치
  - Supertonic: `ko=Sarah`, `en=Jessica`
  - Qwen: `ko=Sohee`, `en=Serena`, `ja=Ono_Anna`, `zh/기타=Vivian`
- `project/video/evidence/render_meta.json`의 `tracks[].mode`에 `+captions` 포함
- `project/video/evidence/render_meta.json`의 `tracks[].mode`에 `+burnin` 포함 (번인 활성 시)
- `ffprobe` 결과에 `codec_type=subtitle`, `codec_name=mov_text` 존재
- 예: `project/out/audio/narration.ja.wav`, `project/out/captions/subtitles.ja.srt` (언어 `ja` 포함 시)
- `project/out/final_showcase.mp4` 및 `project/out/final_showcase.<lang>.mp4` 존재
- 홍보 프롬프트 md 생성:
  - `project/video/assets/thumbnail_prompt_nanobanana_pro.md`
  - `project/video/assets/youtube_description_prompt.md`
  - `project/video/assets/project_overview_doc_prompt.md`
  - `project/video/assets/ppt_slide_prompt_gemini.md`

## 6) 단계별 디버깅
```bash
./project/project-showcase-kit/scripts/pipeline/run_stage.sh manifest --language ko+en+ja+zh --duration-sec auto --max-scenes 3
./project/project-showcase-kit/scripts/pipeline/run_stage.sh showcase-scenario --language ko+en+ja+zh --manifest project/video/manifest.json
./project/project-showcase-kit/scripts/pipeline/run_stage.sh manifest-from-scenario --manifest project/video/manifest.json --script-out project/video/script.md --scenario-version short --language ko+en --reuse-existing false
./project/project-showcase-kit/scripts/pipeline/run_stage.sh manifest-from-scenario --manifest project/video/manifest.json --script-out project/video/script.md --scenario-version normal --language ko+en --reuse-existing false
./project/project-showcase-kit/scripts/pipeline/run_stage.sh manifest-from-scenario --manifest project/video/manifest.json --script-out project/video/script.md --scenario-version detail --language ko+en --reuse-existing false
./project/project-showcase-kit/scripts/pipeline/run_stage.sh preflight --tts-engine qwen-local-cmd --strict-tts false --skip-health
./project/project-showcase-kit/scripts/pipeline/run_stage.sh preflight --tts-engine supertonic-local --strict-tts false --skip-health
./project/project-showcase-kit/scripts/pipeline/run_stage.sh record --headless true
./project/project-showcase-kit/scripts/pipeline/run_stage.sh voice --tts-engine qwen-local-cmd --language ko+en+ja+zh
./project/project-showcase-kit/scripts/pipeline/run_stage.sh voice --tts-engine qwen-local-cmd --language ko+en+ja+zh --strict-tts true --qwen-local-timeout-sec 600
./project/project-showcase-kit/scripts/pipeline/run_stage.sh voice --tts-engine supertonic-local --language ko+en --strict-tts true
./project/project-showcase-kit/scripts/pipeline/run_stage.sh captions --language ko+en+ja+zh
./project/project-showcase-kit/scripts/pipeline/run_stage.sh render --language ko+en+ja+zh --burn-in-captions true
./project/project-showcase-kit/scripts/pipeline/run_stage.sh validate --manifest project/video/manifest.json
./project/project-showcase-kit/scripts/pipeline/manager_cycle.sh --language ko+en+ja+zh --tts-engine qwen-local-cmd --strict-tts false --skip-health --auto-start-services false
python3 project/project-showcase-kit/scripts/video/compare_tts_engines.py --manifest project/video/manifest.json --language ko+en

# 캐시 무시 전체 재생성(디버깅)
./project/project-showcase-kit/scripts/pipeline/run_all.sh --language ko+en --cache-mode refresh --strict-tts true --skip-health --auto-start-services false
```

## 7) 단위/통합 검증 루프
1. 스모크 테스트 실행: `python3 -m pytest -q project/project-showcase-kit/tests/pipeline/test_voice_supertonic_engine_policy.py project/project-showcase-kit/tests/pipeline/test_tts_comparison_report.py`
2. 전체 테스트 실행: `python3 -m pytest -q project/project-showcase-kit/tests`
3. Supertonic Standard(보통) 실행: `./project/project-showcase-kit/scripts/pipeline/run_all.sh --language ko+en --scenario-version normal --manifest-from-scenario auto --strict-tts true ...`
4. Qwen 실행(비교/다국어 시): `./project/project-showcase-kit/scripts/pipeline/run_all.sh --language ko+en --tts-engine qwen-local-cmd --qwen-local-timeout-sec 600 ...`
5. 버전별 실행: `--scenario-version short`, `--scenario-version normal`, `--scenario-version detail` 각각 1회 실행
6. 비교 리포트 실행: `python3 project/project-showcase-kit/scripts/video/compare_tts_engines.py --manifest project/video/manifest.json --language ko+en`
7. 리포트 검증: `project/video/evidence/validation_report.json`와 `project/video/evidence/tts_comparison_report.json` 확인
8. 실패 시 3~6단계 반복

## 8) 현재 복원 범위
지원 stage:
- `preflight`, `manifest`, `showcase-scenario`, `manifest-from-scenario`, `record`, `voice`, `captions`, `render`, `assets`, `validate`, `qc`, `manager-report`, `quality-report`, `sync-policy`
- 호환 stage: `gate-b-review`, `gate-c-review`, `sync-audit`, `timeline-report`

참고:
- `supertonic-local`은 정책상 `ko/en`만 허용하며 `ko=Sarah`, `en=Jessica` speaker를 사용한다.
- `--strict-tts false`에서만 런타임 실패 시 fallback(`system-tts`/silence)을 허용한다.
- `--strict-tts true`에서는 선택된 엔진 결과만 허용한다.
- `captions`는 음성 길이에 맞게 자동으로 타이밍을 보정하고, `render`는 음성/자막 길이를 포함하도록 영상 길이를 확장한다.
- legacy manifest(언어별 `narrationByLang` 없음)에서도 기본 데모 문장 3개는 `en/ja/zh`로 자동 보정된다.
