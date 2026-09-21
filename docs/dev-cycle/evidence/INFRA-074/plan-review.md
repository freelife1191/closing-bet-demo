# Independent plan review
Reviewer: /root/restart_plan_review (critic), baseline92d84ab, INFRA-074-plan.md and matrix.

Initial REJECT: lifecycle ownership/legacy migration, atomic lock, launcher+listener readiness, partial failure cleanup and CD011 retry contract needed explicit specification.
Second REJECT: shared active venv/node_modules must not be changed before stopping services. Fixed order before implementation.

## Final original result
**OKAY**

**Justification**: 최종 계획은 구현자가 추측 없이 진행할 수 있습니다. lifecycle 순서가 `lock → 소유권 확인 → 정상 중지·포트 해제 → 의존성 동기화 → 기동`으로 확정됐고, 설치 실패 시 서비스가 내려간 상태임을 그대로 보고하도록 명시했습니다. 공유 활성 환경을 갱신하는 위험과 불필요한 atomic 배포 확장도 피했습니다.

대표 경로를 다시 대입한 결과 모두 실행 가능합니다.

- legacy 서비스는 UID·cwd·argv가 모두 맞을 때만 인수하며, 확인 불가 프로세스는 보존하고 실패합니다.
- 동시 restart/stop은 시작 식별자를 포함한 공유 원자 lock으로 직렬화됩니다.
- frontend 실제 launcher와 listener 자손 관계를 확인하므로 `grep` PID 및 타 서버 HTTP 200을 성공으로 오인하지 않습니다.
- 부분 기동 실패는 이번 실행의 자식과 기록만 정리하며 로그와 scheduler lock을 보존합니다.
- KRX 최초 로그인과 CD011 재요청의 HTTP·비JSON·schema·network 실패가 동일한 비밀 비노출 계약으로 검증됩니다.

**Summary**:
- Clarity: 통과
- Verifiability: 통과
- Completeness: 통과
- Big Picture: 관측된 결함 범위 안에서 최소 수정으로 적절함
- Principle/Option Consistency (ralplan): 해당 없음
- Alternatives Depth (ralplan): 해당 없음
- Risk/Verification Rigor (ralplan): 통과
- Deliberate Additions: 해당 없음

원격 Linux의 systemd/Supervisor를 임의 조작하지 않고 로컬 격리 검증 한계를 명시한 것도 적절합니다. 구현·검증 단계로 진행할 수 있습니다.
