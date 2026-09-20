# 리뷰 범위와 실행 대응

기준 5e21da2부터 이번 frontend 소스·테스트35파일과plan/QA/manifest. 기존 rootpackage미추적은 제외. ponytail→code-review+architect→T3 review 순서. security-review는 settings masking DOM/payload와권한유지범위 별도독립검토.

T3 review는 /Users/freelife/.codex/skills/gstack/review/checklist.md의 critical/info 두pass를 해당diff에적용한다. 원격PR/Greptile·홈telemetry·온보딩설정은수행하지않는다. 새SDK/의존성없음, Next번들문서및설치React타입으로검증한다. 사용자가선택한ego-browser외다른브라우저로조사하지않는다. 이대응은리뷰결함이나필수lane누락을PASS로바꾸지않는다.
