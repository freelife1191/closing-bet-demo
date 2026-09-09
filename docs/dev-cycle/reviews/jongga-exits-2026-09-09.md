# JONGGA-012·013 검토와 검증

- 승인: 기본 +5%/-3%, 저장된 개별 가격/AI 원문 보존, 백테스트·누락 보정·안내 일치. 현재 대화의 설계와 사용자 「진행해」를 근거로 수행했다.
- 구현: `252568c`, QA 모바일 수정: `ba91b8e`. 독립 develop clone에서 구현·검증했고 원본 서비스에 요청하거나 재시작하지 않았다.
- 정적: pytest **2249 통과 / 기존 skip3**, Vitest **424 통과 / 59파일**, 실제 Next build·타입 검사 통과, lint **오류0/기존경고201**.
- QA: [JONGGA-012 6/6](../qa/JONGGA-012.md), [JONGGA-013 4/4](../qa/JONGGA-013.md). UltraQA App 대응 **2회차**, agent-browser 실제 Next 화면·합성 데이터·실제 계산 함수·실제 Flask history handler를 사용했다. 공급자/실계정 연동 검증으로 세지 않는다.
- 상태: 필수검증10/10과런타임정리완료. 로컬통합·임시clone정리·아카이브마감중.

## 변경과 확인

생성 기본값을 공용 상수로 모으고 저장된 목표·손절가를 우선한다. 요약·누적성과는 같은 거래 결과를 사용하며, 109원 정확 도달과 같은 봉 손절 우선, 반올림상+5.0%인 미청산도 WIN으로 바꾸지 않는 것을 검사했다. 과거 별칭·파일명 기준일·혼합 가격/pct 인자를 보존했다. 최신·과거 응답의 보정은 저장 원문을 덮어쓰지 않는다.

화면에는 시스템 계산 기준과 AI 원문 출처를 구분했다. 모바일 실측에서 기준일과 체크리스트의 교차46.171875px²를 발견해 작은 화면1열로 수정했고, 재측정0과데스크톱2열복귀를확인했다. 35개 screenshot을실제로열었고GET166건이모두200, 변경요청0이었다. Next컴파일/세션오류와브라우저페이지/콘솔오류는없었다.

## 리뷰와 적용 방식

critic은기존native agent가설치된역할지침으로검토한대체경로이며, 원문은 [plan-review-final.md](../evidence/jongga-exits-2026-09-09/plan-review-final.md)에있다. 이전스레드한도경험에따라계획단계에서대체했으며, 이번코드검토단계의새전용호출은실제로성공했다.

전용ponytail후전용code-reviewer **APPROVE**와전용architect **WATCH(차단0)**를독립실행했다. 합성판정은**COMMENT**이며무조건APPROVE로표현하지않는다. WATCH는생산계약밖DataFrame의공개helper직접호출제한으로[FLOW-015](../TODO.md)에남겼다. QA한줄CSS수정은전용리뷰에서APPROVE/CLEAR다. T3심층`review`는설치체크리스트를develop/baseSHA에맞춘App대응으로수행했다. native gstack PR절차나OMX상태수명주기를실행했다고주장하지않는다.

## 실패 이력과 이월

빌드격리정책의localhost IPC차단과실패캐시, Cookie파일형식·ref매칭실수는하네스문제로수리후재실행했다. 기존chat004 타이머에의존하는중간렌더검사는전체실행1회실패뒤단독/전체재검증과소스불변을확인하고INFRA-068에기록했다. 중복수동캐시테스트2개는더강한기존실제signature builder검사를유지하면서제거했다. 알려진VCP홈안내의기준불일치는VCP-025로분리했다.

외부CDN아이콘글꼴차단으로일부아이콘시각확인은제한되며홈기준문구는DOM대조다. 가격·출처·점수표·성과표의판정은실제화면/요청/응답과연결했다. 원본package.json 미추적파일과원본venv는보존했다.

전체증거: [qa-verification.json](../evidence/jongga-exits-2026-09-09/qa-verification.json), [code-review.md](../evidence/jongga-exits-2026-09-09/code-review.md), [architecture-review.md](../evidence/jongga-exits-2026-09-09/architecture-review.md), [visual-inspection.json](../evidence/jongga-exits-2026-09-09/visual-inspection.json).
