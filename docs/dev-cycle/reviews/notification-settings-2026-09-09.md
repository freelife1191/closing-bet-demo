# 설정·알림 연속 라운드 검수 결과

2026-09-09 대화에서 승인한 다섯 라운드를 구현·독립 리뷰·UltraQA·아카이브까지 완료했다. 원본 develop에 fast-forward로 반영했고, 원본의 사용자 소유 package.json은 그대로 보존했다.

| 항목 | 결과 | 필수 QA | 구현·QA 커밋 |
|---|---|---|---|
| [INFRA-043](../qa/INFRA-043.md) | 비밀 로그 차단, 비활성화·발송 실패 전달 | 4/4 | a902a58, ff71f6c |
| [INFRA-057](../qa/INFRA-057.md) | C0/DEL과 dotenv 제어문자 이스케이프 거부 | 3/3 | 5716194, 23c2d9a |
| [INFRA-058](../qa/INFRA-058.md) | 파일에 없는 키의 명시적 삭제를 워커에 반영 | 3/3 | 749a4de, 129a0f9 |
| [INFRA-051](../qa/INFRA-051.md) | 거부·적용·삭제·유지 결과와 부분 저장 실패 표시 | 3/3 | 726aa39, 4c34796 |
| [FE-041](../qa/FE-041.md) | 저장 성공 확인 후 발송, 실패 구분과 안전한 502 응답 | 5/5 | 203739e, 6e384d1 |

## 검증

- pytest 2220 통과, 기존 3 skip. Vitest 405 통과/58파일. typecheck exit0, lint 오류0/기존경고204.
- 실제 앱의 설정 화면을 agent-browser로 조작하고 실제 Next·Flask의 인가, 저장, 발송 진입 흐름을 검사했다. 외부 발송 경계와 보조 시장·프로필 응답은 합성 대역이다. 앱의 LLM·메일·메신저 서비스에는 실제 요청을 보내지 않았다.
- 필수 시나리오 합계18/18. 마지막 라운드는 dev 및 actual npm build/start의 정상·실패 흐름을 확인했다. 스크린샷은 직접 열어 판정했고, UI/API 보강/대역 적용 범위를 각 보고서에 구분했다.
- ponytail·code-review·security-review 통과. 독립 아키텍처는 네이티브 에이전트 한도 때문에 read-only ephemeral Codex CLI로 대체했고 원문·종료 코드·입력 SHA를 보존했다. root 심층 검토는 gstack checklist 직접 적용으로 기록했다.
- MCP LSP/AST 진단은 Transport closed로 사용할 수 없었다. 실행한 타입 검사·lint·Python AST·회귀와 구분했으며 LSP 통과로 표시하지 않았다. Next 실행 서버의 MCP는 실제 호출해 컴파일·런타임 오류를 확인했다.

## 발견과 보완

- dotenv의 제어문자 복원 범위 누락을 찾아 abfnrtv와 실제 C0/DEL을 함께 막았다.
- 최외곽 비밀 로그와 unknown JSON·재시도·GET/POST 응답 본문 오류 검사를 보강했다.
- 새 테스트 matcher의 타입 등록 누락으로 실패한 빌드를 표준 DOM 검사로 고쳤다. 타입 억제나 검사 삭제는 하지 않았다.
- 로딩 준비, 개발 캐시의 일시적404, 빈 입력 조작, 중계 Content-Type과 상태 계측의 검증 도구 문제를 제품 결함과 분리했다. 실패 원문과 보완 근거를 남겼고 성공 문구만으로 통과시키지 않았다.

## 최종 상태

- 최신 수정 파일18개(제품·테스트)를 각 파일의 마지막 독립 검토 SHA, 검증된 clone, 원본 Git HEAD와 대조했다. 계획은 완료 체크만 갱신했고 요구사항은 바꾸지 않았다.
- 전용 Next·Flask·proxy·브라우저를 종료하고 합성 env·쿠키·프로필·namespace, 격리 clone과 임시 실행 하네스를 모두 삭제했다. 원본 venv와 사용자 package.json을 보존했다.
- 운영 서버를 재시작하거나 배포하지 않았다. 파일 저장 후 메모리 적용은 현재 요청 워커에 한정하는 기존 방식이다. 저장과 발송 두 요청을 원자적으로 묶거나 실패를 자동 롤백하는 기능은 추가하지 않았다.
- TODO에서 승인한5개만 제거했다. 남은 항목71개(P0 0/P1 21/P2 50).

정확한 파일 해시와 정리 증거: [verification.json](../evidence/notification-settings-batch/verification.json). 라운드별 완료 기록: [일별 아카이브](../archive/daily/2026-09-09.md).
