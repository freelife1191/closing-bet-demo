# SECURITY REVIEW REPORT

검토일: 2026-09-09 (Asia/Seoul)
검토 범위: `review-input-v4.json`으로 고정된 8개 파일과 `review-v4.diff`
기준 커밋: `4e57aa3d74f8ca8592fe7757b398a25f13307c69`
판정: **APPROVE (보안 범위)**

## 요약

- CRITICAL: 0
- HIGH: 0
- MEDIUM: 0
- LOW: 0
- 총 보안 이슈: 0

이번 변경은 새 인증·인가, 사용자 입력, 네트워크 요청, 파일 쓰기, 데이터베이스 질의,
명령 실행 또는 의존성 경계를 추가하지 않는다. 스케줄러 변경은 정적인 단계 이름만 로그에
기록하며, 실패했는데도 전체 성공으로 기록하던 A09 로깅 문제를 바로잡는다.

## Stage 1 — 요구사항 및 근본 원인 준수

승인 계획의 두 목표를 모두 충족한다.

1. `README.md:94-106`, `README.md:407-440`, `README.md:551-556`,
   `README.md:1451-1484`, `.env.example:88`, `.env.example:109-116`,
   `.env.example:186-187`, `frontend/src/app/page.tsx:249-260`은 실제 30분 기본 주기,
   17:00 단일 장 마감 체인, 조건부 AI 폴백을 설명한다. 실제 비밀값이나 새 공개 환경변수는
   추가하지 않는다.
2. `services/scheduler_jobs.py:118-143`은 네 단계 결과를 합산하고 알림 처리 뒤 전체 성공과
   부분 실패를 구분한다. `services/scheduler_jobs.py:127-140`의 새 로그 데이터는 코드에
   고정된 단계 이름뿐이며 외부 응답, 모델 출력, 환경값 또는 예외 내용을 새로 포함하지 않는다.
3. `tests/services/test_scheduler_jobs_refactor.py:150-299`은 단일·복합 실패, `None` 호환,
   알림 순서, 예외 뒤 성공 로그 부재와 상태 초기화를 대역으로 검증한다.

실패를 숨기는 신규 fallback, 무음 기본 반환, 진단 하향 또는 우회 경로는 없다. 런타임 AI
fallback은 변경되지 않았고 문서가 기존 조건과 논리 슬롯 의미를 정확히 설명하도록 수정됐다.

## Stage 2 — 보안 검토

### OWASP 범위

- **A01 접근 통제 / A07 인증 실패:** 관련 라우트, 세션, 토큰 검증 코드 변경 없음.
- **A02 암호화 실패 / 시크릿:** 추적 환경 파일은 `.env.example` 하나다. 추가된 값은
  스케줄 숫자·시간과 설명뿐이며 API 키·토큰·비밀번호·개인키 값은 없다.
- **A03 인젝션 / 출력 인코딩:** 새 외부 입력이나 문자열 실행 경로가 없다. TSX 변경은 React의
  정적 텍스트 노드이며 `dangerouslySetInnerHTML`을 추가하지 않는다. Python 로그의
  `failed_steps`는 고정 문자열 allowlist다.
- **A04 안전하지 않은 설계:** 기존 단계 실행·알림 조건·반환값 계약을 유지한다. 실패 단계
  집계는 로컬 호출 결과만 사용한다.
- **A05 보안 설정 오류:** `.env.example:88`의 기본 동기화 주기는 5분에서 30분으로 완화됐다.
  폐지된 `JONGGA_SCHEDULE_TIME` 예시를 제거해 운영자가 존재하지 않는 별도 잡을 오인할
  가능성을 줄인다.
- **A06 취약 구성요소:** 의존성 및 lockfile 변경 없음. 이번 변경에 대한 온라인 CVE 감사와
  `npm audit`은 실행하지 않았다. 따라서 저장소 전체 의존성에 알려진 CVE가 없다고 주장하지
  않는다.
- **A08 무결성 실패:** 기준 커밋과 매니페스트의 8개 SHA-256이 모두 현재 파일과 일치했다.
  생성한 범위 diff와 `review-v4.diff`의 SHA-256은 모두
  `3a5f8af97859070f87635f87e7190a4f768ff1f4187b43e95878cc1daced71a3`로 일치했다.
- **A09 로깅·모니터링 실패:** `services/scheduler_jobs.py:137-143`은 실패 단계가 하나라도
  있으면 ERROR를 기록하고 전체 완료 로그를 억제한다. 로그 내용은 정적 단계명이라 새 민감정보
  노출 경로가 아니다.
- **A10 SSRF:** URL 입력·HTTP 클라이언트·외부 provider 호출 코드 변경 없음.

### 정적 검사 및 진단

- `git diff --check`: 통과.
- LSP diagnostics: `services/scheduler_jobs.py`,
  `tests/services/test_scheduler_jobs_refactor.py`, `frontend/src/app/page.tsx` 모두 0건.
- AST 위험 패턴 검사: 수정 코드에서 `console.log`, 빈 catch/except, 하드코딩 문자열 비밀,
  bare except가 발견되지 않았다.
- 추가 diff 시크릿 패턴 검사: `NEXT_PUBLIC_`, API key, secret, token, password, private key,
  자격증명 포함 URL의 새 할당 또는 값 노출 없음.
- 기존 빌드 산출물의 `OPENAI_API_KEY` 일치는 `localStorage.removeItem` 목록의 키 이름이며
  비밀값이나 `process.env` 치환 결과가 아니다.
- 실제 `.env`, 실제 자격증명 값, `data/` 사용자 자료는 읽지 않았다.

## 검증 증거

- 전체 pytest: 2258 passed, 3 skipped, exit 0.
- 프론트엔드 Vitest: 424 passed, exit 0.
- TypeScript type-check: exit 0.
- ESLint: 오류 0, 기존 경고 201.
- 스케줄러 대상 테스트: 16 passed, exit 0.

`docs/dev-cycle/qa/INFRA-019.md:5-25`와 `docs/dev-cycle/qa/INFRA-029.md:5-25`는 현재
해시에서 계획 단계 문서다. 동적 브라우저·subprocess QA 완료 여부는 이 보안 리뷰의 승인
주장이 아니며 별도 QA 게이트에서 판정해야 한다.

## Recommendation

**APPROVE** — 고정된 v4 diff에서 배포를 막을 CRITICAL/HIGH 또는 그 밖의 보안 이슈를
찾지 못했다. 의존성 전체 CVE 상태는 변경이 없고 온라인 감사도 실행하지 않았으므로 별도
전면 의존성 보안 보증에는 포함되지 않는다.
