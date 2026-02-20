# STEP2 - 전체 파이프라인 실행

목표: `manifest -> showcase-scenario -> scene-runner -> preflight -> record -> voice -> captions -> render -> assets -> validate -> manager-report -> quality-report -> qc` 경로를 성공시킨다.

참고 스킬:
- `project/project-showcase-kit/skills/psk-video-postproduction-remotion/SKILL.md`

## 권장 실행
```bash
cd /Users/freelife/vibe/lecture/hodu/closing-bet-demo

./project/project-showcase-kit/scripts/pipeline/run_all.sh \
  --language ko+en \
  --strict-tts true \
  --skip-health \
  --auto-start-services false
```

설명:
- `--tts-engine` 미지정 시 기본값 `supertonic-local`이 사용된다.
- 기본 `cache-mode=auto`에서 `manifest/showcase-scenario/record`는 유효 캐시를 재사용한다.
- 전체 재생성은 `--cache-mode refresh`로 강제한다.
- `ja/zh` 포함 다국어는 `qwen-local-cmd`로 실행한다.

## Qwen 다국어 실행(옵션)
```bash
./project/project-showcase-kit/scripts/pipeline/run_all.sh \
  --language ko+en+ja+zh \
  --tts-engine qwen-local-cmd \
  --cache-mode refresh \
  --qwen-local-timeout-sec 600 \
  --strict-tts true \
  --skip-health \
  --auto-start-services false
```

## 단계별 실행(디버깅)
```bash
./project/project-showcase-kit/scripts/pipeline/run_stage.sh manifest --language ko+en+ja+zh --duration-sec auto --max-scenes 3
./project/project-showcase-kit/scripts/pipeline/run_stage.sh showcase-scenario --language ko+en --manifest project/video/manifest.json
./project/project-showcase-kit/scripts/pipeline/run_stage.sh scene-runner --manifest project/video/manifest.json
./project/project-showcase-kit/scripts/pipeline/run_stage.sh preflight --tts-engine supertonic-local --strict-tts true --skip-health
./project/project-showcase-kit/scripts/pipeline/run_stage.sh record --headless false
./project/project-showcase-kit/scripts/pipeline/run_stage.sh voice --tts-engine supertonic-local --language ko+en --strict-tts true
./project/project-showcase-kit/scripts/pipeline/run_stage.sh captions --language ko+en
./project/project-showcase-kit/scripts/pipeline/run_stage.sh render --language ko+en --strict-remotion true --burn-in-captions true
./project/project-showcase-kit/scripts/pipeline/run_stage.sh assets --thumbnail-mode manual --title "KR 마켓 패키지 데모" --subtitle "통합 검증"
./project/project-showcase-kit/scripts/pipeline/run_stage.sh validate
./project/project-showcase-kit/scripts/pipeline/run_stage.sh manager-report
./project/project-showcase-kit/scripts/pipeline/run_stage.sh quality-report
./project/project-showcase-kit/scripts/pipeline/run_stage.sh qc --gate-a approved --gate-b approved --gate-c approved --gate-d approved
python3 project/project-showcase-kit/scripts/video/compare_tts_engines.py --manifest project/video/manifest.json --language ko+en

# 캐시 무시 전체 재생성
./project/project-showcase-kit/scripts/pipeline/run_all.sh --language ko+en --cache-mode refresh --strict-tts true --skip-health --auto-start-services false
```

## 완료 기준
- [ ] `project/video/manifest.json` 생성
- [ ] `project/video/script.md` 생성
- [ ] `project/video/scenes/scene-01.mp4` 생성
- [ ] `project/video/audio/narration.wav` 생성
- [ ] `project/video/audio/narration.json` 생성
- [ ] `project/video/captions/subtitles.srt` 생성
- [ ] `project/out/audio/narration.ja.wav` 생성(선택 언어 포함 시)
- [ ] `project/out/audio/narration.zh.wav` 생성(선택 언어 포함 시)
- [ ] `project/out/captions/subtitles.ja.srt` 생성(선택 언어 포함 시)
- [ ] `project/out/captions/subtitles.zh.srt` 생성(선택 언어 포함 시)
- [ ] `project/out/final_showcase.mp4` 생성
- [ ] `project/out/final_showcase.ko.mp4`, `project/out/final_showcase.en.mp4` 생성
- [ ] `project/video/assets/thumbnail_prompt.md` 생성
- [ ] `project/video/assets/thumbnail_prompt_nanobanana_pro.md` 생성
- [ ] `project/video/assets/youtube_description_prompt.md` 생성
- [ ] `project/video/assets/project_overview_doc_prompt.md` 생성
- [ ] `project/video/assets/ppt_slide_prompt_gemini.md` 생성
- [ ] `project/video/audio/narration.json`의 track speaker가 정책과 일치
  - Supertonic: `ko=Sarah`, `en=Jessica`
  - Qwen: `ko=Sohee`, `en=Serena`, `ja=Ono_Anna`, `zh/기타=Vivian`
- [ ] `project/video/evidence/validation_report.json`의 `status`가 `pass`
- [ ] `project/video/evidence/signoff.json`의 `status`가 `approved`
- [ ] `project/video/evidence/tts_comparison_report.json` 생성
- [ ] `tts_comparison_report.json`에서 `qwen-local-cmd`, `supertonic-local` 모두 `status=pass`

## 추가 확인
 - [ ] `./project/project-showcase-kit/scripts/pipeline/manager_cycle.sh --tts-engine supertonic-local --strict-tts true --skip-health --auto-start-services false` 1회 성공
- [ ] `./project/project-showcase-kit/scripts/pipeline/rerun_failed.sh` 실행 시 오류 없이 안내 메시지 출력
