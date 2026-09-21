## 요약

`CLEAR` 유지입니다. `MarketGate`는 삭제된 `create_market_gate` 외에 남은 참조가 없으며, import 제거는 동작 변경 없이 `scripts/init_data.py`의 불필요한 모듈 결합과 import 비용을 줄입니다.

## 분석

- 현재 import 목록에는 `engine.market_gate`가 없고 파일 전체에도 `MarketGate` 참조가 없습니다. [scripts/init_data.py:65](/Users/freelife/vibe/lecture/hodu/closing-bet-demo/scripts/init_data.py:65)
- 리뷰 diff에는 이 한 줄 제거가 정확히 포함됐습니다. [review-diff.txt:683](/Users/freelife/vibe/lecture/hodu/closing-bet-demo/docs/dev-cycle/evidence/vcp-cleanup-20260921/review-diff.txt:683)
- 현재 `scripts/init_data.py` SHA `3749f7d0...`가 갱신된 동결 파일과 일치합니다. [review-frozen.json:4](/Users/freelife/vibe/lecture/hodu/closing-bet-demo/docs/dev-cycle/evidence/vcp-cleanup-20260921/review-frozen.json:4)
- raw diff, gzip 해제 결과, `raw-index.json`의 SHA가 모두 `705f27c2...`로 일치해 stale index 문제도 해소됐습니다. [raw-index.json:3](/Users/freelife/vibe/lecture/hodu/closing-bet-demo/docs/dev-cycle/evidence/vcp-cleanup-20260921/raw-index.json:3)

강한 반론은 미사용 import도 대상 모듈의 import-time 부수효과를 실행할 수 있다는 점입니다. 허용된 소스 범위에는 그 부수효과에 의존한다는 증거가 없으며, 이미 해당 기능 진입점 자체를 의도적으로 제거했으므로 그런 숨은 결합을 유지할 이유가 없습니다.

## Architectural Status

`CLEAR`

`pytest:deep-final` 결과는 전체 마감 검증 게이트로 별도 확인하면 됩니다. 이번 한 줄 delta 자체에서 추가 아키텍처 조치는 필요하지 않습니다.
