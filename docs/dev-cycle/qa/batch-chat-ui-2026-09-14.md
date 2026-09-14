# UltraQA Report

- 항목: CHAT-019 · CHAT-010 · CHAT-020, 사용자 「승인」 범위의 공유 T3 라운드.
- engine: ultraqa | lifecycle: app-adapted | phase: complete | iteration: 3
- same_failure_count: 0 (첫 회 S-2 제품 실패 이력 보존, 두 번째 회 S-3는 하네스 진단 후 판정 보류).
- browser_applicability: required | browser_driver: agent-browser
- 기준 커밋: `b86358f` (첫 구현), `174795b` (QA Escape 수정).
- 기준 소스: `../evidence/chat-ui-20260914/qa-source.json`, `qa-source-v2.json`, `review-input.json`의 6개 SHA.
- 대상: 격리 Next `127.0.0.1:57601`, Flask `127.0.0.1:57602`.
- 브라우저: `chat-ui-20260914/qa`, 보조 `chat-layout-20260914/qa`. 최종 S-3는 headed 브라우저.
- 완료 조건: 필수 8/8, 정적 검사, T3 독립 리뷰, 소유 프로세스·fixture 정리.

## 범위와 실행 경계

챗봇의 카드·명령 팝업 배치, 삭제 명령 설명, 모바일 메뉴의 초점과 폭 전환, VCP의 메시지·대화·`/clear` 삭제 결과 처리를 검증했다. VCP에서는 성공 후에만 표시를 바꾸고, 메시지 404와 세션 404를 실제 재조회로 구분하며, 늦은 응답이 다른 종목을 바꾸지 않는 것이 핵심이다.

원본 서버 3500/5501과 라이브 사이트를 QA 대상으로 사용하지 않았다. git archive 사본과 가짜 계정·데이터를 썼다. 외부 LLM 경계와 의도적인 오류·지연만 fixture로 대체하고 실제 화면, 요청 생성, Flask 챗봇 라우트, 명령 처리, 이력 저장소는 유지했다. 실제 로그인·외부 LLM 응답 품질·과금 검증은 아니다. 비밀 파일을 복사하지 않았다.

한 실행자가 금지된 원본 cwd에서 신규 mock Vitest 파일을 한 번 실행했다. 부모가 경로를 확인한 뒤 이를 격리 증거에서 제외하고 scratch에서 다시 검증했다. 원본 Vite 캐시 쓰기 가능성은 배제하지 않는다. 원문과 조치는 `execution-deviation.md`에 보존했다.

## 필수 행렬 결과

아래 증거 경로는 `../evidence/chat-ui-20260914/` 기준이다. 각 행은 필수이며, 전체 정리는 `cleanup.json`에 연결된다.

| ID | 의도·사용자 모델 | 실제 조작과 기대 | 실제 결과·증거 | 정리 | 판정 |
|---|---|---|---|---|---|
| S-1 | 작은 화면 사용자 | 1280×577, 1440×900, 375×812에서 빈 화면과 `/` 팝업 열기. 카드·툴바·다섯 명령을 모두 읽고 삭제 설명 대조 | 겹침 없이 접근 가능. 두 챗봇 명령 설명 일치. `layout-qa/report.md`, `s1-*.png/txt`; 이미지 직접 열람 | 보조 브라우저 종료 | 통과 |
| S-2 | 키보드 사용자 | 메뉴 접기→Tab, 직접 닫기·대화 선택, 삭제 확인의 취소에 초점→Escape 두 번 | 숨은 링크 제외, 닫힌 뒤 메뉴 열기로 초점 복귀. 첫 Escape는 확인창만, 두 번째는 메뉴 닫힘. `layout-qa/qa2-report.md`, `qa2-escape-first.png`, `qa2-*-active.txt` | 보조 브라우저 종료 | 실패 → 고침 |
| S-3 | 창 크기 변경 사용자 | 모바일 초기, desktop→mobile, mobile open→desktop→mobile. 이벤트 수신 뒤 drawer DOM도 없어야 함 | 1280에서 MQL true·drawer DOM false, 375 복귀에서 MQL false·drawer DOM false. `qa3-desktop-state.txt`, `qa3-return-state.txt`, `qa3-return.png` 직접 열람 | 부모 브라우저 종료 | 통과 |
| S-4 | 메시지 삭제 사용자 | 첫 질문 삭제, 500, 메시지 404/세션 유효, 세션 404, 이력 보관 한도 | 서버 `[user,model]`→`[model]`; 500 내용 보존; DELETE404→GET200 재동기화/GET404 키 정리. 50개 중 마지막 답변 삭제→49개. `vcp-first-delete-result.json`, `vcp-message-errors-result.json`, `vcp-seed-50-result.json` 및 전후 UI 기록 | 합성 이력 scratch 제거 | 통과 |
| S-5 | 대화 삭제 사용자 | 실제 버튼·확인창으로 500/404/200 | 500 기록 보존과 오류 표시, 404 키 복구, 200 실제 이력 삭제. `vcp-conversation-errors-retry-result.json` 및 UI 기록 | 합성 이력 scratch 제거 | 통과 |
| S-6 | 명령·반복 입력 사용자 | 실제 입력창 `/clear` 500/404/200 및 삭제 지연 중 Enter 반복 | 동일 오류 계약. pending에서 입력·삭제 비활성, 반복 Enter에도 DELETE 1회. `vcp-clear-errors-result.json`, `vcp-pending-repeat-result.json`, `iteration3-requests.jsonl` | 합성 이력 scratch 제거 | 통과 |
| S-7 | 빠른 종목 전환 사용자 | Alpha DELETE/POST/SSE 지연 중 차트 닫고 Beta 진입 | Beta 이력·세션 키 유지, 늦은 Alpha 문구가 Beta에 없음. Alpha 서버 처리도 실제 완료. `vcp-delayed-clear-result.json`, `vcp-delayed-post-result.json`, `vcp-stream-switch-result.json` 및 전후 UI 기록 | 지연 작업 완료 후 서버 종료 | 통과 |
| S-8 | 경계·증거 검수 | 현재 SHA·원본 목록·사용자 파일, Next MCP·콘솔·실제 검사 수·정리 대조 | 소스 6개 일치, MCP issues/configErrors/sessionErrors 빈 배열, 페이지 오류 없음, 사용자 package SHA·data 최상위 목록 동일, 소유 포트·프로필 프로세스 없음. `preservation.md`, `qa2-next-compilation.txt`, `qa3-next-runtime.txt`, `qa3-final-errors.txt`, `cleanup.json` | scratch 제거 완료 | 통과 |

