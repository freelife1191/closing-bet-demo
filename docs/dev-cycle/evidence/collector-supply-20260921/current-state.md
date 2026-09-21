# collector/supply current state

Active approved Native execution for INFRA-030+FLOW-014, plan63b1db0. Do not ask again.
Source edited on develop, execution only sandbox archive recorded review-input.json. No product commit yet.
Tasks1~4 implemented, Task5 UI complete; independent code+architecture rereview pending, T3 after both then firstcommit, egoQA,cleanup,archive.

Product: legacy KRX50methods moved into package/mixins, public init exports canonical classes, rootengine lazy2export fixes servicefirstimportcycle. BaseCollector reused; dead legacy Naver/News and orphan CSV cache helper removed. Dead KRXfundamental cache removed afterponytail. 24old modular-private tests retired with reasons and canonical replacements; surviving legacy contracts retained.
Personal: shared engine/investor_personal_flow.py validates5dates/finite values; CSV no personal→None, pykrx/Toss actual monetary values; schema marker on caches; completedetail legacy0→None; normalized reference stores personal dates and validates exact selected-date set. Marked malformed detailcache bool/nonfinite/string→None. UI0 versus 자료없음 and close/reopen recovery.
Flow: failedcache60sec/4096 monotonic fromcompletion, data_dir+provider+ticker+date key, Future singleflight+generation clear; SQLite publish serialized withclear. Historical candidates cut firstmax_stocks, only references4concurrent, pandas callerthread, duplicatecandidateoutputs retained.

Latest review frozen c62a0302df8a01781c71971d3444bbb7c42ed2f46ebe38dffc853f0a68e978e5 29paths incl27product/test+2plan/spec. review-frozen-before-review-fixes.json retains earlierinput. Do not mutate products without refreezing and rereview.
Ponytail2cuts applied. code-review first REQUEST CHANGES date loss plus importorder→fixed RED2/GREEN68. Parentmarkedcache RED4/GREEN34. code-review final pending agent supply_code_review.
Architect spawn failed threadlimit; delegated architecture prompt to existing independent quota_ticker_fixture (not thisimplementationauthor). Initial BLOCK056080fallback was wrong: compared dead modular KRX, selectedruntimelegacy neverhad056080. Architect withdrew BLOCK after directgitbaseline comparison. Final newSHA rereview pending; report fallback/dedicatedrole distinction honestly.

Baselinepytest2422/3skip, Vitest629. Afterimplementation pytest2435/3skip; latestpytest-final includes6newtests pending log. Vitest634/83PASS, build3PASS, typecheckPASS, lint0errors184warnings. UIoldthree-dashesexpectation updatedintentionally; firststringreplacementmissed sectionselector then corrected. No product bug hidden.
Performance sixruns actualreference+SQLite, synthetic600x50ms: median36.420962→10.083368sec,ratio.276856, all600fetches/outputdigest same, max4. Running bench:final against datefix code now (session85309), eachchildtimeout60, overall240.
Fixture: actualTossparser+actualstockdetail/cache→syntheticFlask→realUI. fixture:final sixmodes zero/positive/negative/missing/invalid/legacy match 0/100m/-100m/None/None/None inclSQLite reread; error503; forbiddenmutation405. No socketservers yet. Filesfixture/gateway/serve/stop_service ready, intendedownedports57940/41/42. Browser Space notcreated; read ego-browser skill already. First realbrowser call creates singleSpace/p1 after firstimplementationcommit. ego finish exactlyonce afterQA.
QA matrix docs/dev-cycle/qa/batch-collector-supply-2026-09-21.md Q1..Q9required, individual wrappers INFRA030/FLOW014. BrowserQ7/Q8/Q9notdone, no completion/archive. OMXstates untouched. Rootpackage hash4ef4b68fea412928af1832150490aaf5817d56c753e20a456f612142deaed3d8 preserved.

Ledger .superpowers/sdd/2026-09-21-collector-supply/progress.md with rulings. Generic worktree creation overridden by approveddevelop+scratch; generic one-passreview overridden repoT3+rechecks. taskdone records have base==head because devcycle firstcommit waits reviews+static.
Need retain raw review reports (agents authorized only own reportmarkdown writes), logs compress withSHA,index,images directview, current source/scratch/commit SHA matching beforecleanup. Final task5 completion includes requiredQA and cleanup; archive onlythen. End expected12→10TODO; no push/deploy.
