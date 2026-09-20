# UI batch 합성 API fixture

이 fixture는 FE-032·030·036·037·017과 JONGGA-023·026·029·FE-016의 브라우저 QA에만 쓴다. 제품 Flask 앱이나 백엔드 모듈, 실제 DB를 import하지 않으며 합성 JSON만 응답한다.

## 실행 경계

- `git archive`로 만든 scratch checkout에서만 실행된다. 원본 저장소, `.git`이 있는 checkout, `.env`·`.env.production`·`.env.vertex`가 있는 checkout에서는 즉시 중단한다.
- `127.0.0.1`에만 바인딩하며 3500과 5501은 거부한다. QA 배치의 API 포트는 57622를 쓴다.
- 부모 gateway는 `/api` 전체를 이 fixture로 보내야 한다. 그러면 NextAuth 경로도 `/api/auth/session`의 합성 세션을 사용하고 실제 Next 인증·Flask API에 닿지 않는다.
- `POST`·`PUT`·`PATCH`·`DELETE`는 전부 405다. 예외는 `POST /__qa/control`과 가격 수집을 하지 않는 `POST /api/kr/realtime-prices`뿐이다.
- 요청 로그는 scratch의 `.qa-ui-batch/requests.jsonl`에 `method`, `path`, `status` 세 필드만 남긴다.

예시 실행 명령은 scratch 안에서 다음과 같다.

```bash
python docs/dev-cycle/evidence/ui-batch-20260920/fixture.py \
  --repo "$PWD" --port 57622 --reset-log
```

## QA 제어

`POST /__qa/control`은 두 필드만 받는다.

```json
{"mode": "admin"}
```

- `mode: "admin"`: 정상 신호와 `fakeadmin@example.test` 합성 NextAuth 세션을 쓰며 `/api/admin/check`는 `true`다.
- `mode: "normal"`: 정상 신호와 로그인된 일반 사용자 세션을 쓰며 관리자 판정은 `false`다. 설정 모달의 관리자 탭·환경 요청 차단을 확인할 때 쓴다.
- `mode: "empty"`: 관리자 세션을 유지하고 종가/VCP 신호만 빈 배열로 제공한다. 필터 0건과 원자료 없음은 각각 UI 필터 조작과 이 모드를 나눠 검증한다.
- `mode: "historical"`: 관리자 세션을 유지하고 최신 응답의 기준일을 2026-09-18로 내려 과거 자료·매수 금지 안내를 검증한다. 날짜별 history 경로도 별도로 응답한다.
- `admin: true|false`는 위 preset의 관리자 판정만 덮어써 조합이 필요할 때 사용한다.

제어 상태는 메모리에만 있으며 fixture 재기동 시 관리자·정상 자료 상태로 돌아간다.

## 제공 응답

- 인증·설정: auth session, admin check, 마스킹된 고정 환경값, 사용자/챗봇 quota, 빈 합성 채팅 기록
- 종가베팅: dates, latest/history, status, 세 종목 신호, stock detail
- VCP: signals/dates/status, AI analysis, market gate, stock chart, 합성 realtime prices
- 모의투자: portfolio, 종목별 포함 trade history, asset history
- 데이터 상태: data-status와 유휴 update-status

금액 경계 자료는 1조 2400억, 1조 2600억, 32억 7600만 4650원, 음수 대칭값을 포함한다. 종가 신호는 필터로 0건을 만들 수 있도록 등급·점수·상승률·거래대금을 다르게 하고, 전체 신호의 테마가 남는지 확인할 수 있도록 겹치는 테마와 고유 테마를 함께 제공한다. VCP의 두 번째 AI 의견은 HOLD 67%로 좁은 화면의 라벨 줄바꿈도 관찰할 수 있다.
