# Ponytail 반영

- summary의 중복 ticker/entry 전처리 제거: 공통 trade 생성 경계에서 검사한다.
- build_cumulative_trade_record의 중복 가격 보정 제거: metrics에서 한 번 해석한다.
- 새로 추가했던 수동 signature 캐시 검사 2개 제거: 실제 signature builder와 캐시 save/get을 사용하는 기존 검사를 유지한다. 현재기본값변경에맞춰 summary 검사 버전99 사용.
- 별도 리더 검수에서 NaN 진입가가 거래로 만들어지는 경우 재현(RED), 공통 trade 경계의 isfinite 검사와 회귀로 보완. 실제 시그널·과거 AI 원문은 변경하지 않는다.
- 영향 targeted pytest: ponytail-green.json.
