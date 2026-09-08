# INFRA-063 메시지 발송 JSON 경계 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development or superpowers:executing-plans to implement this plan task-by-task. 프로젝트 dev-cycle의 리뷰·커밋·QA 순서가 우선한다.

**Goal:** POST /api/kr/jongga-v2/message가 관리자 JSON 객체 요청만 발송 처리로 넘긴다.
**Architecture:** require_admin 뒤에서 MIME·JSON 문법·객체 검사를 끝낸 뒤 기존 execute_json_route의 발송 처리로 진입한다. 공통 예외 처리기나 다른 라우트는 바꾸지 않는다.
**Tech Stack:** Flask/Werkzeug, pytest, Next proxy/rewrite, vitest.
**Spec:** 현재 대화의 bounded 설계: 비JSON415, 잘못된 JSON400, 정상 발송·중복 방지 유지, 격리 환경의 T3/UltraQA. 사용자는 설치 보완 후 「다음 진행해」, 중단 후 「계속 진행해」로 진행을 요청했다.

## Global Constraints

- 기준 5aab1dc, develop 독립 clone. 원본 .env/.env.production/.env.vertex/data 읽기·변경 금지.
- 원본 Next3500·Flask5501·https://close.highvalue.kr 요청 금지. 실제 LLM·발송·refresh·reset·거래·설정 저장 금지.
- 신규 의존성 없음. 원본 /Users/freelife/vibe/lecture/hodu/closing-bet-demo/package.json(기존 untracked) 해시 보존. 이 파일은 clone에 복사하지 않았으며 clone/frontend/package.json과 다르다. clone 부모 preservation.json에 원본 해시가 있다. 원본 운영 서비스 재시작·배포 없음.
- UI/Next 코드 변경 없음. 기존 호출 page.tsx:419는 application/json과 JSON.stringify({target_date: date})를 보낸다.
- field schema(target_date·force), nonce, 다른 실행/재분석 라우트는 범위 밖이다.
- JSON 객체 {}는 기존 최신 결과 의미를 유지한다. application/json 및 application/*+json 허용; MIME 매개변수 허용.
- 비JSON/빈 MIME 요청415, JSON MIME에 빈 본문/문법오류/비객체(null·배열·문자열·숫자·불리언)400.
- 인증은 앞에서 판정: 익명/비관리자는 JSON 여부와 무관하게403. OPTIONS는 기존 무부수효과 응답.
- 새 MIME·문법·객체 거부 응답은 일반 JSON 메시지이며 입력을 반사하지 않는다. 파싱 예외는 본문 없는 고정 로그.
- 기존 발송 실패500의 str(error)와 공통 wrapper 로그 정책은 이번 변경 밖(INFRA-038/043)이다. 발송 실패 복구 검사는 비밀 없는 fixture 오류를 사용한다.
- Q6 비노출은 새 입력거부의 본문 sentinel과 실제 통신의 fake identity secret/전체서명/MAC를 대상으로 한다. 모든 기존 발송 오류의 비노출을 보장했다는 뜻이 아니다.
- 프로젝트 스킬 순서 critic → TDD → ponytail → code-reviewer/architect·security → deep review → 전체 baseline → 첫 구현/행렬 commit(TODO 유지) → exact commit UltraQA → 증거 commit → 통합/정리 → archive.
- 검사180초, build/vitest300초, 독립 리뷰12분, HTTP하네스10분. QA 최대5회/동일실패3회.
- 진행 기록은 docs/dev-cycle/qa/INFRA-063.md와 reviews/INFRA-063.md; native OMX 상태는 변경하지 않는다.

## Task 1: 요청 파싱 경계와 회귀 검사

**Files**
- Modify: app/routes/kr_market_jongga_execution_routes.py (message route only).
- Create: tests/app/test_jongga_message_request_boundary.py.
- Existing regression: tests/app/test_kr_market_jongga_execution_routes_refactor.py, tests/app/test_admin_gated_routes.py (기대값 완화 금지).

**Interfaces:** 실제 _register_request_context + _register_jongga_message_route를 bare Flask에 등록한다. 가짜 Messenger만 외부 발송 대역으로 쓰고 실제 중복 guard는 tmp_path를 사용한다. 조회·객체생성·발송 횟수와 guard 디렉터리 불변을 관측한다.

- [ ] 승인된 형식에 대한 경계 테스트를 먼저 만든다. 폼 POST가 현행코드에서 발송 또는 조회에 닿고415기대가 실패하는 RED를 저장한다.
```python
@pytest.mark.parametrize("content_type,body,want", [
    ("application/x-www-form-urlencoded", "force=true", 415),
    ("text/plain", "{}", 415),
    ("application/json", "{", 400),
    ("application/json", "null", 400),
    ("application/json", "[]", 400),
])
def test_invalid_body_never_reaches_send(client, counters, signed_admin, content_type, body, want):
    response = client.post(PATH, data=body, content_type=content_type, headers=signed_admin)
    assert response.status_code == want
    assert counters == {"load": 0, "construct": 0, "send": 0}
```
- [ ] 최소 구현. get_json의 BadRequest를 공통 execute_json_route 밖에서 처리해500전환을 피한다.
```python
from werkzeug.exceptions import BadRequest

if not request.is_json:
    return jsonify({"status": "error", "error": "JSON 요청 본문이 필요합니다."}), 415
try:
    data = request.get_json()
except BadRequest:
    logger.error("Invalid JSON body for jongga message request")
    return jsonify({"status": "error", "error": "올바른 JSON 객체가 필요합니다."}), 400
if not isinstance(data, dict):
    return jsonify({"status": "error", "error": "JSON 객체가 필요합니다."}), 400
# 기존 _handler는 검증된 data를 사용한다.
```
- 익명·비관리자 각각에 비JSON 폼과 malformed JSON을 보내403과 load/construct/send/guard변화0을 확인해 인증이 파싱보다 앞임을 증명한다.
- [ ] 대상 pytest: 새 경계파일 + 기존 jongga 실행·관리자게이트 회귀. 정상 {}·날짜·null날짜·force true/false, 동일 날짜 중복, 발송 오류의 claim release 유지, JSON vendor MIME, 익명/비관리자/OPTIONS, 큰 잘못된 본문·Unicode·로그비반사 포함.
- [ ] 독립 ponytail 및 코드/아키텍처/보안/심층 리뷰. 원문·입력hash를 보존하고 지적을 반영한다.

## Task 2: 확정 커밋 실제 전송 검증과 마감

**Files**
- Create: docs/dev-cycle/qa/INFRA-063.md; docs/dev-cycle/reviews/INFRA-063.md; docs/dev-cycle/evidence/INFRA-063/.
- Update: docs/dev-cycle/TODO.md; docs/dev-cycle/archive/2026-09.md; docs/dev-cycle/archive/daily/2026-09-08.md.
- Temporary: clone 부모의 message_transport.py, 실행시 생성하는 fake fixture/로그. 원본 INFRA-062 transport/harness.py.gz의 소유 프로세스 정리 방식을 재사용한다.

**Interfaces:** actual Next dev(proxy/rewrite) → bare Flask + 실제 request-context/admin gate/message route. 합성 NextAuth admin/user JWT와 fake secret, dummy Messenger; load_json_file은 하네스가 만든 임시 fixture만 읽으며 기존 clone/data나 원본 data를 읽지 않는다. 실제 guard는 임시 디렉터리. 서버 도달, load/construct/send, guard 상태를 분리 관측한다.

- [ ] root가 전체 pytest·vitest·typecheck·lint를 실행한다. 외부 네트워크 금지 Python sandbox; 시작/마감 exit와 skip을 보존한다.
- [ ] 시크릿 검사: tracked .env.example만; client JS sentinel 부재; 응답/Next·Flask 로그 fake secret/서명/MAC 비노출.
- [ ] 첫 구현/행렬 commit 후 하네스가 HEAD 일치 확인. 정상200/send1 → 중복200/skipped/send1 → force200/send2; admin 비JSON415/invalid400은 load·construct·send·guard 변경0; cross-site/헤더없음403과 upstream0; anonymous/user403; OPTIONS no send.
- [ ] 실제 결과와 정리를 QA에 기록한다. 정리 시 Next process group과 Flask listener 종료, 임시 fixture 제거를 검증한다. 실패는 원인 수리 후 동일 행렬 재실행.
- [ ] 증거 commit(TODO 유지), 원본 HEAD/dirty/hash 재확인 후 fast-forward. 복제본 정리 후 최종 archive에서만 TODO 제거.
