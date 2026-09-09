# 독립 architect 중간 원문

중대한 통합 결함 발견: 새 `frontend/tests/build/verify-build.mjs`와 `README.md`가 루트 `.gitignore:78`의 `build/` 규칙에 잡혀 `git status --ignored`에서 `!! frontend/tests/build/`로 나오고 `git ls-files`에도 없습니다. 반면 `frontend/package.json:17`은 이 파일을 실행합니다. 현재 상태로 일반 커밋/체크아웃 시 `npm run test:build`가 ENOENT가 되어 제안 변경은 BLOCK입니다. 해결은 (a) 두 파일을 `git add -f`로 명시 추적하고 추적 여부를 재확인하거나, (b) 무시되지 않는 디렉터리로 이동/좁은 negate 규칙 추가입니다. 나머지 인터페이스/SQLite 경계 검토는 계속하겠습니다.

## 리더 조치

동일 문제를 리더도 `git status`와 `git check-ignore`로 확인했다. `build-checks/`로 이동하고 실행 경로를 갱신했으며 새 경로가 untracked로 노출됨을 확인했다. 해시 갱신과 독립 리뷰 재검토, 변경한 경로의 명령 재실행을 수행한다. 최초 BLOCK을 삭제하거나 최초부터 CLEAR였다고 표시하지 않는다.
