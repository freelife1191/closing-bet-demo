# `.env` 파일 모드 0600 구현 계획

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 시크릿을 담은 `.env` 계열 파일이 같은 호스트의 다른 로컬 계정에 읽히지 않게 하고, 설정 화면의 쓰기 경로가 좁힌 모드를 되돌리지 않게 한다.

**Architecture:** 고칠 자리는 실측으로 하나로 좁혀졌다. `.env` 를 쓰는 두 경로 가운데
`atomic_write_text` 를 쓰는 쪽은 이미 0600 을 남기므로 손대지 않고, `open(w)` 로 쓰는
`update_env_file` 에만 `os.fchmod` 한 줄을 더한다. `.env` 를 자동으로 만드는 실행 경로는
`scripts/init_all.sh` 의 `cp` 한 줄이며, 사람에게 만들라고 지시하는 자리는 설치 문서에
있다. 이미 존재하는 운영 파일들은 코드가 아니라 일회성 `chmod` 로 좁힌다.

**Tech Stack:** Python 3.11 (`os.chmod`, `stat`), bash, pytest

**Spec:** 대화 설계(bounded). `docs/dev-cycle/TODO.md` 의 `[INFRA-053]` 항목이 근거이며
2026-09-08 `[INFRA-049]` 사이클의 `oh-my-claudecode:security-reviewer` 지적에서 나왔다.

## Global Constraints

- 티어는 T3 이다. `tier-rules.md` §2 「시크릿과 인증」이 「`.env` 로 시작하는 모든 파일」을
  접촉 패턴으로 정하므로 줄 수와 무관하다. §1 의 시크릿 확인 세 가지를 검증에 더한다.
- 운영 `.env` 의 **내용**은 읽지도 쓰지도 않는다. 이번 작업이 바꾸는 것은 모드뿐이다.
- 키 이름과 값의 유무·길이 외에는 어떤 값도 출력하지 않는다.
- 사용자가 방금 기동한 서비스(5501 gunicorn, 3500 next-server)를 재기동하지 않는다.
  `./restart_all.sh` 와 `./stop_all.sh` 를 실행하지 않는다.
- 임시로 띄우는 프로세스에는 `SCHEDULER_ENABLED=false` 와 `NOTIFICATION_ENABLED=false` 를
  반드시 함께 넘긴다. 운영 `.env` 의 `NOTIFICATION_ENABLED` 는 `true` 이고 디스코드 웹훅과
  텔레그램 토큰이 실제 값이다.
- `.env.example` 은 추적되는 공개 파일이므로 모드를 좁히지 않는다. `chmod` 대상은 glob 이
  아니라 파일명을 하나씩 지정한다.
- 백업 파일은 삭제하지 않는다. 되돌릴 수 없는 조작이라 이번 범위 밖이다.
- 루트 `package.json` 은 추적하지 않고 그대로 둔다. 다른 작업의 파일을 스테이징·삭제·
  스태시하지 않는다.

## 실측으로 확정한 전제

계획을 세우기 전에 스크래치패드에서 두 쓰기 경로의 실제 동작을 쟀다.

| 경로 | 기존 0644 파일 | 새 파일 |
|---|---|---|
| `update_env_file` (`open(w)`) | 0644 유지 | 0644 (umask 022) |
| `persist_market_gate_interval_to_env` → `atomic_write_text` | **0600 으로 좁힘** | 0600 |

두 번째 경로가 좁히는 이유는 `tempfile.NamedTemporaryFile` 이 0600 으로 만들고
`os.replace` 가 그 모드째 교체하기 때문이다. 그래서 이 항목이 고칠 자리는 첫 번째 하나다.

현재 모드가 0644 인 파일은 일곱 개다. `.env`, `.env.production`, `.env.bak.20260505_042017`,
`.env.bak.20260901_082418`, `.env.bak.20260901_084454`, `.env.bak.20260907_164102`,
`.env.production.bak.20260907_164335`. TODO 항목이 함께 보라고 적은 `.env.vertex` 는
이 저장소에 존재하지 않는다.

gunicorn 워커 셋과 next-server 는 모두 `freelife` 로 돌고 파일 소유자도 같으므로 0600 으로
좁혀도 읽는다.

