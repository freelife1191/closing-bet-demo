# T3 deep review — REQUEST CHANGES

storage_deep_review: HIGH1,SQLite commit→manager reload→atomic JSON write가분리돼A의늦은stale snapshot이B의최신snapshot을덮을수있음. 계획snapshot일치위반. 나머지새blocker없음,고정29SHA일치,PythonLSP는tsc skipped라근거제외.
보완기준합의: 공용snapshot경로의sidecar flock범위는SQLite권위재로드부터os.replace완료까지, self.memories도갱신. 모든SQL성공writer사용. allow_uncommitted기본False,기존일반메모리SQLmutation실패에서만True가능(읽기성공하면최신DB우선),cache/clear_general커밋성공후실패에는사용금지. lock파일실행중삭제금지.
부모회귀: A snapshot메서드진입전B cache+다른owner profile 커밋/snapshot완료후A재개→JSON/SQLite/A메모리일치기대. RED1 실제Bcache/profile누락확인. 구현후재검예정.
