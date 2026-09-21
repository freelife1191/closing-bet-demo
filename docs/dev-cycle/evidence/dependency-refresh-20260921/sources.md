# 버전 선택 근거

독립 dependency-expert와 frontend dependency audit을 사용했고, 공개 메타데이터·프로젝트 보안 공지를 대조했다.
- Python 직접핀: Flask3.1.3/requests2.33.0/dotenv1.2.2/pytest9.0.3은 보안 수정 최소 안정판. yfinance1.3.0은 curl-cffi0.15를 허용하는 최소판.
- google-genai1.62.0의 anyio<5/requests<3, google-auth의 cryptography>=38.0.3 조건과 호환한다. google-genai/OpenAI 직접판은 유지하며 전이 의존성은 fresh설치+SDK실제파싱 검사로 검증한다.
- Next16.3.5/React19.2.8은 기존 minor 유지보수·보안판. Vitest4.1.11/Vite6.4.3은 기존2.x/5.x 취약점이 수정된 최소 지원선. plugin-react4.7은Vite6 peer지원.
- eslint-plugin-react-hooks7.0.1은 기존버전 유지. 7.1 compiler규칙 도입을 이번과 분리한다. next의^7.0.0요구 충족/최종audit0.
- eslint9.39.5 설치시 EOL경고가 있다. 이번에는 보안감사를 충족하는 기존Next9계열 구성을 유지하며 ESLint10 마이그레이드를 완료했다고 주장하지 않는다.
- numpy/pykrx는 INFRA-018 기존 쿠키 경계 문제로 유지. 감사DB 0은 그 미등재 결함이 해결됐다는 뜻이 아니다.

## 공식 링크
- https://pypi.org/pypi/yfinance/1.3.0/json
- https://pypi.org/pypi/google-genai/1.62.0/json
- https://github.com/pallets/flask/blob/3.1.3/CHANGES.rst
- https://github.com/nextauthjs/next-auth/security/advisories/GHSA-xmf8-cvqr-rfgj
- https://github.com/vitest-dev/vitest/security/advisories/GHSA-82fw-gwwq-j7x9
- https://github.com/vitejs/vite/security/advisories/GHSA-fx2h-pf6j-xcff
- https://github.com/react/react/security/advisories/GHSA-wx67-qw84-cm4g
- https://nextjs.org/docs/app/guides/upgrading/version-16
- https://v4.vitest.dev/guide/migration

별도 외부 CLI 리뷰/실제 OAuth/원격LLM/실시간시세를 실행했다고 보고하지 않는다.
