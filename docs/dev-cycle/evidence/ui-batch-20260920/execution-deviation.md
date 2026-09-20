# 실행 편차

ui_pages가 부모만 격리 사본에서 테스트한다는 지시를 어기고 원본 frontend에서 Vitest를 실행했다고 보고했다. 즉시 추가 원본 실행을 중단시켰다.

- 2026-09-20 17:01:25 KST: `npx vitest run`에 closing-bet/page.regression-fe-024, page.regression-jongga-010, vcp/page.regression-fe-013, data-status/page.test.tsx 네 파일 지정. 12실패10통과. data-status fixture 때문에 단건 text selector가 다건이 된 테스트 오류를 수정했다는 보고.
- 17:01:53 KST: 동일 네 파일을 각각 `--reporter=dot`으로 실행. 각각5/8,2/1,3/1,1/1 실패/통과. 원본 서버/HTTP/data/env 직접 접근은 하지 않았다고 보고.
- 보고에 원시 파일 로그는 없으며 도구 결과 요약이다. 실제 효과 전체가 없었다고 단정하지 않는다.
- 부모는 별도 archive sandbox에서 같은4파일을 새로 실행해 11실패11통과를 확인했다. 이 격리 결과가 구현 근거이며 `target-pages-red.log`/json에 보존한다. 이후 구현자 테스트실행 금지와 부모실행 원칙을 재전달했다.

## 부모 검증 게이트 실행 순서 오류

2차 커밋 직전 git diff --cached --check가 display-diff.txt의 원시 diff 공백 때문에 exit2였다. 부모가 그 결과를 읽기 전에 같은 orchestration 호출에 뒤따른 commit과 start_qa가 실행됐다. be36cb7 커밋과 소유 QA2 서버 시작은 이 게이트를 올바르게 거친 것으로 주장하지 않는다. 브라우저 QA2 조작은 아직 없었다.

원문 바이트는 display-diff.txt.gz에 보존하고 표시용 txt의 줄끝공백만 정리했다. 새로운 정정 커밋 전에 check를 독립 호출로 실행하고 exit0을 확인한다. 제품 소스 변경 없음. 재발 방지를 위해 게이트 결과가 필요한 후속 호출은 결과 확인 후 별도 실행한다.
