Ponytail 리뷰 원문 판정: APPROVE
현재 frozen diff는 VCP-020/021/023/024의 승인 범위를 벗어나지 않습니다.

검토 결과:
- 날짜 정합성은 services/kr_market_vcp_payload_service.py에서 전체 signal의 단일 ISO 날짜를 증명한 뒤 날짜 파일을 선택하도록 바뀌었습니다.
- 날짜 파일 내부 signal_date 충돌, mixed/missing/invalid signal date는 fail-closed입니다.
- generic legacy는 현재 날짜이며 payload의 signal_date가 일치하는 경우만 보강에 사용됩니다.
- 추천 field 정본은 기존 결과 뼈대 모듈의 tuple 하나로 통합됐고 새 registry나 의존성은 없습니다.
- 1일 수급은 현재 engine/screener_result_builders.py에서 0으로 채워지던 값을 None으로 보존하고, CSV·batch·재분석 경로까지 전달합니다.
- rule fallback은 결측을 0/1.0으로 위조하지 않습니다. BUY는 여섯 필수 수치가 모두 있어야 하고, SELL은 실제 낮은 score 또는 실제 두 기간 음수 수급만 사용하며, 그 외 정보 부족은 HOLD로 처리합니다.
- 테스트는 기존 기대를 삭제하거나 약화하지 않고 날짜, provider field, 1일 수급, zero/NaN/inf, legacy 충돌, fallback 예외를 추가로 고정했습니다.
- 새 추상화, 중복 provider tuple, 범위 밖 UI/의존성 변경, 테스트만 통과시키는 우회는 발견되지 않았습니다.
- 현재 계획과 구현 사이의 중대한 누락은 없습니다. 전체 테스트 및 HTTP 실측은 요청대로 실행하지 않았습니다.

주요 파일/테스트 SHA: review-input.json. 최종 legacy 예외격리 delta는 별도 재검토.
