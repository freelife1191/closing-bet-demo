# 증거 안내

검사 원문 `.log`는 Git ignore 대상이므로 같은 이름의 `.log.gz`에 무손실 보존한다. 검사 JSON은 명령·시각·종료코드와 연결된다. 오래된 `pytest-final`은 당시 중간 검사이며 최종 Python은 `pytest-approved` 2296/3skip이다. 최종 UI 수정은 `vitest-qa-fix` 460/67, lint/typecheck-qa-fix를 사용한다.

최초 검토는 7개 Python 파일, QA 수정 검토는 `63ec882` 이후 Sidebar의 2개 파일이다. 현재 review-input은 둘을 합친9개 해시다. 최초 원문을 현재검토로 위장하지 않고 qa-fix 원문과 함께 읽는다.
