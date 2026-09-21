# INFRA-070 의존성 보안 업데이트 실행 계획

> 실행: 리더가 직접 구현·검증, native 독립 계획/코드/구조/보안 리뷰. 사용자는 필요한 패키지 업그레이드와 검증을 요청했고 앞서 승인 판단을 위임했다.

**목표:** 현재 감사에서 발견한 수정 가능한 의존성 보안 문제를 제거하고 앱 동작을 유지한다.
**설계:** brainstorming bounded 업데이트 묶음, Vitest/cryptography/setuptools 주요 버전 변경으로 T3. 새 기능·전역 monkeypatch·vendor fork 없이 공식 배포 패키지만 사용한다. 새 설치 의존성이 아니라 기존 전이 의존성의 보안 하한을 보안 요구사항으로 고정한다.

## 범위와 선택
- requirements.txt: Flask3.1.3, requests2.33.0, python-dotenv1.2.2, pytest9.0.3 이상 중 공식 호환 수정판을 exact pin. yfinance1.1.0의 curl-cffi<0.14 제한 때문에 yfinance1.3.0도 함께 올린다. 다른 직접 패키지는 유지한다.
- requirements-security.txt 신규 보안 하한 요구사항(requirements.txt가 `-r requirements-security.txt`로 직접 포함): anyio>=4.14.2, click>=8.3.3, cryptography>=50.0.0, curl-cffi>=0.15.0, idna>=3.15, lxml>=6.1.0, pillow>=12.3.0, pyasn1>=0.6.4, Pygments>=2.20.0, setuptools>=83.0.0, soupsieve>=2.9.0, urllib3>=2.7.0, Werkzeug>=3.1.6. 실제 설치 resolver/pipcheck/감사로 호환성 확인. 설치 결과를 보고서에 남긴다.
- frontend/package.json/package-lock.json: next/eslint-config-next16.3.5, react/react-dom19.2.8, next-auth4.24.15, vitest/@vitest/ui4.1.11, Vite6.4.3. Vite는 기존 전이 의존성의 버전 선택을 명확히 할 필요가 있으면 devDependency로 선언. 기존 @vitejs/plugin-react4.7 peer 호환 유지. 다른 기존 범위 하위 의존성은 npm update로 보안 수정판 선택.
- 필요 시 Vitest4 타입/설정 호환성만 수정한다. 테스트 의미·기대값을 낮추거나 실패 검사를 제거하지 않는다.
- numpy1.26.4/pykrx1.2.3, google-genai1.x는 유지. INFRA-018 보류는 별도이며 이번 감사0건으로 해제하지 않는다. 감사DB는 알려지지 않은 pykrx 쿠키 결함을 보장하지 않는다.
- 원본 venv/node_modules, .env/data/logs, 3500/5501/live 미변경·미접속. 임시 소유 checkout/venv만 설치. 공식 npm/PyPI 설치 시 scripts 비활성 또는 wheel만 사용. 제품 실행은 외부 네트워크 차단.

## 작업과 검증
- [ ] 공식 버전/보안 근거와 설치 전 감사 기록 확정. 독립 계획 검토 ACCEPT.
- [ ] NextAuth malformed Bearer의 실제 getToken 경계 회귀를 먼저 추가해 이전 버전 실패 확인. 합성 JWT 정상 encode/decode와 익명/잘못된 토큰도 검증한다. 원본 인증 정보 없음.
- [ ] 후보 manifest/보안 하한를 소유 scratch에서 설치. pipcheck, npm audit, Python OSV 재감사. 호환성 문제는 원인 확인 후 최소 수정; 수정되지 않은 취약점은 완료하지 않는다.
- [ ] yfinance 실제 Ticker.history를 합성 HTTP 경계 응답으로 실행해 OHLCV/빈 응답/오류 동작과 외부 통신 0을 확인한다. 기존 소비 함수와 기대값을 대조하며 보안 변경 RED/GREEN은 NextAuth 실제 경계로 입증한다.
- [ ] 표적 회귀, 전체 pytest/Vitest, type/lint, production build3종을 수행한다. Next16 patch에는 major codemod를 적용하지 않는다. Vitest4 migration 공식 문서에 따라 필요한 타입만 조정.
- [ ] ponytail → code+architect → security/T3 순차 독립 검토. 설치 tarball/lock 해시와 정적검증 기준 고정.
- [ ] 구현/QA 행렬 첫 커밋 후 UltraQA App 대응. ego-browser 신규 전용 공간 하나에서 실제 앱 VCP 정상/빈분석/합성엔진 생성·차트 실패복구, 로그인 화면·세션 거부를 검증한다. API와 모델 외부 전송만 합성하며 UI는 실제 Next 앱. 실제 NextAuth JWT 및 Flask JSON 계약은 별도 동적 경계 검사로 보강한다. MCP 오류0 확인.
- [ ] 소유 프로세스/브라우저/scratch 정리, 원래 package.json SHA 불변. 필수 통과 후 INFRA-070만 archive. INFRA-018 유지.

## 성공 기준 및 제한
npm audit 보고23개 항목 제거, Python 설치환경17개 영향패키지의 알려진 보안 문제 제거 또는 미해결이면 BLOCKED. 전체 tests/형검사/빌드/실측 통과. 실제 OAuth 로그인·유료 모델·시세 원격 호출은 하지 않으며 그 영역의 실서비스 검증을 주장하지 않는다.
현재원본환경 업데이트/서비스 재시작/배포는 이번 소스 업데이트와 분리한다.

## 근거
- npm-audit-before.json, python-audit-before.json, python-advisories.json (공식 npm registry 및 OSV)
- https://nextjs.org/docs/app/guides/upgrading/version-16
- https://vitest.dev/guide/migration/ (4.x는 v4 문서 별도 확인)
- https://github.com/vitest-dev/vitest/security/advisories/GHSA-82fw-gwwq-j7x9
