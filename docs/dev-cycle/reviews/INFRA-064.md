# INFRA-064 리뷰 기록

- 승인: 사용자에게 bounded·T2 설계를 제시한 뒤 2026-09-08 「진행해」 응답.
- 기준: c25e09b, 정확한 입력 해시는 ../evidence/INFRA-064/review-input.json.
- 순서: ponytail → 독립 code-reviewer + architect. 수정 후 영향받은 리뷰 재검토.
- 시간 상한: 레인별900초. App 대응이며 hook 상태 조작 없음.

## 과잉설계 원문

초기: 발견 없음. 공유 flock을 실행 중 잠금과 완료 후 쿨다운 기록에 함께 쓰는 구현은 INFRA-064 요구를 직접 충족합니다. FileBackedStatus는 실행 동안 잠금을 보유하는 계약이 없어 대체 수단이 되지 않으며, 별도 서비스·새 추상화 추가도 없습니다. 새 테스트의 프로세스 실행은 워커 간 공유 동작을 실제로 확인하는 최소 경계입니다.

Lean already.

I/O 보완 후: 발견 없음. r+ 전환은 같은 inode와 기존 예약 내용을 유지하면서 write → flush → truncate 순서를 가능하게 하는 stdlib 최소 해법입니다. running 표식은 새 상태 계층을 만들지 않고 기존 손상 상태 복구 분기를 재사용하며, 완료 시 쓰기 실패의 즉시 재실행을 막습니다. close() 예외 뒤 로컬 플래그를 복구하는 중첩 finally도 별도 추상화 없이 실패 경계 안에만 제한되어 있습니다.

Lean already.

## 독립 지적 원문과 조치

code-reviewer: flock 경합을 무조건 True로 반환합니다. 쿨다운 중 두 워커가 동시에 GET하면 A는 잠금을 잠깐 잡고 timestamp를 읽는 동안 B가 BlockingIOError→True가 되어, 실제 분석이 없는데도 route가 initializing을 반환합니다. 손상/running 복구 중 잠깐 잠금을 잡은 경우도 같습니다. 실제 분석중만 initializing; cooldown은 data/fallback/empty 계약 위반입니다.

architect: running 위에 raw 숫자 timestamp를 덮어쓴 뒤 flush/truncate합니다. ENOSPC/EIO가 flush 중 partial write를 남기면 7~9자리 숫자만 남을 수 있고, parser는 이를 유효하지만 과거인 timestamp로 받아 즉시 재분석을 허용합니다. 명시 계약인 file-I/O 실패 fail-closed가 여전히 깨질 수 있습니다. cooldown:<timestamp>:end처럼 비숫자 prefix+완결 sentinel을 쓰고 exact parse하여 partial은 손상→5분 예약으로 보내는 최소수정 권장.

두 지적을 회귀3개 RED로 재현한 뒤 반영했다. 원문 명령/종료코드/실패는 review-red·review-green 증거에 보존했다. 수정 후 최종 code-reviewer APPROVE · architect CLEAR.

## 마지막 delta ponytail 원문

발견 없음.

cooldown:<timestamp>:end 완결 표식은 부분 flush가 유효한 과거 숫자로 해석되는 재실행 결함을 막는 최소 파일 형식입니다. 별도 상태 계층이나 직렬화 도구 없이 기존 텍스트 레코드만 확장했습니다.

BlockingIOError에서 정확히 running 표식만 실행 중으로 인정하는 분기도, 분석 실행 잠금과 쿨다운 읽기·복구 잠금의 경합을 구분하는 직접적인 최소 수정입니다. 두 회귀 테스트는 각각 실제 RED 재현 경계를 고정하므로 불필요한 fixture 계층으로 보이지 않습니다.

Lean already.

## 최종 아키텍처 원문 결과

```text
ARCHITECTURE / DEVIL'S-ADVOCATE REVIEW
Architectural Status: CLEAR
Blocking Findings: none

날짜 지정 GET은 저장 자료 조회로 제한된다.
최신 GET은 실제 running 상태에서만 initializing을 반환한다.
멀티워커 실행과 완료·실패 후 300초 쿨다운은 같은 flock inode로 공유된다.
손상, 중단, write/partial-flush/close 실패는 fail-closed 복구 경로를 갖는다.
관리자 POST와 스케줄러는 의도적으로 별도 정책으로 유지된다.

Residual action:
최종 QA 문서 수정 뒤 review-input.json의 QA SHA256을 갱신한다.
```

아키텍처 tradeoff: 시작·완료 순간의 상태 판정은 파일 읽기 시점에 의존한다. 관리자 POST·스케줄러 통합은 승인 범위 밖이다. QA 보고서의 실행 이력 갱신은 코드 입력 변경과 구분하고, 마감시 결과 문서 해시를 별도로 갱신한다.

## 최종 코드 리뷰 원문

Files Reviewed: 입력 5개 + TODO/QA/evidence
Total Issues: 1
CRITICAL: 0 / HIGH: 0 / MEDIUM: 0 / LOW: 1

[LOW] 복구 중 running 상태의 순간적 오표시 가능
File: app/routes/kr_market.py:295
Issue: 중단된 running 기록을 다른 워커가 복구하는 짧은 동안 동시 요청이 running을 읽으면 실제 분석 없이 initializing을 한 번 반환할 수 있습니다. 중복 분석이나 쿨다운 우회는 발생하지 않고 다음 폴링에서 정정됩니다.
Fix: 순간 단위의 정확성이 필수가 되면 짧은 lock 재확인이나 별도 공개 상태를 도입합니다. 현재 범위에서는 동기화 복잡도 대비 영향이 작아 비차단 사항입니다.
Confidence: HIGH(경합 존재), LOW(사용자 영향)

검토 결과:
- 날짜 쿼리 존재 여부를 직접 확인해 명시된 날짜 GET은 자동 분석을 시작하지 않습니다.
- 최신 invalid/stale GET만 공유 flock 경로에 진입합니다.
- 분석·저장·스레드 기동 실패 모두 완료 시점부터 300초 쿨다운을 기록합니다.
- running과 cooldown:<timestamp>:end 형식으로 부분 기록을 유효한 만료 시각으로 오인하지 않습니다.
- fcntl 부재와 잠금·파일 I/O 실패는 분석을 억제하며 오류 증거를 로그에 보존합니다.
- 표준 TextIOWrapper의 flush 실패에서도 하위 fd가 닫힘을 실제 ENOSPC 대조로 확인했습니다. 별도 os.close()는 fd 재사용 경쟁을 만들 수 있어 요구하지 않습니다.
- 우회성 fallback, 빈 예외 처리, 하드코딩된 시크릿은 발견하지 못했습니다.

Recommendation: APPROVE
확정 blocker는 없습니다. 루트 원인인 무제한 재실행 경로를 직접 막았고, 실패 증거를 숨기는 우회도 추가하지 않았습니다.

리더 판정: APPROVE / Architectural Status CLEAR. LOW는 공개 상태 스냅샷의 짧은 전이 창으로 수용한다. 빈도 제한·중복 방지의 우회가 없고 다음 폴링에서 정정되므로 별도 상태 계층을 추가하지 않는다. 요구사항을 순간별 선형화 보장으로 확대하지 않는다.
Python LSP 응답은 0 diagnostics이나 실제 backend가 tsc skipped이므로 Python 타입 검증 성공으로 세지 않는다. AST+실행 검사 증거를 사용했다.
