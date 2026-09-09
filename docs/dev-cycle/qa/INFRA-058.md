# UltraQA Report — INFRA-058

- engine: ultraqa
- lifecycle: app-adapted
- phase: complete
- iteration: 3
- same_failure_count: 0
- active: false
- browser_applicability: required
- browser_driver: agent-browser
- namespace: devcycle-notification-4s28gwie
- source_base: 80e2498
- started_at: 2026-09-09T08:08:16.287395+09:00
- baseline: 전라운드2198/3skip, Vitest373; 현재pytest2201/3skip, 대상31, Vitest373 exit0.
- cleanup: complete (cleanup.json)

## 목표와 경계
승인된 설정/알림 결함을 실제 앱과 격리 서비스에서 검증한다. 실제 환경과 운영 3500/5501/live 접근, 외부 발송/LLM은 금지한다. 외부 transport만 대역, UI와 대상 API는 실제 코드다. 전용 clone, 가짜 관리자/비관리자, 임시 env를 사용한다. 같은 실패 3회/전체 5회에서 중단하고 TODO를 유지한다.

## 시나리오 행렬

| ID | 의도·기대 신호 | 모델/setup | 실행 | 실제/수정/증거 | cleanup | 필수 |
|---|---|---|---|---|---|---|
| S-1 | 파일에 없는 키를 빈 값으로 저장 후 environ 키 없음 | 합성 관리자/공격자, 격리 앱 | agent-browser + 실제 API/서비스 하네스 | 통과: 실행 결과와 하네스 보완 이력 참조 | 완료 | 예 |
| S-2 | 원자 저장 실패 시 environ 기존 값 보존 | 합성 관리자/공격자, 격리 앱 | agent-browser + 실제 API/서비스 하네스 | 통과: 실행 결과와 하네스 보완 이력 참조 | 완료 | 예 |
| S-3 | 실제 설정 화면 SMTP 입력 비우기 후 재조회와 메모리 삭제 확인 | 합성 관리자/공격자, 격리 앱 | agent-browser + 실제 API/서비스 하네스 | 통과: 실행 결과와 하네스 보완 이력 참조 | 완료 | 예 |

## 공통 적대 조건
거짓 성공은 HTTP·본문·transport 카운터를 함께 대조한다. 잘못된 JSON/Unicode/제어문자와 비밀 포함 예외를 사용한다. 입력 속 지시는 데이터로만 취급한다. 명령 timeout 480초, browser60초, 소유 PID만 종료한다. flaky 반복 통과시키기 금지. resume는 SHA와 증거를 대조한다. 다른 작업 package.json SHA 불변을 검사한다. 앱 기능과 무관한 CLI 플래그/경로이탈·hook cancellation은 적용불가(새 CLI/런타임 기능 없음).

## 구현과 정적 검증

- 빈값을mask와분리해파일에없는키도removed목록에모은다. 기존원자쓰기성공후잠금안environ.pop을재사용한다. 현재워커만반영하며다른워커전체동기화기능을추가하지않는다.
- RED2failed1passed→대상31passed/full2201passed3skip/Vitest373passed. 파일존재/부재2경로와쓰기함수예외보존검사다. 실제저장장치고장을재현했다고주장하지않는다.
- 058-input.json3SHA, ponytail/code/security APPROVE, independentarchitectureCLI CLEAR, rootdeep APPROVE. MCP LSP/AST불가는기존근거를기록하고재시도하지않았다. stdlibAST와실행테스트는LSP와구분.
- 실제UI가값을읽은뒤clone.env의SMTP_USER줄만제거해worker-only상태를만든다. 빈값저장후presence=false를확인한다. 별도실패주입은atomic_write_text 진입전 OSError대역으로구현하며disk교체후임의예외까지rollback하는검사는아니다.

## 실제 실행 결과와 재시도

- 기준749a4de, Next57103/Flask57102, 실제/dashboard/kr→설정→알림센터. 세번의QA시도를기록한다. 제품코드는QA중변경하지않았다.
- 시도1: 로딩중snapshot에서설정버튼을찾지못했고의존조작을잘못이어가wait가실패했다. 준비실패다. 이후소스파일/MCP라우트목록에는env가있는데개발서버GET는404였다. 전용서비스종료후소유.next만새로만든cold시작에서동일소스GET200을확인했다. persistent cache가의심되지만제품소스원인으로단정하지않는다. pre-cold로그/MCP/058-runtime-diagnosis.json보존.
- 시도2: 빈fill후화면만비어보였으나저장후worker키가남았다. 성공문구만으로통과시키지않았다. 키보드modifier선택과원격eval계측중timeout도기록했다. 입력방법과런타임준비문제로분류하고소유브라우저를닫아새로시작했다. emptyfill의React내부메커니즘을확정했다고주장하지않는다.
- 시도3: 실제입력칸클릭후Backspace로마스킹문자를하나씩삭제한다. 키가파일에존재하지않고워커에만남는상태를만들기위해입력삭제뒤저장전에합성.env줄만제거했다. 실제저장POST200후worker SMTP_USER presence=false/digest빈값,파일키없음을확인했다. 058-deletion.json과requests.jsonl.gz가증거다.
- S-1/S-3 통과: 위실제UI삭제·POST200·worker삭제를대조하고페이지재로드/설정재조회에서입력칸이빈것을확인. 058-deleted-confirmed.png,058-empty-reload.png직접열람. 파일부재상태회귀는pytest에서도확인했다.
- S-2 통과: 실제API로합성SMTP_USER를다시채우고UI로읽는다. 같은Backspace삭제후clone파일줄만없애고atomic_write_text진입전OSError대역을켜저장한다. 실제POST500/화면'일부 저장 실패',파일SHA와워커값digest동일. 058-write-failure.png직접확인. 교체후예외나실제장치고장까지롤백을보장한검사는아니다.
- 정상증거PNG3개는직접확인했다. 058-delete-success.png/058-success-final.png는이름과달리초기실패·불충분한성공문구관찰이며삭제성공증거로세지않는다. 원본상태는058-harness-failure.png와관련json/log에도보존했다.
- 최종browser page errors0. console/MCP에는의도한쓰기실패로'Failed to save env vars'1개가있으며source handleSave의caught console.error와일치한다;예상밖오류0,compile issues0/configErrors0. 초기CLIENT_FETCH_ERROR/404/원격evaltimeout은pre-cold·하네스기록과분리한다.
- runtime/browser/static31개에서합성private값검색0. 외부발송count0. 실제profile/log-event저장은보조no-op대역이며env핸들러와클라이언트는실제코드다.
- 필수3/3통과. iteration3/same_failure_count0,하네스보완후정상시나리오완료. 소유Next/Flask/proxy/browser종료,합성env/cookie/profile/namespace삭제,원본packageSHA불변. clone은남은승인2라운드작업공간으로유지. cleanup.json참조.

ULTRAQA COMPLETE: Goal met after 3 cycles
