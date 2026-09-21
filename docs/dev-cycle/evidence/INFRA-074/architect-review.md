# Independent architecture review

Reviewer /root/restart_arch_review, baseline92d84ab.

## Final original delta confirmation
Architectural Status: CLEAR

최종 변경은 기존 안전 경계를 유지하면서 실제 Bash 동작 문제를 바로잡았습니다.
- ps 출력 공백 제거 후에도 정확한 서비스 명령 검증을 유지합니다.
- 실행·정지 job 목록을 먼저 수집하고, parent PID·역할·cwd·시작 토큰을 다시 검증한 뒤에만 종료합니다.
- 실패 정리 후 포트가 남으면 PID 기록을 지우지 않고 orphan 또는 외부 관리자를 명시합니다.
- Ready! 전 backend와 frontend의 최종 이중 검증도 유지됩니다.

Current hashes:
restart_all.sh 0c5a27f5f4fe68d1cbb9a56da4f392c98a3645d272c2ff16dcded4e63ae1ed11
stop_all.sh 51d75910fa62c5476c4c54a02b9e29b71b470528b4e5c739347308164fe5b38c
scripts/service_lifecycle.sh 028f929c5abbaf5a57202dda77976f856a512250ef186648a57b5a334e7d6d0a
scripts/sync_dependencies.sh ecd34f67ab25b8f83cf9945579cd3d42be56d6647f6c080b391dd177bf090e70
pykrx cookie.2 3648009de4202f6087be7e8eef174a86c3d77eed6d3db60eb9ecf18ac6b8a099

테스트·네트워크·원본 환경 접근은 하지 않았습니다. git diff --check와 실행 권한은 정상입니다.

## Findings resolved across review
Executable mode; exact ownership; old launcher must exit before dependencies; newly started child cleanup independent of port/PID write; final readiness of both; post-termination port reoccupation; documentation of managed-only stop. Detached TERM-resistant descendants cannot always be proved without supervisor/process groups; final script retains evidence and fails honestly. This ceiling is documented, not an approval to kill unknown processes.
