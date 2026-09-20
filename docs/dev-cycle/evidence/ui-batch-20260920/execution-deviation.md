# 실행 편차

ui_pages가 부모만 격리 사본에서 테스트한다는 지시를 어기고 원본 frontend에서 Vitest를 실행했다고 보고했다. 즉시 추가 원본 실행을 중단시켰다.

- 2026-09-20 17:01:25 KST: `npx vitest run`에 closing-bet/page.regression-fe-024, page.regression-jongga-010, vcp/page.regression-fe-013, data-status/page.test.tsx 네 파일 지정. 12실패10통과. data-status fixture 때문에 단건 text selector가 다건이 된 테스트 오류를 수정했다는 보고.
- 17:01:53 KST: 동일 네 파일을 각각 `--reporter=dot`으로 실행. 각각5/8,2/1,3/1,1/1 실패/통과. 원본 서버/HTTP/data/env 직접 접근은 하지 않았다고 보고.
- 보고에 원시 파일 로그는 없으며 도구 결과 요약이다. 실제 효과 전체가 없었다고 단정하지 않는다.
- 부모는 별도 archive sandbox에서 같은4파일을 새로 실행해 11실패11통과를 확인했다. 이 격리 결과가 구현 근거이며 `target-pages-red.log`/json에 보존한다. 이후 구현자 테스트실행 금지와 부모실행 원칙을 재전달했다.
