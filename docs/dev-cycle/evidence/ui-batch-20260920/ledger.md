# SDD ledger — plan: docs/dev-cycle/evidence/ui-batch-20260920/plan.md

| Tasks | 공통경계 | 판정 |
|---|---|---|
| 1/2/3 | 독립파일 | 병렬소유 가능 |
| 2/4 | ModalShell props | 기존호환·portal·상단focus계약 공유 |
| 2/3 | Tooltip portal | dialog내부에 portal하여 inert와충돌금지 |
| 4/5 | 종가/VCP page | 1차 완료후2차수정 |
| 1 | masking | server PLAIN_ENV_KEYS유지, UI보완 |
| 2 | 초점과정리 | unit+실측 필요 |
| 3 | clipping | scroll/resize/초점/팝업hover 검증 |
| 4 | 모달호출부 | 거래/삭제미실행 |
| 5 | 표시 | 신호계산불변 |

Ruling: 사용자묶음처리와 AGENTS native독립레인 허용에따라1/2/3병렬. 저장소 develop규정에따라코드는현재checkout, 테스트는별도 archive scratch.

Plan critic REJECT→보완→OKAY. Task4는 Task2의 구현완료가 아니라 interface확정이선행조건이며 확정후별도page파일의회귀를병렬작성한다. Task5는여전히1차마감후. ui_settings/ui_modal/ui_tooltip/ui_pages는testsfirst→parentRED 확인대기. ui_fixture_fallback은terra capacity2회실패후sol대체(소유코드없음).

Baseline: pytest2314passed/3skip,Vitest506/71. App-adapted UltraQA. ego Space2/p1 생성. 아직 페이지 접근 없음.
Task1: parent RED11fail/13pass→GREEN24/24. Task2: parent RED16fail/7pass. Task3: parent RED13fail. Task4: parent RED11fail/11pass. All bounded runs in archive sandbox; task4 implementer original-Vitest deviation recorded separately. QA fixture safety probe PASS (required GET JSON200, mutations405, admin control).
Task2: 초기GREEN실패2건은fireEvent.click의focus누락 test입력, 이후initialFocusRefnull조기복사실제결함1건수정. parent modal-green3 24/24. Task3: popuphover버블로layout재초기화결함수정후13/13. Task4:22/22. 통합1:47fail은기존Modalmock/portal/닫힌Tooltip직접DOM질의/alertdialog와test타입오류분류; 통합2:535/538통과, 나머지3개같은Tooltip질의이관중. buildintegrated2실제3/3PASS, lint0오류191경고(SSRportalsetupwarning1개추가,억제없음).
Ponytail4지적모두반영후SHIP. UI전체review1 Vitest538/72,build3/3,lint0errors191warnings. Source35SHA일치. code-review/architect/security독립검토중. 실제브라우저아직미실행,첫commit전.
독립 code REQUESTCHANGES(close icon labels/hovergrace),architectBLOCK(z-order/hosttransform/noninteractivefocus). 회귀review-red12fail69pass확인. z-orderinline공용소유·hostfade→card·닫기이름수정후targetreview-green64/65. 남은1건은testregex의fade-in부분매칭오류라exactclass token으로수정;동작기대유지. Tooltip키보드/grace보완중. 승인반복없이같은범위수정.

Reviewfix: 전체Vitest546/72 build3/3PASS, 마지막Tooltip effectdeps/testjsxkey수정후targetTooltip16/16·lintreview3 0errors192warnings. 추가warning은DOMfocusable자손계산의layout effect1건(기존190+portalsetup1+focusable1). typecheckreview2실행.
QA1 U1설정mask/labels/편집취소/재진입·U3키보드focus/Tab·모달들·U4중첩z1000/1001·U6edge/모달첫줄/resize실측확인. U8 모바일VCP과거선택에서bulk버튼및금지사유가왼쪽으로잘림. ego-u8-vcp-disabled-mobile.png 직접열람하여필수실패기록.
Ruling: FE016(이미승인된후속4건)이U8을막으므로1차5건아카이브하지않고Task5를앞당겨9건통합최종QA로마감. 새범위없음/재승인불필요. 필수U8유지,완료0건. scratchb1718c6를계속검사하고root소스Task5는sync전까지영향없음. ui_pages에Task5testsfirst위임.
하네스편차: gateway 초기WebSocket미전달로Next HMR404와hydration대기. /_next/hmr tunnel추가후정상화. 잘못된정확buttonname/aria-attribute/h3대h4/중간has-text선택자시도는DOM대조후수정. UI성공으로세지않음. 초기sell이미지는transition중이라안정이미지재확인필요.
Task5 구현: parentdisplayRED8fail19pass+missinghelper suite→GREEN42/42. FullVitest558/74 build3/3 lint0. VCP수급금액의'주'표기오류는engine금액임계값으로단위확정해'원'수정; scratch구버전+새assert RED1fail2pass→GREEN3/3, typecheckpass. 현재43SHA원본/사본일치. ponytailSHIP,code/arch후속4건영향리뷰중. 기존모달/Tooltip/Settings소스불변.
Task5 추가리뷰D-only/0접두사보완. parentRED3fail17pass→최초GREEN시testselector이스케이프오류1건→정확class token으로수정후fullVitest561/74PASS. builddisplay-final3/3,lint0/192,typed0. codeAPPROVE/architectCLEAR,후속T3review중. 승인9범위제품구현완료,QA2아직미실행.

최종QA2 필수12/12 PASS. 138개API요청오류0/허용밖변경0,NextMCP빈목록,Spacefinish1회/서버3개및scratch/SDD정리. 독립verifier PASS/APPROVE 후9TODO아카이브. 잔여29건(P1 8/P2 21).
