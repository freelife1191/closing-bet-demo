# INFRA-051 심층 검토

- root가gstack-review/checklist를직접적용. base6147150,051-input.json6SHA일치. 제품3개·회귀2개·Task4계획검토.
- Critical: admin token gate가JSON파싱/파일접근보다앞선기존순서유지. invalid JSON은HTTP400/415를고정메시지로반환한다. 값이문자열이아니면invalid_type,비편집키는unsupported_key,제어문자/확장값은unsafe_value. 반환은키/고정이유뿐이다.
- 정상필드는기존부분반영을유지하며실제applied/removed/preserved목록으로결과를밝힌다. 모두거부시파일에접근하지않는다. accepted 필터를거친뒤기존잠금/원자쓰기/메모리적용순서유지,쓰기예외는generic500/type-only로그다.
- UI는rejected가객체인지확인후Object.keys만React텍스트로출력한다. 예외값/거부사유를그대로그리지않고 HTML삽입도없다. HTTP실패에서기존failed[]에이름을보강하므로프로필·관심종목독립저장구조유지.
- 새로운상태문자열은API의기존status ok/error이며test-send가저장결과를무시하는FE041은명시적후속Task5다. 이리뷰로Task5를완료했다고주장하지않는다.
- 대상147/backend·10/UI,전체pytest2220passed3skip/Vitest374passed57files/typecheck0/lint0errors204기존warnings. Python3파일AST/diffcheckPASS. MCP LSP/AST Transportclosed미실행과실행대체근거를분리한다.
- Next번들06-fetching/07-mutating/15-route-handlers를읽었다. 패키지/권한/네트워크대상변경없음. Pre-Landing Review: No issues found. APPROVE.
