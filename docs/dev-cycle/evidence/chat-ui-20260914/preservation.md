# 원본 보존 대조

원본 data/의 바로 아래 항목 이름을 정렬하고 개행으로 연결한 baseline과 동일하다. 27,484개, SHA256 dd1993f656484ad62a5cc63cfcaf6bf68eabd898df0dbbd7fab0cd17e2c1f215. 파일 내용 불변 증명이 아니라 목록 대조다.

재개 때 재귀 파일 목록으로 계산하여 불일치한 첫 검사는 집계 방식 차이였다. 재귀 파일 수 27,518개와 baseline의 최상위 항목 수를 혼동했다. baseline 방식으로 계산한 뒤 정확히 일치했다. 데이터를 바꾸거나 삭제하지 않았다.

사용자 미추적 root package.json SHA256: 4ef4b68fea412928af1832150490aaf5817d56c753e20a456f612142deaed3d8 (작업 전과 동일). 원본 단일 Vitest 실행 위반과 캐시 쓰기 가능성은 execution-deviation.md에 별도 보존한다.
