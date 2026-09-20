# Ponytail — CUT 반영

storage_ponytail 초기29파일검토,잠재57줄감축권고.
적용: B6모듈의생성자max중복/forceFalse명시제거(ensure동적max유지); 내부prune공개export제거/private화; 캐시UPSERT기존_upsert_memory_rows_cursor재사용.
미적용: 한회사용실패callback을lambda로바꾸는스타일제안은named함수의loggerNone분기/가독성을유지한다. snapshot실패중복로그는DBcommit성공/스냅샷실패경계를설명하므로유지한다.
알려진no-opBEGIN문제는별도RED1후readonly probe/필요시transaction재조회로고쳤다.
기존gatealias/SQLJSON정규화헬퍼/회귀는계약상필요한것으로판정.