S-4~7의 기본 행위는 `b86358f`에서 실측했다. `174795b`의 제품 변경은 chatbot 페이지의 Escape 등록·해제 인자 두 개뿐으로 VCP의 SHA가 그대로이므로 그 증거를 재사용했다. 명령 중복 방지는 최종 소스에서 추가 실측했다. 초기 GET의 늦은 응답, 동기화 오류, 완료 없는 SSE, 임시 명령의 순서 등 세부 분기는 회귀 검사로 보강했으며, 모든 분기를 브라우저에서 각각 실행했다는 의미는 아니다.

별도 CLI 플래그·경로 파서, 외부 LLM prompt injection 실행은 이번 UI 변경에 해당하지 않는다. 합성 응답과 화면 문구는 자료로만 취급했다. 명령·대기에는 시간 제한을 두고 숨은 실패와 skip을 확인했다.

## 정적 검사와 리뷰

모든 기준 검사는 `run_check.py`가 기록된 scratch에서 실행했다. 환경 변수는 최소 허용 목록과 합성 설정만 전달했고 원본 쓰기·외부 네트워크는 sandbox로 차단했다.

| 검사 | 명령 | 제한 | 결과 |
|---|---|---|---|
| Python | `venv/bin/python -m pytest -q` | 180초 | 2296 통과, 3 skip, exit 0 |
| Frontend | `npx vitest run` (frontend cwd) | 300초 | 69파일, 488 통과, exit 0 |
| Lint | `npm run lint` | 90초 | 오류 0, 경고 190, exit 0 |
| 실제 빌드 | `npm run test:build` | 240초 | 빌드·필수 라우트·TypeScript 3/3, skip 0, exit 0 |
| TypeScript | 빌드 후 `npm run type-check` | 90초 | exit 0 |

증거는 `pytest.json` 및 `*-qa2.json`, 각 `.log.gz`다. Python 3 skip은 기존 수동 검사 2개와 `.env`를 복사하지 않은 격리 검사의 환경 대조 1개다. Python 변경은 없었다. React act 경고·기존 lint 경고·Browserslist 갱신 안내가 남아 있으며 경고 0으로 보고하지 않는다. LSP가 연결되지 않아 타입 검사로 대체했고 LSP 성공으로 기록하지 않았다.

리뷰는 ponytail → code-review/architect → T3 deep-review 순서를 수행했고, 마지막 Escape 수정에도 같은 영향 검토를 했다. 최종 SHIP / APPROVE / CLEAR / APPROVE. 최초 차단과 수정 결과는 `code-review-*.md`, `architect-*.md`, `deep-review-*.md`, `capture-reviews.md`에 보존했다. T3 계획 검토는 최초 REJECT를 보완해 OKAY를 받았다. 합계 diff로 T3에 올린 뒤 계획을 보강한 시점을 숨기지 않았다. gstack review는 현재 묶음 기준의 로컬 검토로 대응했고 원격 PR/Greptile 검토를 주장하지 않는다(`review-mode.md`).

