# TODO 및 아카이브 기록 형식

dev-cycle 이 백로그와 완료 기록을 남기는 형식이다. 형식을 바꾸려면 이 파일만 고친다.

## 1. 파일 위치

```
docs/dev-cycle/
  TODO.md                    백로그. 대기 중이거나 진행 중인 항목만 담는다
  archive/
    2026-09.md               월별 요약. 완료 항목을 한 줄씩 적는다
    daily/
      2026-09-01.md          일별 상세. 완료 항목의 전체 기록
```

백로그는 `TODO.md` 한 곳에만 둔다. CLAUDE.md 를 비롯한 다른 문서에 할 일 목록을 중복해서
적지 않는다. 중복된 백로그는 반드시 어긋난다.

## 2. 항목 ID

`<카테고리 약어>-<세 자리 일련번호>` 형식을 쓴다.

| 약어 | 카테고리 | 주요 경로 |
|---|---|---|
| `CHAT` | 챗봇 | `chatbot/`, `app/routes/kr_market_chatbot_*`, `frontend/src/app/chatbot/` |
| `JONGGA` | 종가베팅 | `app/routes/kr_market_jongga_*`, `frontend/src/app/dashboard/kr/closing-bet/` |
| `VCP` | VCP 시그널 | `engine/vcp_ai_analyzer*`, `app/routes/kr_market_vcp_*`, `frontend/src/app/dashboard/kr/vcp/` |
| `FLOW` | 수급·백테스트 | `services/investor_trend*`, `services/kr_market_backtest_*`, `services/kr_market_flow_service.py` |
| `FE` | 프론트엔드 공통 | `frontend/src/app/components/`, `frontend/src/lib/` |
| `INFRA` | 인프라·패키지 | `requirements.txt`, `frontend/package.json`, `services/scheduler*`, `scripts/init_data.py` |

일련번호는 카테고리별로 독립 증가하며 완료 후에도 재사용하지 않는다. 다음 번호는
`TODO.md` 와 `archive/` 전체에서 해당 약어의 최대 번호에 1을 더해 정한다.

```bash
# CHAT 카테고리의 다음 번호를 구한다
grep -rhoE 'CHAT-[0-9]{3}' docs/dev-cycle/ | sort -u | tail -1
```

## 3. 우선순위

| 값 | 뜻 |
|---|---|
| `P0` | 즉시 처리한다. 동작이 깨져 있거나 다른 작업을 막고 있다 |
| `P1` | 이번 주기에 처리한다 |
| `P2` | 대기한다. 순서가 오면 처리한다 |

## 4. TODO.md 형식

```markdown
# TODO

> 백로그의 단일 관리 지점입니다. 형식은
> `.claude/skills/dev-cycle/references/archive-format.md` 를 따릅니다.
> 완료된 항목은 아카이브로 옮기고 이 파일에서 제거합니다.

## P0 — 즉시

### [INFRA-001] 파이썬 의존성 버전 고정
- 카테고리: 인프라 | 티어: T3 | 근거: AUDIT-INFRA §1
- [ ] requirements.txt 에 버전 핀 적용
- [ ] google-genai 2.x 호환성 확인
- [ ] 회귀 테스트 확인

## P1 — 이번 주기

### [VCP-001] ...

## P2 — 대기

### [FE-001] ...
```

각 항목은 제목 줄, 메타 줄 하나, 체크박스 목록으로 이루어진다. 메타 줄에는 카테고리와
티어를 반드시 적고, 감사에서 나온 항목이면 근거를 함께 적는다. 근거는 감사 리포트의
절 번호를 가리킨다.

체크박스는 실행 단위를 적는다. 세 개에서 여섯 개 사이가 적당하며, 열 개를 넘으면 항목을
둘로 쪼갠다.

## 5. 일별 상세 형식

`docs/dev-cycle/archive/daily/YYYY-MM-DD.md` 에 완료 순서대로 덧붙인다. 파일이 없으면
그날 첫 완료 시점에 다음 헤더로 새로 만든다.

```markdown
# 2026-09-01

## [INFRA-001] 파이썬 의존성 버전 고정
- 완료 2026-09-01 14:32 | 티어 T3 | 커밋 abc1234, def5678
- 변경: requirements.txt, engine/genai_client.py (+42 -18)
- 리뷰: ponytail-review(net -12) · code-review(3건 적용) · review(1건 반영)
- 검증: pytest 1515 통과 · vitest 160 통과 · qa 헬스 99
- 메모: google-genai 2.x 에서 GenerateContentConfig 시그니처가 바뀌어 대응했다
```

- **완료** 줄에는 시각, 티어, 커밋 해시를 적는다. 커밋이 여럿이면 쉼표로 잇는다.
- **변경** 줄에는 건드린 파일과 `git diff --stat` 의 증감을 적는다. 파일이 다섯 개를
  넘으면 대표 파일 세 개와 `외 N개` 로 줄인다.
- **리뷰** 줄에는 실제로 돌린 자산만 적는다. 티어가 T1 이면 `ponytail-review` 하나만
  적힌다. 각 자산 뒤 괄호 안에 결과를 요약한다.
- **검증** 줄에는 실행한 테스트와 그 결과를 적는다.
- **메모** 줄은 다음에 같은 자리를 건드릴 사람이 알아야 할 사실이 있을 때만 적는다.
  없으면 줄 자체를 뺀다.

## 6. 월별 요약 형식

`docs/dev-cycle/archive/YYYY-MM.md` 의 표에 한 줄을 덧붙이고 통계를 갱신한다. 파일이
없으면 그달 첫 완료 시점에 새로 만든다.

```markdown
# 2026-09 요약

| 완료일 | ID | 제목 | 카테고리 | 티어 | 커밋 |
|---|---|---|---|---|---|
| 09-01 | INFRA-001 | 파이썬 의존성 버전 고정 | 인프라 | T3 | abc1234 |

## 통계
- 완료 1건 (P0 1 · P1 0 · P2 0)
- 순 코드 증감 +24줄
```

통계는 항목을 추가할 때마다 다시 계산해서 덮어쓴다. 순 코드 증감은 그달 각 항목의
`변경` 줄에 적힌 증감을 합한 값이다.

## 7. 기록 시점

게이트 2 를 통과한 직후에 기록한다. `TODO.md` 의 항목 제거는 구현과 함께 첫 커밋에 담고,
일별 상세와 월별 요약은 그 커밋의 해시를 적어야 하므로 바로 뒤이은 둘째 커밋에 담는다.
월말에 몰아서 집계하는 배치 작업은 두지 않는다.
