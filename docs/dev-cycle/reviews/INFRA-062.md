# INFRA-062 리뷰 기록

- 승인: 현재 대화의 method/path v2·구형거부 설계 후 사용자 「진행해」.
- 기준 a464a30; 설계/계획 커밋9fdb1f9, critic 보완 diff 포함.
- 실행: 승인된 계획을 native executor의 Python/Next 레인으로 나누고 root가 경계fixture·문서·통합을 담당했다. 독립 테스트 엔지니어는 cross-runtime proof, 다른 executor는 실제 transport 하네스를 담당한다. dev-cycle 순서가 외부 구현 스킬의 커밋/리뷰순서보다 우선한다.
- 환경: 독립 clone develop. 원본 .env/data/3500/5501/live 접근 없이 준비 baseline pytest1914/vitest365 PASS. package.json 보존. native hook 상태를 쓰지 않는다.

## 계획 critic

초기 피드백은 실제 transport 기대값과 malformed HTTP assertion, 완전한 파일경로가 필요하다는 것이었다. spec의 raw→Next→decoded→Flask/status/hit 표와 http.client 원문 입력, Next기본trailing308을 추가했다. 추가 피드백에 따라 env추적·응답/로그·clientbundle 비노출의 구체assertion과 증거경로도 적었다.

최종 원문은 evidence/INFRA-062/plan-critic.json에 보존했다. 판정 OKAY.

## 구현 확인

- root replay RED: 구형헤더로 보호경로에200이 반환되어 expected401 검사 실패. 테스트인터페이스에없는인자오류가아닌실제보안동작 RED.
- Python unit에는 새 method인자 미지원 TypeError RED 기록도 있으며 별도로 구분한다.
- Python 및 실제 경계112 PASS. 최초 root fixture가 bareBlueprint '/refresh' 대신운영prefix '/api/kr/refresh'로서명해1실패했고, assertion을유지한채실제fixture경로로고쳐통과했다.
- Next target27/full373/typecheck/lint0errors(199warnings) PASS 보고. root최종통합검증은후속기록.

## 리뷰 상태

- ponytail: `Lean already. Ship.` 추가수정없음. 원문 evidence/INFRA-062/ponytail.json.
- code/security: APPROVE, architect: CLEAR. 원문 evidence/INFRA-062/code-review.json, architecture-review.json. 원문/24개입력hash가보존됨.
- deep review: APPROVE. 코드와하네스수리delta 원문은 evidence/INFRA-062/deep-review.json. 미해결0.

심층검토 중 QA하네스의 Next-only 로그검사와 leader종료시잔존child를거짓정리완료로기록하는문제를발견했다. Flask로그분리·종료후scan, exactPGID확인과leader reap을보완하고 alive/dead leader 두조건의network-free cleanup회귀를검증한다. 제품코드는이보완으로바뀌지않는다. 최종delta판정전에는QA실행/완료를주장하지않는다.
