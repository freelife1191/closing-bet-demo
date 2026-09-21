# 확인 근거와 한계
- engine/toss_collector.py get_financials는 두 재무 endpoint에 빈 POST body를 보낸다. periodType 지정 없음.
- parse_financials는 table[-1]의 값을 선택한다. 같은 row.period만 연결하며 이전행 기간을 추정하지 않는다.
- EPS 파서의 수익.data.epsKrw는 값만 있고 저장소에 기간 계약이 없다. TTM/연간 단정 금지.
- 기존 회귀 fixture는2025Q1 형식. 이는 합성 fixture이며 실제 공급자 전체 스키마를 증명하지 않는다.
- 공개 외부 API 수집/원본data 조사하지 않음. 특정종목 실제 부호차이의 회계 원인은 미확정.
- git57b83d2는 가산점 최대9(거래량4+장대양봉5),5a1200c는 최대7(5+1+1). 현재계산 초과불가.
- 과거저장값8/9에 표시를 달되 역사적 생성버전은 metadata가 없어 특정하지 않는다. 총점/등급/원본 보존.
- 조사agent 초기 breakdown 초과가능 추론은5+1+1 검증으로 기각,제품수정에 반영하지 않음.
