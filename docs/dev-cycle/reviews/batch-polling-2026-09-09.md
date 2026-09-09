# 후속 연속 묶음 결과 — 2026-09-09

4건을 완료했다. 기존 TODO 62건에서 검증 중 발견한 INFRA-069를 추가하고 4건을 완료해 59건이 남았다.

| 항목 | 결과 | 구현 커밋 |
|---|---|---|
| JONGGA-014 | 이전 필수 웹 QA 실패를 보완해 최종 4/4 | a8a781c, b50854c |
| JONGGA-032 | 화면 이탈·시간 제한·완료 시 폴링 정리, QA 6/6 | b50854c |
| JONGGA-037 | 완료 응답 뒤 버튼 복구·재조회, QA 6/6 | b50854c |
| INFRA-069 | 뉴스 회귀 테스트의 실제 캐시 의존 제거 | b50854c |

## 변경 및 검증

종가 업데이트 폴링은 이전 렌더의 updating 값을 완료 조건으로 쓰지 않는다. 같은 타이머 생명주기 안에서 완료·350초 제한·화면 이탈을 정리하고, 늦은 응답은 무효화한다. 진행 중인 상태 요청이 있으면 다음 tick에서 요청을 겹치지 않는다. 새 의존성이나 공용 추상화는 추가하지 않았다.

뉴스 병합 테스트는 수집 mock보다 먼저 실제 캐시를 읽어 실패했다. 첫 두 테스트에서 cache load/save만 대역으로 바꾸고 정렬·limit·일부 소스 실패의 기존 기대값과 별도 캐시 테스트를 유지했다. 원본 캐시는 삭제하지 않았다.

- pytest 2,281통과·2skip. 초기 1실패와 보완 전후 로그 보존.
- Vitest 429통과·60파일. 대상 회귀 15통과, typecheck exit0, lint 오류0·기존 경고200.
- 독립 ponytail 및 code-review APPROVE, architect CLEAR. 리뷰 입력 해시와 실행 checkout 해시 일치.
- agent-browser로 실제 Next 화면에서 정상200·409·TypeError500·홈 이동 검증. 정상/409는 status2회·latest1회 후 버튼 활성,500은 예상 오류와 버튼 복구·추가조회0회,홈 이동 후 status13→13 고정.
- screenshot5개를 직접 열어 대조. 최초 URL-null SyntaxError1건은 새 세션7단계에서 미재현. 원인은 단정하지 않으며 최초 증거도 보존했다.
- UltraQA App대응 실행. native OMX 상태는 수정하지 않았다. Webpack 컴파일 MCP 도구 미지원은 실제 dev 컴파일 로그와 정적검증으로 대체했다.
- 2개 브라우저 세션, 소유 서버와 격리 checkout·fake env·쿠키를 정리했다. 사용자 root package.json은 불변이다. 원본3500/5501/live 재시작·배포·실제 LLM·거래·발송은 없었다.

검토·증거: [증거 디렉터리](../evidence/jongga-polling-20260909/), [종가 완료 QA](../qa/JONGGA-037.md), [기존 파이프라인 QA 재개](../qa/JONGGA-014.md).

## 후속 묶음 설계

FE-022와 FE-039는 같은 프로필 복원 흐름을 공유한다. 사용자 기본 이름의 출처를 맞추고, 저장된 직무가 목록 밖이면 직접 입력에 원래 값을 복원하는 bounded 설계를 제시했다. 새 항목의 설계 질문에 아직 답변이 없어 이 두 항목은 구현하지 않았다. 관련 경로는 frontend/src/app/components/{chatHelpers,Sidebar,SettingsModal}.tsx 또는 .ts와 chatbot/page.tsx다.

레거시 정리 후보들은 실제 호출·위임 경로가 남아 있어 일괄 삭제하지 않는다. 긴급성이 낮거나 상용서비스가 아니라는 이유로 TODO를 제거하지 않았다.