`restart_all.sh:21` 이 `ln -sf ../.env frontend/.env` 로 심볼릭 링크를 만들지만, 링크 자체의
모드는 접근 판정에 쓰이지 않고 읽기가 원본으로 내려가므로 `chmod 600 .env` 하나로 덮인다.

`.env` 를 **자동으로** 만들거나 쓰는 자리를 저장소 전체에서 확인했다. `scripts/deploy_prep.sh`
는 `.env` 를 다루지 않고, `Procfile` 은 gunicorn 한 줄뿐이며, `restart_all.sh:18` 과
`stop_all.sh:18` 은 읽기만 한다. `.env.bak.*` 를 만드는 코드도 없어서 손으로 좁히면 코드가
되돌리지 않는다. 반면 **사람에게 `.env` 를 만들라고 지시하는 문서**는 일곱 자리에 있다.
`docs/INSTALLATION.md:46` 이 지금도 쓰이는 설치 안내이고, 나머지 여섯
(`docs/reference/PART_07.md:300`, `docs/reference/README.md:82`, `docs/DEBUG_GUIDE.md:112`,
`docs/SETUP_PROGRESS.md:86`, `docs/PROJECT_COMPLETION.md:123`, `docs/FINAL_REPORT.md:266`)은
완료 보고와 진행 기록이라 이번에 고치지 않는다. `docs/DEPLOYMENT_GUIDE.md` 는 `.env` 를
만들지 않고 키를 준비하라고만 한다.

---

### Task 1: `update_env_file` 이 쓰기 전에 모드를 좁힌다

**Files:**
- Modify: `services/common_env_service.py:174-176`
- Read: `services/kr_market_data_cache_core.py:146-172` (비교 대상인 다른 쓰기 경로)
- Test: `tests/app/test_common_env_service.py`

**Interfaces:**
- Consumes: 없음. 이 태스크가 첫 번째다.
- Produces: `update_env_file(env_path: str, data: dict[str, Any], environ: dict[str, str]) -> None`
  의 시그니처는 바뀌지 않는다. 부수 효과 하나가 추가될 뿐이다.

- [ ] **Step 1: 실패하는 검사를 쓴다**

`tests/app/test_common_env_service.py` 끝에 덧붙인다. 기존 파일의 관례대로 `tmp_path`
픽스처를 쓰고 새 프레임워크나 픽스처 계층을 만들지 않는다.

```python
def test_update_env_file_narrows_file_mode(tmp_path: Path):
    """0644 로 열려 있던 .env 가 저장 한 번으로 0600 이 된다.

    운영 파일이 실제로 0644 였고, 이 함수가 open(w) 로 쓰는 탓에 설정 화면을 아무리 써도
    모드가 좁아지지 않았다([INFRA-053]).

    파일이 없을 때 새로 만드는 경로는 따로 재지 않는다. 새 파일의 모드는 0o666 & ~umask 라
    umask 가 077 인 셸에서는 구현을 통째로 되돌려도 0600 이 나와, 검사가 구현이 아니라
    실행 환경을 재게 된다. 이 검사는 chmod(0o644) 로 시작 상태를 코드 안에 못박으므로
    umask 와 무관하게 언제나 결함을 잡는다.

    구현이 아니라 「이 함수가 끝나면 0600」이라는 동작을 재므로, [INFRA-050] 이 이 함수를
    atomic_write_text 로 옮겨도 그대로 통과한다. NamedTemporaryFile 이 0600 을 남기기
    때문이다. 그 리팩터링과 함께 지우지 않는다.
    """
    env_path = tmp_path / ".env"
    env_path.write_text("OPENAI_API_KEY=old\n", encoding="utf-8")
    env_path.chmod(0o644)

    update_env_file(str(env_path), {"OPENAI_API_KEY": "new-value"}, {})

    assert stat.S_IMODE(env_path.stat().st_mode) == 0o600
    # 모드만 보면 쓰기가 실패해도 통과한다. 값이 실제로 바뀌었는지 함께 본다
    assert env_path.read_text(encoding="utf-8") == "OPENAI_API_KEY=new-value\n"



def test_update_env_file_does_not_create_file_when_nothing_to_write(tmp_path: Path):
    """버려진 입력만 왔을 때 빈 .env 를 만들어 두지 않는다.

    ADMIN_API_TOKEN 은 EDITABLE_ENV_KEYS 밖이라 :116-120 의 필터에서 전부 떨어지고 :121 의
    이른 반환에 걸린다. 두 이른 반환(:109, :121) 가운데 하나라도 사라지면 open(w) 가
    존재하지 않던 파일을 빈 채로 만들고, 아래 단언이 그때 실패한다.
    """
    env_path = tmp_path / ".env"

    update_env_file(str(env_path), {"ADMIN_API_TOKEN": "blocked"}, {})

    assert not env_path.exists()
```

