# Ponytail review

frontend/src/lib/api.ts:L27-31: yagni: 호출이 한 번뿐인 invalidJsonError 팩터리가 5줄을 차지한다. L73에서 `throw Object.assign(new Error('서버 응답이 올바른 JSON이 아닙니다'), { status: response.status });`로 인라인한다.
net: -5 lines possible.

그 외 generation+identity 가드와 snapshot identity는 계정 전환 늦은 응답/효과 실행 전 stale 표시를 각각 막는 필수 경쟁 보호. exact+bounded compatibility 조회와 충돌 우선순위는 승인 데이터 호환 계약. FLOW006은 facade3개삭제로 CUT 없음.

결정: CUT 수용, frontend 담당에 전달. 후속 code/architect 리뷰에서 최종 diff 확인.
