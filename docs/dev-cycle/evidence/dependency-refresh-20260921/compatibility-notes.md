# 호환성 조정

- npm의 기존 caret 범위는 React19.3까지 선택했다. 계획한19.2.8 유지보수 범위에 맞춰 선택한 Next/React/Vitest/Vite 계열을 exact pin으로 고정했다. 첫 감사0은 중간 후보이며 최종 lock으로 재감사한다.
- 임시 tilde 범위는 기존 major-version smoke 검사가 caret만 제거하는 관례와 맞지 않았다. 기대값을 바꾸지 않고 exact pin으로 해결했다.
- Next가 ProcessEnv.NODE_ENV를 필수 타입으로 정의하므로 새 인증 subprocess 테스트는 NODE_ENV=test를 명시했다. 실제 자격증명은 전달하지 않는다.
- `eslint-plugin-react-hooks`의 선택적 7.0.1→7.1.1 갱신은 13개 신규 compiler 판정을 발생시켰다. 앱의 compiler 도입/광범위 hook 정리는 이번 보안 업그레이드와 구분해 기존 7.0.1을 override로 유지한다. Next16.3.5의 ^7.0.0 요구를 충족하며 어떤 lint 규칙도 비활성화하지 않는다. 최종 npm audit0을 다시 요구한다.