파일 맨 위의 import 에 `stat` 을 더한다.

```python
import stat
from pathlib import Path
```

- [ ] **Step 2: 검사가 실패하는 것을 확인한다**

```bash
source venv/bin/activate && pytest tests/app/test_common_env_service.py -k narrows_file_mode -v
```

기대: `AssertionError: assert 420 == 384` (0o644 == 0o600 비교의 십진 표기). 함께 넣는
`does_not_create_file_when_nothing_to_write` 는 지금도 통과한다. 그 검사는 이 항목이 고치는
결함이 아니라 이른 반환이라는 다른 축을 지키며, 구현을 넣은 뒤에도 그대로 통과해야 한다.

- [ ] **Step 3: 최소 구현을 넣는다**

`services/common_env_service.py` 의 파일 끝, `with` 블록 **안 맨 앞**에 한 줄을 더한다.

```python
    os.makedirs(os.path.dirname(env_path) or ".", exist_ok=True)
    with open(env_path, "w", encoding="utf-8") as file:
        # 이 파일에는 SMTP 비밀번호와 API 키, ADMIN_API_TOKEN, INTERNAL_IDENTITY_SECRET 이
        # 들어 있는데 운영 파일이 0644 였다. open(w) 는 기존 모드를 그대로 두고 새 파일은
        # umask 를 따르므로, 한 번 넓어진 모드가 설정 화면을 아무리 써도 좁아지지 않았다
        # ([INFRA-053]). 같은 .env 를 쓰는 다른 경로인 persist_market_gate_interval_to_env 는
        # atomic_write_text 가 NamedTemporaryFile(0600) 을 os.replace 로 옮기므로 이미 0600 을
        # 남긴다. 그래서 여기 한 자리만 맞추면 두 경로가 같아진다.
        #
        # 쓰기 뒤가 아니라 여기에 두는 이유는 open(w) 가 이 시점에 파일을 이미 0바이트로
        # 잘라냈기 때문이다. 비어 있는 동안 모드를 좁히므로 새 시크릿은 처음부터 0600
        # 아래에 놓인다. 쓰기 뒤에 os.chmod 를 두면 기존 0644 파일에서도 새 값이 쓰이는
        # 동안 0644 인 창이 남는다(실측).
        os.fchmod(file.fileno(), 0o600)
        file.writelines(new_lines)
```

- [ ] **Step 4: 검사가 통과하는 것을 확인한다**

```bash
source venv/bin/activate && pytest tests/app/test_common_env_service.py -v
```

기대: 기존 검사 다섯을 포함해 전부 PASS.

- [ ] **Step 5: 커밋하지 않는다**

Task 2 와 함께 첫 커밋으로 묶는다. dev-cycle `[3]` 검증 5번이 정한 첫 커밋 하나에
구현과 QA 시나리오를 담는다.

---

### Task 2: `.env` 를 새로 만드는 경로와 이미 존재하는 파일의 모드를 좁힌다

**Files:**
- Modify: `scripts/init_all.sh:103`
- Modify: `docs/INSTALLATION.md:44-46`
- 운영 파일 일곱 개 (저장소 밖, 커밋 대상 아님)

**Interfaces:**
- Consumes: Task 1 이 넣은 `os.chmod(env_path, 0o600)`. 그 한 줄이 있어야 설정 화면
  저장이 모드를 되돌리지 않는다.
- Produces: 없음. 이 태스크가 마지막이다.

- [ ] **Step 1: `scripts/init_all.sh` 의 생성 자리에 모드를 지정한다**

`cp` 는 원본 모드를 그대로 옮기지 않고 umask 를 따르므로, 여기가 0644 인 `.env` 를 새로
만드는 유일한 저장소 경로다.

