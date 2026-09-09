# HTTP 오류 처리 라운드 결과

INFRA-017·038 완료. 구현 `214e996`, QA `3a8efc5`를 develop에 반영했다.

- 전역 및 common update wrapper에서 HTTPException의 상태·응답·헤더 보존.
- 일반500의 내부 경로·예외종류 비노출. 원인로그는 유지.
- 회귀12건 추가, 기존 오류2건을 새 응답 계약으로 갱신. pytest2232/3skip,Vitest405,typecheck0,lint0errors/204existingwarnings.
- ponytail/code-review APPROVE; architect BLOCK 원인(wrapper가400/415를500으로변환)을 수정해 CLEAR.
- UltraQA App 대응8/8. 실제 Next UI와 실제 Flask factory, HTTP10종, 스크린샷7장 검수. 배포·외부발송은 실행하지 않았다.
- 테스트 namespace·프로세스·합성자격증명·독립clone 정리, 사용자 root package.json/venv 보존.

QA: [INFRA-017](../qa/INFRA-017.md), [INFRA-038](../qa/INFRA-038.md). 검증 증거: [qa-verification.json](../evidence/http-errors-2026-09-09/qa-verification.json).

다음 항목 INFRA-045·046은 실제 Next 앞단 프록시와 Procfile 기반 PaaS 사용 계획이 필요하다. 그 답을 추정해서 배포 설정을 바꾸지 않았다. 범위 밖 개별 라우트 오류 wrapper는 INFRA-066으로 등록했다. 남은 TODO70건(P1 19/P2 51).