## 실패 원인과 수정

1. VCP 첫 이력에는 화면 전용 환영 문구가 있어 UI 인덱스를 서버에 보내면 다른 메시지가 삭제됐다. 실제 GET의 서버 인덱스만 삭제에 사용하고, 전송 완료 후 저장 이력을 다시 읽었다. 임시 `/help`·`/status`에는 삭제 인덱스를 부여하지 않았다.
2. 삭제의 중복 실행과 종목 전환 뒤 늦은 GET/DELETE/POST/SSE가 새 화면에 반영될 수 있었다. 공통 pending과 캡처한 대상·작업 세대로 경계를 고정했다. 특히 POST 응답 직후 placeholder를 추가하기 전 현재 작업인지 확인했다.
3. 오류 또는 완료 없는 SSE 뒤 무조건 재조회하면 실패 표시가 사라졌다. 성공한 done 이후에만 동기화한다. reader 실패는 명시적인 오류 표시로 처리하며 모든 부분 답변 보존을 보장한다고 주장하지 않는다.
4. 첫 QA의 실제 Escape는 확인창을 닫은 document 리스너와 window 리스너 사이에서 React가 상태를 갱신해 메뉴까지 닫았다. listener 사이 flushSync 회귀가 먼저 실패한 뒤, window capture 단계에서 확인창 존재를 판정하도록 바꿔 통과했다.

## 브라우저 하네스 진단과 재검증

두 번째 QA의 S-3는 처음에 제품 실패로 보고됐다. 추가 관측에서 CDP의 innerWidth/matchMedia 값만 바뀌고 독립 MQL change, window resize, requestAnimationFrame이 모두 진행되지 않는 현상을 확인했다. 느린 전환에서는 같은 코드가 정상 동작했다. architect는 제품 수정을 추가할 근거가 없으며 이벤트 전달을 선행 조건으로 삼도록 진단했다.

세 번째 QA는 agent-browser를 headed로 다시 열고 렌더 프레임과 MQL 이벤트를 확인한 뒤 DOM 상태를 판정했다. true와 false 이벤트가 모두 전달됐고 drawer가 계속 닫혀 있어 통과했다. 이전 실패 보고는 `layout-qa/qa2-report.md`에 그대로 남긴다. 정확한 하네스 내부 원인이 프레임 정체인지 CDP 이벤트 coalescing인지는 단정하지 않는다. `diag-*.txt`에 독립 관측이 있다. 앱에 불필요한 polling이나 추가 resize fallback은 넣지 않았다.

그 밖의 하네스 제약: 외부 Font Awesome CSS를 차단해 VCP 전체 삭제 버튼이 0×0이므로 실제 키보드 focus+Enter로 활성화했다. floating widget이 전송 버튼을 가리는 기존 FE-010 상황에서는 입력창 Enter를 사용했다. DOM·React 상태를 강제로 바꾸지 않았다. 초기 스크린샷 timeout과 잘못 읽은 ref는 통과 근거에서 제외했다. `qa2-next-runtime.txt`의 브라우저 미연결 결과도 성공으로 세지 않고 연결된 `qa3-next-runtime.txt`로 확인했다.

## 정리와 잔여 한계

- 부모·보조 namespace의 브라우저를 종료했다. 보조 profile은 정확한 경로를 휴지통으로 옮겼으며 보안 삭제를 주장하지 않는다.
- 소유 PID와 실행 명령을 대조한 후 57601/57602 서버 프로세스 그룹을 종료하고 리스너 부재를 확인했다.
- scratch 전체를 제거했다. venv symlink의 원본 대상은 삭제하지 않았다. 재현용 스크립트와 판정 증거는 저장소에 보존했다.
- 원본 data 최상위 목록 27,484개와 SHA가 baseline과 같고 사용자 미추적 package.json SHA도 동일하다. 데이터 내용 전체의 불변을 해시로 증명한 것은 아니다. 재개 시 재귀 목록으로 잘못 계산한 불일치는 baseline 집계 방식을 확인해 해결했다.
- 완전히 같은 timestamp를 가진 옛 임시 명령의 시각적 위치는 best effort이며, 서버 삭제 인덱스에는 영향을 주지 않는다. 실제 외부 서비스와 사용자 비밀·로그인을 이용한 검증은 수행하지 않았다.

필수 시나리오: 8/8 통과. 미통과 필수: 없음. 정리: 완료.

ULTRAQA COMPLETE: Goal met after 3 cycles
