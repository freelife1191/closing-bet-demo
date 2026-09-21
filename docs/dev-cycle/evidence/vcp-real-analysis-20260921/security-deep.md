# 보안 및 별도 T3 심층 리뷰

Reviewer: /root/vcp_real_security (native App 대응, 실제 실행 없이 source/evidence만 읽음)

최초 SECURITY REJECT / T3 REJECT: 공개 GET /api/kr/ai-analysis?date 입력이 검증 없이 파일명으로 삽입되는 HIGH. abspath 정규화 후 자료 디렉터리 밖 JSON을 읽을 수 있는 경계. 원본 파일 또는 외부 요청으로 실험하지 않았다.

재검토 원문:

재검토 결과: **SECURITY APPROVE / T3 ACCEPT**

- `normalize_ai_analysis_date()`가 파일명 생성 전에 ISO·compact 날짜를 엄격한 정규식과 달력 검증으로 canonicalize합니다.
- `/api/kr/ai-analysis`는 잘못된 날짜를 파일 로더 호출 전 400으로 종료합니다.
- 새 경계 검사는 traversal·슬래시·빈 값·전각·달력 오류의 loader 호출 0과 정상 날짜의 고정 basename만 허용함을 다룹니다.
- 공통 AI writer도 같은 날짜 검증 함수를 사용합니다.

기존 architect WATCH인 서비스→`app.routes` private helper 지연 import는 이번 보안 지적과 무관한 nonblocking 관찰로 유지합니다.

리더 검증: read-date-red 8fail/1pass → read-date-green29PASS. 기존 독립 reviewer를 agent thread limit 때문에 재사용해 보안과 후속 심층 pass를 구분했다. 외부 Claude/gstack CLI나 home telemetry를 실행했다고 주장하지 않는다.
