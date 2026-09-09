# INFRA-019·INFRA-029 검토 및 실행 기록

상태: 첫 커밋3853de8에서 UltraQA 필수10/10 동작 통과. 런타임 정리 완료, clone통합·최종아카이브 대기.

## 승인과 범위

2026-09-09 두 라운드 bounded 설계 제안에 사용자 「승인」. 순서 INFRA-019 → INFRA-029, 각각 T3. `.env.example` 및 `services/scheduler_jobs.py` 위험 경로로 판정했다. 독립 clone의 develop에서 작업하며 원본의 미추적 package.json은 보존한다.

INFRA-019: 폐지된 15:20 단독 잡을 README·예제 설정에서 제거하고 Market Gate 기본 30분·17:00 체인으로 정정한다. 개장일의 간격 실행을 장중에만 실행한다고 설명하지 않는다. 랜딩의 GPT·Perplexity 선택은 설정에 따르며 모든 오류에 대체 모델을 보장하지 않는다. 매매 전략 설명에 있는 15:20~15:30은 자동잡 서술이 아니므로 유지한다.

INFRA-029: 일별 주가·수급·VCP·종가베팅 결과를 모아 알림 처리 뒤 성공/부분 실패를 기록한다. 앞 세 단계의 `is False`, 종가의 truthiness, 순서와 알림 조건, 반환값·finally 초기화는 유지한다. 알림 함수가 돌아온 사실을 전달 성공으로 표현하지 않도록 상위 로그는 「알림 처리 종료」로 정정한다.

## 발견과 보완

- critic: Perplexity 모든 실패에 폴백한다는 초안은 과장이다. 코드 429/503·quota/auth 전환과 일반 오류/파싱 실패를 구분해 조건부 문구로 수정했다. 최종 OKAY.
- RED에서 무조건 전체 완료가 기록되는 결함을 확인했다. 예외 검사의 caplog INFO 설정 누락도 보완하고, 옛 코드에서 알림 예외 직전 완료 로그가 포착되는 RED를 별도 확인했다.
- 탐색 에이전트의 「앞 단계 실패 시 알림도 중단」 권고는 채택하지 않았다. 사용자 승인 범위는 기존 알림 조건 보존이므로, 앞 단계 실패라도 종가 성공이면 알림을 처리한다. 두 항목의 ID/QA/완료 기록은 따로 유지한다.

## 검증 기준

baseline pytest2249 통과/기존3skip, Vitest424 통과. 수정 후 pytest2258 통과/기존3skip, 대상16 통과, Vitest424 통과/59files 및 실제 Next build, type-check 통과, lint0errors/기존201warnings. Python AST 두 파일 정상. Python LSP 실행 성공을 주장하지 않는다.

보안 확인은 변경 범위에 한정한다. 실제 비밀 값은 열지 않았으며 추적 env는 .env.example만이다. 새 NEXT_PUBLIC/비밀 할당·로그값·응답 경로가 없다. 빌드의 OPENAI_API_KEY 문자열은 기존 localStorage.removeItem 목록의 이름으로, 값이 아니다. 의존성 변경이 없어 온라인 CVE 전수검사로 확대하지 않았다.

## QA와 환경 대응

UltraQA App 대응으로 시나리오를 기록하며 OMX native state 명령은 실행하지 않는다. INFRA-019는 agent-browser 실제 Next 랜딩 및 스케줄 등록 subprocess, INFRA-029는 실제 체인의 적재/발송 경계만 대역 처리하는 subprocess로 검증한다. 스케줄러 변경은 내부 로그에 한정되고 API·상태 반환이 바뀌지 않아 해당 항목 자체의 browser는 적용 불가다.

검증 서버·브라우저는 고유 포트와 namespace/profile을 사용한다. 원본3500/5501/live, 실제.env와 data, LLM·수집·발송·거래·설정·삭제 경계를 건드리지 않는다. 명령 timeout, 종료 코드, 실제 단언 결과와 정리를 모두 확인한 후 완료한다.

## 증거

`docs/dev-cycle/evidence/scheduler-truthfulness-2026-09-09/`에 입력 해시·리뷰 원문·RED/GREEN·전체 검사·브라우저·동적 하네스·정리를 모은다. 원본 로그는 gzip으로 보존한다. 최종 QA/정리와 통합 뒤 완료 상태를 갱신한다.

독립 판정: ponytail v4 Lean already. Ship.; code-review v4 APPROVE; architect CLEAR; security-review APPROVE; T3 review core App 대응 추가 지적 없음. 보안 검토는 정적 세 확인 완료 후 문서 delta 검토와 병행했다. 아키텍처가 찾은 README 폴백 조건·zai 허용 목록·슬롯 귀속은 v4에서 보완했다.


## UltraQA 실행 결과

App 대응 iteration1. 실제 등록2구성(기본30분/17:00, 사용자7분/18:10; 폐지설정은잡추가없음) 및 실제체인13경우 통과. 외부 적재·발송만 대역으로 치환했다. 실제 Next 랜딩에서 데스크톱/모바일 공급자문구와3개탭 전환확인. browser GET24건 중22건200, favicon기존404, 외부font1건차단. API sink호출0, consolewarning/error0, pageerror0, Next compilation/runtime0. 7개PNG전부실제열람; stale ref로다른곳을찍은1개는제외하고6개로검증했다. whitespace trim 비교도하네스에서정정하고원본과재관측을모두보존했다. 제품실패나QA제품수정은없다.

범위밖 JONGGA-036: 랜딩의 +9/-5·15일 안내와 수익 예시. 현재스케줄/프로바이더설명및로그범위와분리해TODO등록했다. 외부아이콘폰트차단/기존favicon404로 아이콘자산전체검수통과는주장하지않는다. 필수문구와탭동작의검증에는영향없다.

보안·코드리뷰는 실제 source hash 및 입력 원문을 남겼으며, 의미가변하지않는문서진행/QA결과기록은구현범위변경과구분한다. 원본3500/5501재시작/라이브조회/배포/푸시는하지않았다.
