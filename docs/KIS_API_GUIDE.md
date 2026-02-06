# 🇰🇷 한국투자증권(KIS) API 연동 재개 가이드

이 문서는 추후 한국투자증권 계좌 개설 및 API 신청이 완료된 후, **장중 실시간 수급 연동 작업**을 마무리하기 위한 가이드입니다.

## 1. 개요
현재 코드(`engine/kis_collector.py`, `engine/market_gate.py`)는 이미 **KIS API 연동 준비가 100% 완료**된 상태입니다. API 키만 입력되면 즉시 실시간 수급 데이터 수집이 시작됩니다.

---

## 2. API 신청 및 키 발급 절차 (계좌 개설 후)

1. **API 서비스 신청:**
   - [한국투자증권 홈페이지](https://securities.koreainvestment.com/) 또는 앱 > 고객서비스 > 서비스신청 > Open API 신청.
   - **"일반용(개인)"**으로 신청하시면 됩니다.

2. **접근 토큰 발급용 Key 확인:**
   - **APP Key** (약 36자리)
   - **APP Secret** (약 180자리, 매우 깁니다)
   - **계좌번호** (종합매매위탁 8자리 + 2자리)

3. **모의투자 vs 실전투자:**
   - 실전 데이터를 원하시면 **실전투자용** 키를 발급받으세요.
   - 테스트만 하실 거면 모의투자를 신청하셔도 되지만, **수급 데이터는 실전용 API에서만 정확**하게 나옵니다.

---

## 3. 설정 적용 방법

프로젝트 루트의 `.env` 파일을 열고 아래 부분을 찾아 채워주세요.

```bash
# === Korea Investment & Securities (KIS) API ===
KIS_APP_KEY=여기에_APP_KEY_붙여넣기
KIS_APP_SECRET=여기에_APP_SECRET_붙여넣기
KIS_ACCOUNT_NO=본인계좌번호8자리+2자리(선택사항)
KIS_MODE=real  # 실전투자는 real, 모의투자는 virtual (수급 데이터는 real 추천)
```

---

## 4. 연동 확인 및 테스트 (추후 요청 시)

키를 입력한 후 저에게 **"KIS API 키 설정했어, 연동 확인해줘"**라고 말씀해 주시면 다음 절차를 수행해 드립니다.

### ✅ 자동 검증 스크립트 실행
```bash
# 토큰 발급 및 장중 수급 조회 테스트
python engine/kis_collector.py
```
- **성공 시:** `Token Success` 메시지와 함께 삼성전자 등의 수급 데이터가 출력됩니다.
- **실패 시:** 에러 메시지(유효하지 않은 키 등)를 분석해 드립니다.

### ✅ 실시간 로그 확인
서버가 실행 중이라면 로그(`logs/app.log`)에서 다음과 같은 메시지를 확인할 수 있습니다.
```
INFO:engine.kis_collector:KIS API Access Token issued and saved
INFO:engine.market_gate:KIS 실시간 수급 데이터 확보: Foreign=12345678
```

---

## 5. 현재 구현 상태 요약
- **`engine/kis_collector.py`:** 완료 (토큰 관리, 캐싱, 데이터 조회)
- **`engine/market_gate.py`:** 완료 (장중 KIS 우선 조회, 실패 시 CSV Fallback)
- **`scheduler.py`:** 별도 수정 불필요 (기존 1분 주기 로직에서 자동으로 Market Gate를 호출하므로, 위 코드가 활성화되면 자동 반영됨)
