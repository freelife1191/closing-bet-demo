# UltraQA Report

## 상태

engine: ultraqa; lifecycle: app-adapted; phase: blocked; iteration: 1; same_failure_count: 1.
**ULTRAQA BLOCKED: pykrx 1.2.7+가 KRX 세션 쿠키를 다른 출처의 HTTP 요청에 전달한다.**

NumPy2.4.6/pykrx1.2.7은 소유venv에서 설치·pipcheck·pytest2447/3skip·Vitest640·typecheck/lint를통과했다.
이 성공만으로 업그레이드를 완료하지 않았다. 후속 실제Naver/Get·실제KRXSession.get_headers 검사에서 보안 경계가 실패했다.

## 시나리오

| ID | 의도/사용자 모델 | setup·harness | 기대 | 실제 | 결과 | 증거 | cleanup | required |
|---|---|---|---|---|---|---|---|---|
| N1 | 의존성교체 | 소유venv+공식wheel SHA+offlinepip/pipcheck | 두버전정상/원본불변 | 2.4.6/1.2.7,충돌0 | 통과 | installed-metadata/wheel-sources | 소유venv정리 | yes |
| N2 | 지원JSON타입 | encoder9타입+unsupported object | 정확한값/TypeError | RED2→GREEN6 | 통과 | pytarget-red/green | 테스트사본정리 | yes |
| N3 | API변환 | 실제pykrx6API·Post만합성/HTTPguard | DataFrame값·외부0 | 6종정상 | 통과 | candidate/tests/fixtures/pykrx_contract_probe.py | 소유process종료 | yes |
| N4 | 인증경계 | 실제Naver공개API+KRXSession,가짜Cookie,전송capture | 타출처Cookie없음 | HTTP Naver에가짜Cookie붙음,실제외부0 | **실패** | session_probe.py/sessionprobe.log | 가짜session만종료 | yes |
| N5 | 실제Next UI | 후보backend→ego Space20 | 숫자/JSON정상 | N4실패로후속UI단계진입하지않음 | 차단 | 이보고서 | 새서버안띄움 | yes |
| N6 | 복원 | 후보파일보존후원본핀/encoder복원,기존deps소유clone | 기존버전/pipcheck/전체통과 | 1.26.4/1.2.3,pytest2444/3skip | 통과 | restoration/versions/pipcheck/pytest-restored | cleanup.json | yes |

브라우저 적용은required이며, N5를optional로바꿔완료시키지않았다. 원본.env/data/logs,실제KRX/Naver/LLM/쿠키·자격증명·서비스는사용하지않았다.

## 원인과 결정

새pykrx Get은 전역 KRX 세션의 수동 Cookie 헤더를 모든Get URL에전달한다. Naver의URL은http이며출처검사가없다.
가짜쿠키만으로전송직전인자를포착했다. 원본cookiejar를읽거나외부로전송하지않았다.
최신1.2.9와master도같은구현이므로단순버전상향으로해소되지않는다.

- [1.2.7 Get](https://github.com/sharebook-kr/pykrx/blob/v1.2.7/pykrx/website/comm/webio.py)
- [인증헤더구성](https://github.com/sharebook-kr/pykrx/blob/v1.2.7/pykrx/website/comm/auth.py)
- [Naver URL](https://github.com/sharebook-kr/pykrx/blob/v1.2.7/pykrx/website/naver/core.py)
- [최신1.2.9](https://pypi.org/pypi/pykrx/1.2.9/json)
- [현재master Get](https://github.com/sharebook-kr/pykrx/blob/master/pykrx/website/comm/webio.py)

교육용프로젝트의최소버전승격범위를넘는전역monkeypatch/vendor fork를만들지않고기존핀을유지한다.
후보5파일은evidence/candidate에보존했으며원작업트리제품변경은전부복원했다. 원본venv도바꾸지않았다.
INFRA-018은TODO에유지하고완료아카이브를만들지않는다. 해제는업스트림의출처별세션격리수정 또는별도검토된대안이필요하다.

## 실행 실패 이력

설치1회는sandbox literalIP문법거부(exit65),2회는sandbox DNS차단(exit1)으로패키지변경전에실패했다.
허용호스트와해시를검증하는stdlib다운로더→네트워크없는offlinepip로해결했다. 패키지자체실패로오인하지않음.
복원검사실행기의문자열따옴표오류는제품실행전에고쳤다. 후보보안실패와분리한다.

## 잔여

필수N4실패/N5차단. 전체성공아님. 보안review 최종BLOCK, 후보의기존APPROVE/WATCH는상위성공판정으로재사용하지않음.
