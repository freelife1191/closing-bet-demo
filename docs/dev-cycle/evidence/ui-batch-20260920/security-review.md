## 코드 보안 리뷰 요약

**검토 범위:** FE-032 및 공용 모달 변경 12개 파일, 서버 마스크·인가 정책, 합성 QA fixture와 보안 증거
**총 이슈:** 0

### 심각도

- CRITICAL: 0
- HIGH: 0
- MEDIUM: 0
- LOW: 0

### 확인 근거

- settingsEnv.ts:12: 마스킹된 값은 고정 문구만 표시하며 앞뒤 문자가 DOM 값·placeholder로 새지 않습니다.
- SettingsModal.tsx:112: 원본 마스킹 상태는 유지되어 미편집 필드가 저장 payload에 그대로 전달되고, 서버의 기존 보존 계약과 일치합니다.
- common_env_service.py:175: 서버 마스크 정책과 `*` 포함 값 보존 정책은 변경되지 않았습니다.
- env route.ts:26: NextAuth 관리자 판정과 서버 전용 토큰 전달 경로는 변경되지 않았습니다. 새 공개 환경 변수도 없습니다.
- Modal.tsx:103: 최상단 포털만 활성화하고 나머지 레이어와 배경을 `inert` 처리하며, 기존 `inert`·body overflow 상태를 복원합니다. 새 민감정보 노출 경로는 발견되지 않았습니다.
- fixture.py:49와 gateway.py:9: 합성 인증은 scratch 전용 QA 코드이며 제품 라우트에 연결되지 않습니다. 쿠키·Authorization·Set-Cookie도 차단합니다.
- 리뷰 입력에 기록된 대상 12개 파일 SHA-256이 모두 현재 파일과 일치했습니다.
- 대상 12개 파일 모두 LSP 진단 0건, `git diff --check` 통과.
- 합성 서버 비밀 3개를 주입한 빌드가 통과했고, 클라이언트 JS 32개에서 sentinel 일치가 0건입니다. 근거는 security-boundaries.json:13입니다.
- 실제 `.env` 값과 `data/`는 읽지 않았습니다. 추적 환경 파일은 `.env.example`뿐입니다.
- 의존성 변경이 없어 `npm audit`은 범위 밖이며 네트워크 검사를 실행하지 않았습니다.

### 권고

**APPROVE**

부모 보존 주: 판정 본문 유지, 파일 링크 표기만 간소화했다.
