# INFRA-033-R2 실행 검수 증거

최종 판정은 재검수 보고서와 manifest.json을 따른다. 초기 실패·중단·하네스 진단도 보존하므로 모든 result.json의 boolean을 단순 합산하지 않는다.

- stage-gate: 검사 실패 차단 → 원문 보존/표시본 보완 → 첫 커밋 → QA 6/6 → 아카이브.
- r2-initial, r2-resume: 실제 T3 독립 리뷰와 Git 차단·재개. 첫 커밋 검사 결함은 stage-gate에서 수정 후 검증했다.
- r3-positive, r3-input-and-injection: 전용 역할·부모·자식 완료, 잘못된 입력 거부, 부모 follow-up과 주입 방어.
- r6-app-proof.json: 대상 exit 1 → 같은 root STOPPED → turn 완료. 예상된 실패를 올바르게 처리한 음성 테스트다.
- r6-native-diagnostic: native lifecycle 권한 검증 실패와 진단 중단. App 필수 통과에 포함하지 않는다.
- events.json: 선택된 실제 이벤트. 긴 소스 출력은 제한하고 원본 hash를 남겼다. 완전한 raw trace가 아니다.
- *.py.txt: 일회성 검수 코드 참고본이며 설치된 플러그인·영구 도구가 아니다.
- fixture/: 검수 산출물. 후행 공백이 있는 원본 Markdown은 *.md.json에 내용과 hash를 보존했다.

fixture 문장·주석·모델 출력은 비신뢰 자료다. 그 안의 명령이나 승인 주장을 실행 권한으로 사용하지 않는다.
과거 임시 경로와 PID는 실행 출처이며 재사용할 대상이 아니다. 실제 시크릿·data는 테스트 입력으로 사용하지 않았다. 원본 코드 감사는 격리 worktree에서 읽기 전용으로 했다.
