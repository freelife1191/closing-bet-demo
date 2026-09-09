Lean already.

`useChatStream.ts:340`은 기존 이벤트 계약을 현재 요청의 `finally` 가드 안에서 1줄 재사용합니다. 회귀 테스트도 done 시점 0회와 EOF 후 1회를 기존 fixture로 직접 고정합니다.

net 0 lines possible. 매니페스트 11개와 루트 `package.json` 해시가 일치합니다.

Ponytail verdict: Ship.
