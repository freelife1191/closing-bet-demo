# 리뷰 실행 범위

일반 native code-reviewer/architect는 동일 SHA로 spec/quality와 architecture를 분리해 검토한다. T3 gstack review는 설치된 SKILL.md의 critical/info checklist를 추가 독립 code-reviewer에게 전달하는 저장소 대응으로 수행한다. 본체 checklist 파일을 실제 읽었다.

기준은 develop의 이번 5건 시작 커밋 b48c057부터 현재 소스다. 원격 PR·Greptile·origin/main 전체 diff를 검토한 것으로 보고하지 않는다. 외부 서비스 로그인·홈 텔레메트리·온보딩 쓰기는 이번 검토 범위 밖이므로 생략하고, 실제 verdict/근거는 이 evidence 디렉터리에 보존한다. 관련 SDK 변경이나 새 패턴 도입이 없어 외부 웹 조사 대신 설치된 Next 문서와 현 코드·검사 증거를 쓴다.

Task별 spec/quality는 공유 코드 리뷰에서 각각 판정한다. 사용자 최대 묶음 요청에 따라 파일이 겹치지 않는 native 레인을 병렬로 사용하되, 실행·통합·리뷰 gate·커밋·정리는 부모만 수행한다. 완료되지 않은 레인을 부모 자체 검토로 대체하지 않는다.
