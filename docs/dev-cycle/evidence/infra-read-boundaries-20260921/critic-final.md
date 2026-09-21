**ACCEPT**

마지막 IP helper 모순이 해소됐습니다.

- Flask helper 두 곳: `request.remote_addr`
- 순수 chatbot helper: 전달된 `remote_addr`
- `forwarded_for`: 호환용 인자만 유지하고 무시

이제 계획은 구현자가 추측하지 않고 실행할 수 있으며, 앞서 지적한 scheduler·다중 워커 캐시·Market Gate GET·프론트 설명 범위도 모두 명확합니다. 외부 PaaS 사용은 미확인이고 외부 배포·재기동은 수행하지 않는 경계를 유지합니다.
