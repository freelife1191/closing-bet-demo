# JONGGA-012·013 완료 보고

승인한 두 라운드를 구현·검토·실측·정리까지 완료했다. 구현은 `252568c`, 모바일 QA 수정은 `ba91b8e`, 실측 증거는 `ebdba7d`에 기록했다. 검증한 변경을 로컬 develop에 통합했다.

## 변경

- 종가베팅 생성의 기본 목표·손절 폭을 **+5%/-3%**로 모았다. 저장된 유효 가격은 우선하고 누락값만 보충한다. 정상 생성은 SignalConfig를 사용하며, 예외 폴백도 사용자 지정 비율을 유지한다.
- 요약과 누적성과가 같은 거래 결과를 사용한다. 정확한 가격 도달, 같은 일봉의 손절 우선, 반올림된 미청산 수익률을 승리로 오인하지 않는 조건을 확인했다. 과거 종목코드 별칭과 파일명 기준일, 한쪽 가격만 지정한 경우의 비율 계약도 보존했다.
- 최신·과거 조회에 같은 가격 보정을 적용하고, 과거 파일과 AI 본문은 보존했다. 카드·점수표·전략 안내·성과 화면에는 시스템 가격 기준을 명시했다.
- 모바일 실측에서 가격 기준일과 체크리스트의 겹침을 발견했다. 작은 화면을 1열로 바꿔 교차 면적 **46.171875px² → 0**을 확인했고 데스크톱의 2열 배치도 유지했다.

## 검증

| 검사 | 최종 결과 |
|---|---|
| pytest | 2,249 통과, 기존 skip 3 |
| Vitest | 424 통과, 59파일 |
| Next build·TypeScript | 통과 |
| ESLint | 오류 0, 기존 경고 201 |
| [JONGGA-012 UltraQA](../qa/JONGGA-012.md) | 6/6 |
| [JONGGA-013 UltraQA](../qa/JONGGA-013.md) | 4/4 |

UltraQA는 Codex App 대응으로 2회 수행했다. agent-browser로 실제 Next 화면을 조작하고 합성 데이터와 실제 계산 함수, 실제 Flask history handler의 결과를 연결했다. 35개 스크린샷을 열어 확인했으며, 기록된 GET 166건은 모두 200이었다. 변경 요청은 없었고 브라우저·Next 컴파일·세션 오류도 없었다. 외부 공급자나 실계정 연결까지 검증한 것은 아니다.

## 리뷰와 남은 제한

계획 critic은 기존 native agent에 설치된 역할 지침을 적용한 대체 검토다. 이전 스레드 한도 경험에 따라 계획 단계에서 대체했으며, 이번 코드 단계에서는 새 전용 호출이 실제로 성공했다.

전용 ponytail 검토 후 전용 code-reviewer는 **APPROVE**, 독립 architect는 **WATCH(차단 0)**를 반환했다. 합성 판정은 **COMMENT**이며 이를 무조건 APPROVE로 바꾸지 않았다. WATCH는 생산 계약 밖의 DataFrame을 공개 helper에 직접 넣는 경우로, FLOW-015에 기록했다. QA CSS 수정의 전용 리뷰는 APPROVE/CLEAR다. T3 심층 검토는 설치된 review 체크리스트를 develop/base SHA에 맞춰 적용한 App 대응이다.

기존 챗봇 테스트의 타이머 경합은 INFRA-068, VCP 홈 안내의 기존 비율 불일치는 VCP-025로 이월했다. 빌드 격리 정책·실패 캐시·쿠키 입력 형식·ref 매칭의 준비 실패도 숨기지 않고 보존했다. 외부 CDN 아이콘 글꼴은 차단했으므로 일부 아이콘의 시각 검증에는 제한이 있다. 홈 기준 문구는 DOM으로, 가격·성과 수치는 화면과 응답으로 대조했다.

테스트 서버·브라우저·namespace·가짜 계정 자료·독립 clone·실행용 하네스를 제거했다. 원본 미추적 package.json과 venv를 보존했으며 운영 서비스의 재시작·배포는 수행하지 않았다.

증거: [QA 요약](../evidence/jongga-exits-2026-09-09/qa-verification.json), [코드 리뷰](../evidence/jongga-exits-2026-09-09/code-review.md), [아키텍처 리뷰](../evidence/jongga-exits-2026-09-09/architecture-review.md), [시각 검수](../evidence/jongga-exits-2026-09-09/visual-inspection.json), [정리](../evidence/jongga-exits-2026-09-09/cleanup.json).