```bash
        log_info ".env.example 파일을 복사하여 .env 생성 중..."
        cp .env.example .env
        # 곧 API 키와 SMTP 비밀번호가 들어가는 파일이다. cp 는 umask 를 따르므로
        # 여기서 좁히지 않으면 같은 호스트의 모든 로컬 계정이 읽는다([INFRA-053]).
        chmod 600 .env
        log_success ".env 파일 생성 완료 (템플릿 사용)"
```

- [ ] **Step 2: 설치 안내에도 같은 한 줄을 더한다**

`docs/INSTALLATION.md:46` 은 사람에게 `.env` 를 손으로 만들라고 지시하는, 지금도 쓰이는
안내다. 여기서 좁히지 않으면 새로 설치하는 사람마다 0644 를 다시 만든다. 「환경 변수
설정 (.env)」 절의 `ini` 코드 블록 뒤에 짧게 덧붙인다.

```markdown
파일을 만든 뒤 모드를 좁힙니다. API 키와 SMTP 비밀번호가 들어가는 파일이라 기본 모드로
두면 같은 호스트의 모든 로컬 계정이 읽습니다([INFRA-053]).

```bash
chmod 600 .env
```
```

같은 지시가 `docs/reference/PART_07.md:300`, `docs/reference/README.md:82`,
`docs/DEBUG_GUIDE.md:112`, `docs/SETUP_PROGRESS.md:86`, `docs/PROJECT_COMPLETION.md:123`,
`docs/FINAL_REPORT.md:266` 에도 있지만 그 여섯은 완료 보고와 진행 기록이라 고치지 않는다.
여섯 자리를 함께 손대면 기록을 사후에 바꾸는 셈이 되고, 실효는 `INSTALLATION.md` 하나에
있다.

- [ ] **Step 3: 문법을 확인한다**

```bash
bash -n scripts/init_all.sh
```

기대: 종료 코드 0, 출력 없음.

- [ ] **Step 4: 이미 존재하는 운영 파일의 모드를 좁힌다**

파일명을 하나씩 지정한다. `.env.*` glob 을 쓰면 추적되는 공개 파일인 `.env.example` 까지
걸린다.

```bash
chmod 600 .env .env.production \
  .env.bak.20260505_042017 .env.bak.20260901_082418 \
  .env.bak.20260901_084454 .env.bak.20260907_164102 \
  .env.production.bak.20260907_164335
```

- [ ] **Step 5: 모드와 수정 시각을 확인한다**

```bash
ls -la .env .env.production .env.example .env.bak.* .env.production.bak.* | awk '{print $1, $NF}'
```

기대: `.env.example` 만 `-rw-r--r--` 이고 나머지 일곱 개는 `-rw-------`. `chmod` 는
내용을 바꾸지 않으므로 mtime 도 그대로다.

- [ ] **Step 6: 좁힌 모드로 두 서비스가 계속 읽는지 확인한다**

사용자가 기동해 둔 프로세스를 재기동하지 않는다. 확인할 것이 둘이라 명령도 둘이다.

먼저 **모드를 좁힌 뒤에 새로 시작하는 읽기가 성공하는지** 본다. 이것이 이 항목의 유일한
회귀 위험이다. 이미 떠 있는 워커들은 `chmod` **이전에** `.env` 를 읽어 기동했으므로 그들이
200 을 돌려주는 것은 0600 을 읽을 수 있다는 증거가 되지 않는다. 서비스를 새로 띄우지 않고
같은 로더를 직접 부른다.

```bash
source venv/bin/activate && python -c "
from dotenv import dotenv_values
print('keys=', len(dotenv_values('.env')))"
```

기대: `keys=` 뒤에 0 이 아닌 수. 값은 출력하지 않는다. 읽기 권한이 없으면 개수가 0 이 된다.

그다음 **이미 떠 있는 두 서비스가 계속 응답하는지** 본다. `chmod` 가 그들의 열린 파일
기술자나 이미 읽은 값을 건드리지 않았음을 확인하는 것이다.

```bash
curl -s -o /dev/null -w "flask=%{http_code}\n" http://127.0.0.1:5501/health
curl -s -o /dev/null -w "next=%{http_code}\n" http://127.0.0.1:3500/
```

