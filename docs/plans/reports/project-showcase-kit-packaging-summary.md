# project-showcase-kit packaging summary

## 완료 범위

- `project-showcase-kit-src` 기반 매니페스트/템플릿/빌더 구성 완료
- `project-showcase-kit-dist` 설치 엔트리(`install_all.sh`) 구성 완료
- 영상/음성 관련 스킬을 `psk-*` 네임스페이스로 리네이밍 완료
- 루트 설치 대상 `/.agent/skills/psk-*` 기준으로 참조 전환 완료
- 패키징 필수 체크리스트(`required.md`) 최소화 완료

## 설치 대상

- Codex
- ClaudeCode
- Gemini
- Antigravity

## 핵심 검증

- `tests/packaging/*` 신규 테스트 통과
- `tests/skills/test_psk_reference_consistency.py` 통과
- `scripts/skills/validate_skill_structure.py --strict` 통과

## 산출물 경로

- 소스 패키지: `project/project-showcase-kit-src`
- 배포 패키지: `project/project-showcase-kit-dist`
- 필수 체크리스트: `project/project-showcase-kit-dist/checklists/required.md`
