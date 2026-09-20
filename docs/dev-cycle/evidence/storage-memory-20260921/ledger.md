# 실행 기록

- 기준8b5f6d5,사용자4건설계승인. 원본package미추적보존.
- 스키마준비readiness-only통합:SQL/SeenKey/counter/prune정책유지. force재검사·동적max상한은실제기존호출자계약을공용gate에추가.
- 기준pytest2374/3skip,Vitest595/81PASS. 격리scratch·dotenv비활성·원본쓰기/data읽기/외부망차단.
- critic REJECT3(LOCKalias/clear의미/legacy재로드)→계약보완OKAY. gate RED3/기존20PASS→gate+chatbot schema GREEN58. memory RED4(profile노출/504rows/newAPI부재)확인후구현GO.
- A5 readiness이관133PASS,16모듈SQL AST호출인자불변. B레인원본검증편차발견→공식증거제외/격리재실행. execution-deviation.md에정확한한계와조치기록.
- 공식격리그룹순차검증: A133/B141/C105/D117 PASS(각각gate공유23포함,합계를유일test수로세지않음). readiness16모듈의SQL호출AST인자불변확인. B레인원본실행결과는포함하지않음.
- no-op정리도writer락요구하던문제 RED1([False,True...])→readonly probe후필요시BEGIN 재조회보완, memory87PASS/full2384/3skip.
- code/arch에서now TOCTOU HIGH BLOCK. writer/reader 실제2manager 교차RED2로정상신행삭제재현. 첫선택자-k오타exit5/0선택은하네스오류로분리하고올바른테스트RED만근거로사용. JSON/lookup2추가후관측·lock후clock으로고칠예정.
- fixture초기AppConfig readonlysetter실패→프로세스syntheticenv로교정,실제SSE/profile/history/4cache roundtripprobePASS. Chat추천dynamicAPI는현재frontend호출없어API probe로분류하고브라우저B2는대시보드캐시만검증.
- 정책시각4경계writer/reader/legacy/lookup RED2+1+1 재현후관측/BEGIN후시각으로수정. 해당범위85PASS. JSON추가테스트초안은전역snapshot last-writer문제를겨냥해실행전요청한legacy읽기시각검사로교정,그잘못된초안은RED근거로세지않음.
- T3deep HIGH: 늦은JSONsnapshot의다른worker최신state덮기. boundary-level회귀에Bcache+privateprofile+자기메모리동기화추가,RED1 실제누락확인. 공용sidecarlock+SQL권위refresh/replace로보완중,기존mutation실패fallback은명시옵션으로한정.