기대: 둘 다 200. `/health` 라우트는 `app/__init__.py:255` 에 실재한다.

---

---

### Task 3: QA 시나리오 문서를 만든다

**Files:**
- Create: `docs/dev-cycle/qa/INFRA-053.md`

**Interfaces:**
- Consumes: Task 1 과 Task 2 의 변경 전체. 시나리오의 기대값이 그 결과를 가리킨다.
- Produces: 없음. 첫 커밋에 함께 담긴다.

- [ ] **Step 1: `/qa-only` 로 시나리오를 확정한다**

형식은 `archive-format.md` §8 을 따른다. 출발점은 `docs/dev-cycle/TODO.md:43-44` 의 QA
시나리오 줄이다. 「`chmod 600 .env` 뒤 두 서비스가 정상 기동하고, 설정 화면으로 값을
저장해도 모드가 0600 으로 유지된다」.

담을 회귀 시나리오의 핵심은 뒤쪽이다. **설정 저장 경로를 실제로 태운 뒤 `stat` 으로 모드를
다시 재는 것**이 이 항목이 고치는 결함의 직접적인 재현이다.

- [ ] **Step 2: 저장 조작에 쓸 키를 고른다**

`SMTP_PORT` 처럼 값이 바뀌어도 발송이 일어나지 않는 키를 쓴다. **`DISCORD_WEBHOOK_URL`,
`TELEGRAM_BOT_TOKEN`, `TELEGRAM_CHAT_ID`, `EMAIL_RECIPIENTS` 는 쓰지 않는다.** 운영 `.env`
의 `NOTIFICATION_ENABLED` 가 `true` 이고 그 키들에 실제 값이 들어 있어, 과거에 이 경로로
운영 디스코드 채널에 실제 발송이 나간 사고가 있었다. 화면의 「알림 테스트 발송」 버튼도
누르지 않는다.

운영 `.env` 에 쓰지 않고 임시 파일 하네스로 같은 함수를 부른다. 원래 값으로 되돌리는
단계까지 시나리오에 적는다.

- [ ] **Step 3: 시나리오를 실행하고 결과를 기록한다**

`/qa` 로 실행한다. 결과·종료 코드·증거·정리를 같은 문서에 적는다.

---

## Self-Review

**1. 항목 체크박스 대응**

| TODO 체크박스 | 대응 |
|---|---|
| 계획 문서 작성과 `oh-my-claudecode:critic` 검토 | 이 문서와 그 판정 반영 |
| `update_env_file` 이 쓰기 뒤 모드를 보장하게 함 | Task 1 Step 3 |
| `scripts/init_all.sh` 의 `.env` 생성 자리에 모드 지정 | Task 2 Step 1, Step 2 |
| `.env` 계열 파일 일곱 개의 모드를 0600 으로 좁힘 | Task 2 Step 4 |
| 좁힌 모드로 gunicorn·Next 가 정상 기동하는지 확인 | Task 2 Step 6 + Task 3 |
| 리뷰 넷과 시크릿 확인 세 가지 | 아래 표 |

**1-1. `tier-rules.md` §1 의 시크릿 확인 세 가지**

| 확인 | 방법 |
|---|---|
| `.env` 로 시작하는 파일이 추적되지 않는가 | `git ls-files \| grep "^\.env"` 가 `.env.example` 만 낸다 |
| 키 값이 로그나 응답 본문에 실리는가 | 이번 변경은 값을 읽지도 쓰지도 않는다. `os.fchmod` 는 파일 기술자만 받는다 |
| 키가 프론트엔드 번들에 들어가는가 | `frontend/` 를 건드리지 않는다. `NEXT_PUBLIC_` 접두사를 새로 만들지 않는다 |

**2. 자리 표시자 점검**

「적절한 오류 처리를 더한다」류의 문구를 쓰지 않았다. 모든 코드 단계에 실제로 넣을 코드가
들어 있고, 모든 검증 단계에 실행할 명령과 기대값이 있다.

**3. 이름 일관성**

`update_env_file`, `env_path`, `atomic_write_text`, `persist_market_gate_interval_to_env` 는
모두 저장소의 실제 이름이며 태스크 사이에서 같은 철자를 쓴다.
