# T3 review 실행 범위

설치된 gstack review preamble을 실행해 SKILL_START_PROTO1, interactive, develop을 확인했다. 로컬요청의범위는ac4ed20이후승인된3TODO다. origin/defaultmain전체diff나PR댓글/remote fetch로범위를넓히지않고동일diff에설치된review/checklist.md의Critical/Informational계약을네이티브독립code-reviewer로적용했다. 실제PR전체자동화/Greptile검토를실행했다고주장하지않는다.

검토순서: critic OKAY → ponytail SHIP → 독립code-reviewer APPROVE·architect CLEAR → T3심층REQUEST CHANGES → source가드+회귀 → 영향리뷰/정적재실행 → T3 APPROVE. 초기실패와원문보존. 네이티브LSP미지원은tsc정적증거와구분했다.
