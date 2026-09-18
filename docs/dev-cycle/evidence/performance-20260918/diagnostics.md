# 정적 진단 경로

OMX lsp_servers는 typescript.available=true를 반환했지만 version에 실제 TypeScript 버전 대신 `This is not the tsc command you are looking for` 및 설치 안내가 들어 있었다. 프로젝트용 진단 백엔드가 정상이라고 판정하지 않는다. 이 가용성 조회를 typecheck 성공으로 세지 않는다.

부모가 sandbox scratch의 frontend에서 설치된 프로젝트 `npm run type-check`를 build 종료 후 실행했다. typecheck-final2.json/log가 명시적 tsc --noEmit 성공 근거다. 독립 reviewer는 원본에서 LSP/tsc/test를 실행하지 않고 이 해시와 실행 기록을 읽는다. Python은 전체 pytest2310/3skip과 변경 함수 회귀로 검증했으며 Python LSP 성공을 주장하지 않는다.
