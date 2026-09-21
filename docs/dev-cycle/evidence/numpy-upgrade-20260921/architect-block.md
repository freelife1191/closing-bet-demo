## 요약

**아키텍처 판정을 `WATCH`에서 `BLOCK`으로 변경합니다.** pykrx 1.2.7의 전역 KRX 인증 세션이 Naver의 평문 HTTP 조회에도 재사용되며, KRX 쿠키가 수동 `Cookie` 헤더로 교차 출처 전송되는 경로가 외부 네트워크 없이 재현됐습니다. 현재 제약이 shim·원본 설정 수정을 금지하므로 NumPy 2/pykrx 1.2.7 승격을 보류하고 기존 핀으로 복원하는 방향이 맞습니다.

## 분석

- probe는 실제 `stock.get_market_ohlcv_by_date()` 공개 API를 호출하고, 발명한 비밀 아닌 쿠키가 `http://fchart.stock.naver.com/sise.nhn` 요청의 `Cookie` 헤더에 포함되는 것을 전송 직전 경계에서 포착했습니다. 실제 외부 요청은 0회였습니다. `docs/dev-cycle/evidence/numpy-upgrade-20260921/session_probe.py:9-21`, `docs/dev-cycle/evidence/numpy-upgrade-20260921/sessionprobe.log:1-2`
- pykrx 1.2.7은 import 시 KRX 인증 세션을 전역으로 설정하고, 모든 `Get` 하위 클래스가 이 세션의 헤더를 재사용합니다. `/private/var/folders/99/kpfx0mdj3fvbczqpbncjl0bm0000gn/T/numpy-upgrade-20260921-1c6rka1_/venv/lib/python3.11/site-packages/pykrx/website/comm/webio.py:5-14`, 같은 파일 `:28-50`
- `KRXSession.get_headers()`는 저장된 쿠키의 domain·path·secure 속성을 검사하지 않고 모든 쿠키를 하나의 수동 `Cookie` 헤더로 직렬화합니다. 로그인 성공 시 실제 세션 쿠키가 이 저장소에 복사됩니다. `/private/var/folders/99/kpfx0mdj3fvbczqpbncjl0bm0000gn/T/numpy-upgrade-20260921-1c6rka1_/venv/lib/python3.11/site-packages/pykrx/website/comm/auth.py:55-68`, 같은 파일 `:72-83`
- Naver 시세 클래스는 공용 `Get`을 상속하고 대상 URL은 HTTPS도 아닌 `http://fchart.stock.naver.com/sise.nhn`입니다. `/private/var/folders/99/kpfx0mdj3fvbczqpbncjl0bm0000gn/T/numpy-upgrade-20260921-1c6rka1_/venv/lib/python3.11/site-packages/pykrx/website/naver/core.py:1-24`
- 기존 pykrx 1.2.3은 전역 인증 세션 없이 `requests.get()`을 자체 헤더로 직접 호출하므로 이 쿠키 전달 경로가 없습니다. `venv/lib/python3.11/site-packages/pykrx/website/comm/webio.py:1-15`
- 앞선 `Post.read` 합성 계약은 NumPy/pandas 변환을 잘 검증했지만, 자격 증명을 제거하고 `Post.read`를 대체했기 때문에 이 결함을 구조적으로 보지 못했습니다. `tests/fixtures/pykrx_contract_probe.py:29-36`

## Root Cause

pykrx 1.2.7이 KRX 인증 세션을 **출처에 묶이지 않은 전역 HTTP 세션**으로 도입한 것이 근본 원인입니다. 쿠키를 Requests의 cookie jar 정책에 맡기지 않고 문자열 헤더로 만들어 모든 `Get`/`Post` URL에 붙이므로, Naver 같은 다른 출처와 평문 HTTP에도 KRX 쿠키가 전달됩니다.

현재 KRX 자격 증명이 설정되지 않았다는 반론은 즉시 노출 가능성을 낮출 뿐입니다. 로그인 기능이 활성화되는 순간 같은 바이너리와 코드가 위험해지며, 저장소는 그 설정을 영구히 금지하는 경계를 갖고 있지 않습니다.

## 권고

1. **현재 승격 후보 복원** — 즉시, 필수
   `requirements.txt`와 `numpy_json_encoder.py`를 기준 커밋 상태로 되돌리고, 새 3개 제품 테스트 파일을 작업 트리에서 제거하십시오. 후보 diff·해시·probe·로그는 evidence에 보존합니다.
2. **기존 핀 유지** — `numpy==1.26.4`, `pykrx==1.2.3`
   shim 금지 조건에서 안전하게 유지할 수 있는 유일한 현재 경로입니다.
3. **INFRA-018 미완료 유지**
   완료 아카이브로 이동하지 말고 “pykrx 1.2.7+의 교차 출처 쿠키 전달”을 차단 사유로 남깁니다.
4. **향후 해제 조건 명시**
   upstream이 URL origin별 세션 분리, 쿠키 jar의 domain/secure 정책 준수, Naver HTTPS 전환을 제공하고 이를 회귀 검사로 증명할 때 다시 승격합니다. 공식 1.2.9/master도 동일하다는 dependency-expert 결과가 맞다면 단순 상위 핀으로는 해제되지 않습니다.
5. **복원 후 검증**
   기존 venv에서 전체 pytest와 `pip check`를 새로 실행해 원래 핀 상태가 복구됐음을 확인합니다.

## Architectural Status

`BLOCK`

## 강한 반론

“현재 배포에는 `KRX_ID`/`KRX_PW`가 없으므로 쿠키도 없어 안전하다”는 반론은 조건부로 맞습니다. 그러나 이는 코드 안전성이 아니라 배포 설정 우연성에 의존합니다. 기존 핀이 같은 기능 요구를 충족하고, 새 핀의 인증 기능을 저장소 수준에서 불가능하게 만들 권한도 현재 범위에 없으므로 보안 위험을 받아들일 이유가 없습니다.

---
리더 실행: 원본venv에서제품을실행하지않고같은의존성의소유clone에서복원검증을수행했다. pytest2444/3skip,pipcheck통과. 현재배포의KRX설정유무는조회하지않았다.
