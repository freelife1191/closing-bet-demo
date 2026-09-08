#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Common Env Service

공통 라우트의 .env 관리 로직을 분리한다.
"""

from __future__ import annotations

import fcntl
import os
import re
from contextlib import contextmanager
from typing import Any, Iterator

from services.kr_market_data_cache_core import atomic_write_text


@contextmanager
def _env_file_lock(env_path: str) -> Iterator[None]:
    """`.env` 의 읽기-수정-쓰기 한 벌을 프로세스 사이에서 직렬화한다.

    설정 화면이 이 파일에 저장 요청을 내는 자리가 둘이다. SettingsModal.tsx:167 의
    「저장」 버튼과 :279 의 알림 테스트가 각각 POST /api/system/env 를 보내며, gunicorn
    이 워커 둘에 스레드 여덟로 뜨므로 동시에 처리된다. update_env_file 은 읽은 내용
    전체를 다시 쓰기 때문에, 옛 내용을 읽은 쪽이 나중에 쓰면 그 사이의 갱신이 자기 키
    하나가 아니라 통째로 되돌아간다. 두 요청 모두 성공을 반환하므로 화면에서는 보이지
    않는다([INFRA-050]).

    gunicorn 이 워커를 둘 이상 띄우므로 threading.Lock 은 통하지 않는다. fcntl.flock 은
    파일 기술자 단위라 워커 사이에서 배타적이고, 같은 프로세스 안의 서로 다른 기술자
    사이에서도 배타적이라 스레드로 재현하는 검사를 쓸 수 있다. fcntl.lockf 는 프로세스
    단위라 후자의 성질이 없다.

    잠금을 .env 자체가 아니라 별도 파일에 거는 이유는 os.replace 가 inode 를 갈아
    끼우기 때문이다. .env 에 걸면 교체 순간 잠금이 경로에서 분리된 옛 inode 에 남아,
    다음 주체가 새 inode 를 열어 거는 잠금과 서로 배타되지 않는다. 잠금 파일은
    .gitignore 의 `.env.*` 에 이미 걸리므로 작업 트리에 나타나지 않는다.

    **재진입이 불가능하다.** 진입할 때마다 새 os.open 을 하므로 같은 스레드에서
    중첩하면 flock(LOCK_EX) 이 자기 자신을 기다려 그 스레드가 영구히 멈춘다. 지금
    중첩하는 호출자는 없지만, 다른 .env 쓰기 경로를 이 함수에 위임하는 식으로 고치면
    곧바로 여기에 걸린다. 위임하는 쪽이 아니라 감싸는 쪽 한 자리에서만 이 잠금을 잡아야
    한다.

    **대기에 상한이 없고 gunicorn 의 --timeout 이 그것을 끊지 못한다.** 이 배포는
    --threads 8 이라 gthread 워커를 쓰는데, 그 워커의 run() 은 요청을 처리하는 스레드
    풀과 별개인 while self.alive 루프에서 self.notify() 를 부른다(gunicorn 25.0.3 소스로
    확인했다). 그래서 요청 스레드가 여기서 막혀도 마스터는 워커를 살아 있다고 보고
    죽이지 않는다. 막힌 스레드는 그대로 점유되고 여덟 번 반복되면 그 워커가 요청을
    하나도 받지 못한다([INFRA-050] Codex 적대적 리뷰).

    그래도 상한을 두지 않는다. 잠금 보유자는 아래 finally 에서 반드시 놓고 그 사이의
    작업이 밀리초 단위이며, 프로세스가 죽으면 커널이 놓는다. 무기한 대기가 실제로
    일어나려면 이 잠금 파일을 붙잡고 놓지 않는 다른 주체가 있어야 하는데, 그러려면
    저장소 루트에 쓸 수 있어야 하고 그 주체는 .env 를 직접 지우는 더 강한 수단을 이미
    갖고 있다. 상한을 넘겼을 때의 재시도와 오류 분기를 더하는 대가가 그보다 크다.

    O_NOFOLLOW 를 붙이는 이유는 os.replace 가 .env 의 링크 교체를 닫은 뒤 이 파일이 그
    표면을 물려받기 때문이다. 부모 디렉터리에 쓸 수 있는 주체가 이것을 자기가 이미 잠근
    파일의 링크로 바꾸면 저장이 무기한 대기한다. 정상 배포에서
    이 파일은 언제나 일반 파일이라 막는 것이 없고, 링크였다면 ELOOP 로 저장이 실패해
    조용히 엉뚱한 파일을 잠그는 것보다 낫다.

    닫지 않은 것 둘을 적어 둔다. 아래 0o600 은 파일을 **새로 만들 때만** 걸리므로, 누가
    이 파일을 미리 넓은 모드로 만들어 두면 그 모드가 남아 다른 계정이 잠금을 잡아 저장을
    막을 수 있다. os.fchmod 한 줄로 좁힐 수 있으나 넣지 않았다. 그렇게 하려면 저장소
    루트에 쓸 수 있어야 하는데, 그 주체는 .env 를 직접 지우는 더 강한 수단을 이미 갖고
    있어 이 자리에서 막을 것이 없다. 그리고 flock 은 NFS 같은 일부 네트워크 마운트에서
    호스트 로컬로 퇴화하므로, 저장소를 그런 마운트에 두는 배포가 생기면 워커 사이
    배타성이 조용히 사라진다([INFRA-050] 보안 리뷰 L1).
    """
    lock_path = f"{env_path}.lock"
    os.makedirs(os.path.dirname(lock_path) or ".", exist_ok=True)
    lock_fd = os.open(lock_path, os.O_CREAT | os.O_RDWR | os.O_NOFOLLOW, 0o600)
    try:
        fcntl.flock(lock_fd, fcntl.LOCK_EX)
        yield
    finally:
        os.close(lock_fd)


def _read_env_lines(env_path: str) -> list[str]:
    """`.env` 를 링크를 따라가지 않고 읽는다. 파일이 없으면 빈 목록을 준다.

    open(r) 은 링크를 따라간다. 이 파일을 읽는 경로가 둘인데 결과가 각각 다르게 나쁘다.
    update_env_file 에서는 아래 줄 루프가 data 에 없는 키를 무조건 보존하므로 링크 대상의
    내용이 그대로 새 .env 로 옮겨 붙고, 실측하면 대상에 둔 ADMIN_API_TOKEN 과
    ADMIN_EMAILS 가 그대로 나타났다. EDITABLE_ENV_KEYS 필터가 막으려던 바로 그 키들이
    파일 경로로 주입된 것이다. read_masked_env_vars 에서는 대상의 값이 관리자 화면에 뜨는데,
    PLAIN_ENV_KEYS 인 SMTP_HOST·SMTP_PORT·AI_PROVIDER 는 마스킹 없이 나간다
    ([INFRA-050] 적대적 리뷰).

    두 경로를 같은 함수로 맞춘다. 한쪽만 고치면 관리자가 화면에서 보는 파일과 저장이 닿는
    파일이 갈려 진단이 어려워진다.

    링크였다면 OSError(ELOOP) 가 그대로 올라가 저장이나 조회가 실패한다. 조용히 엉뚱한
    파일을 읽는 것보다 낫다. 운영 배포의 루트 .env 는 일반 파일이라 이 경로를 밟지 않으며,
    restart_all.sh 가 만드는 링크는 frontend/.env → ../.env 로 가리키는 쪽이다.

    exists() 사전 검사를 두지 않는다. 검사와 열기 사이에 파일이 바뀔 수 있고,
    FileNotFoundError 를 받는 것이 같은 판정을 한 번에 낸다.
    """
    try:
        read_fd = os.open(env_path, os.O_RDONLY | os.O_NOFOLLOW)
    except FileNotFoundError:
        return []
    with os.fdopen(read_fd, "r", encoding="utf-8") as file:
        return file.readlines()


# 설정 화면(`SettingsModal.tsx`)이 실제로 읽고 쓰는 키만 오간다. 나머지를 함께 실어
# 보내면 관리자 화면 하나가 .env 전체의 사본이 된다. 종전에는 키 이름에 KEY·SECRET
# 같은 단어가 있는지로 가릴지 정했는데, 그 방식은 해당 단어가 없는 변수를 그대로
# 흘렸고 그 안에 ADMIN_EMAILS 가 있었다. 화면에 필드를 더할 때 이 목록에도 더한다.
EDITABLE_ENV_KEYS = frozenset(
    {
        "AI_PROVIDER",
        "DISCORD_WEBHOOK_URL",
        "EMAIL_RECIPIENTS",
        "GOOGLE_SEARCH_ENGINE_ID",
        "OPENAI_API_KEY",
        "PERPLEXITY_API_KEY",
        "SMTP_HOST",
        "SMTP_PASSWORD",
        "SMTP_PORT",
        "SMTP_USER",
        "TELEGRAM_BOT_TOKEN",
        "TELEGRAM_CHAT_ID",
    }
)

# 값 자체가 화면 동작에 필요하고 새어도 무해한 키. AI_PROVIDER 를 가리면 공급자
# 버튼이 어느 것도 선택되지 않는다. 종전 규칙에서는 PROVIDER 안의 "ID" 가 걸려
# 실제로 마스킹되고 있었다. SMTP_HOST 는 smtp.gmail.com 같은 공개 주소이고, 아래
# MASK_KEEP_EDGES_MIN 을 올리면 짧아서 전부 가려지는 탓에 관리자가 어느 서버로
# 보내는지 화면에서 확인할 수 없게 된다.
PLAIN_ENV_KEYS = frozenset({"AI_PROVIDER", "SMTP_HOST", "SMTP_PORT"})

# 이 길이 이하의 값은 앞뒤를 남기지 않고 전부 가린다. 종전 기준은 8 이었는데, 그러면
# 16자인 Google 앱 비밀번호가 절반을 그대로 흘렸다. SMTP_HOST 와 SMTP_USER 가 같은
# 응답에 함께 실리므로 나머지만 맞히면 곧바로 인증된다.
MASK_KEEP_EDGES_MIN = 24

# 값 하나가 .env 의 한 줄로 끝나지 않게 만드는 문자들. 이 파일은 셋이 읽는다.
#
# 개행과 캐리지리턴: 한 항목이 두 줄로 나뉘어 EDITABLE_ENV_KEYS 밖의 키를 그대로 쓸 수
# 있다. `$` 뒤의 `{`·글자·숫자: python-dotenv 와 @next/env 가 `${VAR}` 와 맨 `$VAR` 를
# 보간하므로, 편집 가능한 키의 값에 `${ADMIN_API_TOKEN}` 을 넣으면 읽기에서 가려 둔 값이
# 그 키의 실제 값이 된다. 발송 대상 주소에 그것을 심으면 서버가 스스로 토큰을 보낸다.
# `$` 뒤의 `(`: 두 기동 스크립트가 이 파일을 통째로 source 하던 시절에는 명령 치환이 다음
# 기동에서 실행됐다. [INFRA-049] 가 그 source 를 걷어내 지금은 restart_all.sh:13 과
# stop_all.sh:15 가 scripts/env_value.sh 로 필요한 값만 읽으므로 그 경로는 닫혔다. 그래도
# 계속 막는다. 이 파일을 셸에서 읽는 방법이 다시 생길 때 이 한 글자가 없으면 그때 다시
# 열린다([INFRA-050] 보안 리뷰의 지적으로 근거를 갱신했다).
#
# `$` 하나만으로 막지는 않는다. `$` 로 끝나거나 `$!` 처럼 기호가 이어지는 비밀번호가 있다.
# 공백도 막지 않는다. Google 앱 비밀번호에 들어 있고 EMAIL_RECIPIENTS 가 `, ` 로 나눈다.
# 공백은 source 하는 셸에서만 위험하므로 [INFRA-049] 가 그 자리에서 없앤다.
UNSAFE_ENV_VALUE = re.compile(r"[\r\n]|\$[{(\w]")


def resolve_project_root() -> str:
    return os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def resolve_env_path(project_root: str | None = None) -> str:
    root = project_root or resolve_project_root()
    return os.path.join(root, ".env")


def _mask_env_value(key: str, value: str) -> str:
    if key in PLAIN_ENV_KEYS:
        return value
    if len(value) > MASK_KEEP_EDGES_MIN:
        return value[:4] + ("*" * (len(value) - 8)) + value[-4:]
    return "*" * len(value)


def read_masked_env_vars(env_path: str) -> dict[str, str]:
    env_vars: dict[str, str] = {}
    for raw_line in _read_env_lines(env_path):
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue
        if "=" not in line:
            continue
        key, value = line.split("=", 1)
        if not value or value.strip() == "":
            continue
        if key not in EDITABLE_ENV_KEYS:
            continue
        env_vars[key] = _mask_env_value(key, value)

    return env_vars


def update_env_file(
    env_path: str,
    data: dict[str, Any],
    environ: dict[str, str],
) -> None:
    if not data:
        return

    # 게이트를 통과한 관리자라도 화면에서 ADMIN_EMAILS 나 ADMIN_API_TOKEN 을 덮어쓰면
    # 자기 자신을 잠글 수 있다. 읽기와 같은 목록으로 쓰기도 막는다. 키만 보면 부족해서
    # 값도 함께 본다. 막는 것과 이유는 UNSAFE_ENV_VALUE 에 적어 두었다. 아래 두 쓰기
    # 경로에 각각 두지 않고 여기 한 자리에서 함께 막는다.
    data = {
        key: value
        for key, value in data.items()
        if key in EDITABLE_ENV_KEYS and not UNSAFE_ENV_VALUE.search(str(value))
    }
    if not data:
        return

    with _env_file_lock(env_path):
        lines = _read_env_lines(env_path)

        updated_keys: set[str] = set()
        new_lines: list[str] = []
        # 저장이 성공한 뒤에 옮기려고 모아 둔다. 루프 안에서 바로 고치면 저장이
        # 실패했을 때 그 워커의 메모리와 디스크가 갈리고, is_admin_email 처럼 매 요청
        # os.environ 을 다시 읽는 경로가 워커마다 다르게 동작한다.
        applied: dict[str, str] = {}
        removed: list[str] = []

        for original_line in lines:
            line_stripped = original_line.strip()
            if not line_stripped or line_stripped.startswith("#"):
                new_lines.append(original_line)
                continue

            if "=" not in line_stripped:
                new_lines.append(original_line)
                continue

            key = line_stripped.split("=", 1)[0]
            if key not in data:
                new_lines.append(original_line)
                continue

            new_value = str(data.get(key, ""))
            updated_keys.add(key)

            if "*" in new_value:
                # 마스킹 값은 사용자 입력이 아닌 조회 결과일 수 있어 기존 값 유지
                new_lines.append(original_line)
                continue

            if not new_value:
                removed.append(key)
                continue

            new_lines.append(f"{key}={new_value}\n")
            applied[key] = new_value

        for key, raw_value in data.items():
            if key in updated_keys:
                continue
            value = str(raw_value)
            if "*" in value or not value:
                continue
            if new_lines and not new_lines[-1].endswith("\n"):
                new_lines[-1] += "\n"
            new_lines.append(f"{key}={value}\n")
            applied[key] = value

        # open(env_path, "w") 를 직접 쓰던 자리다. 그 방식은 여는 시점에만 잘라내므로,
        # 저장 둘이 겹치면 서로 다른 기술자가 각자 offset 0 에서 썼다. 나중에 쓴 쪽이
        # 짧으면 먼저 쓴 쪽의 꼬리가 남아 키 없는 줄이 되고, 위 파서가 = 없는 줄을
        # 그대로 보존하므로 영구히 남았다. 줄 중간에 떨어지면 값 자체가 잘린 채
        # 오염됐다.
        #
        # [INFRA-053] 이 이 자리에 넣었던 os.fchmod 도 여기서 사라진다.
        # atomic_write_text 는 NamedTemporaryFile(0600) 에 쓰고 os.replace 로 옮기므로
        # 모드가 처음부터 좁고, 잘라낸 뒤 실패해 .env 가 빈 채로 남는 창도 없다.
        #
        # os.replace 는 심볼릭 링크를 따라가지 않고 링크 항목 자체를 갈아 끼운다.
        # open(w) 는 따라가서 대상을 잘랐으므로, 부모 디렉터리에 쓸 수 있는 주체가
        # 읽기와 쓰기 사이에 .env 를 다른 파일의 링크로 바꾸면 그 대상이 이 내용으로
        # 덮였다. 그 쓰기 쪽 경로가 닫힌다. 읽기 쪽은 위의 O_NOFOLLOW 가 맡는다.
        # 둘 가운데 하나만으로는 부족하다.
        #
        # 대신 요구하는 권한이 파일에서 디렉터리로 옮겨 간다. open(w) 는 .env 자체의
        # 쓰기 권한을 봤고 os.replace 는 부모 디렉터리의 쓰기 권한을 본다. 그리고 새
        # inode 로 갈아 끼우므로 .env 에 걸린 하드 링크가 끊겨, 그 링크는 교체 전 내용을
        # 계속 들고 있는다. 유출된 키를 이 화면으로 교체해도 그 경로로는 옛 값이 계속
        # 읽힌다는 뜻이다. 이 배포에는 그런 링크가 없고 frontend/.env 는 ../.env 를
        # 가리키는 경로 심볼릭 링크라 무관하다([INFRA-050] 보안 리뷰 L2).
        atomic_write_text(env_path, "".join(new_lines))

        # 잠금 안에서 옮긴다. gunicorn 이 워커마다 스레드를 여덟 두므로 같은 워커의
        # 스레드 둘이 겹칠 수 있고, 이 두 줄이 잠금 밖에 있으면 파일 반영 순서와
        # environ 반영 순서가 뒤집힌다. A 가 잠금을 놓은 뒤 B 가 잡아 쓰고 environ 까지
        # 갱신한 다음에야 A 의 update 가 돌면, 그 워커의 메모리가 파일보다 오래된 값을
        # 들고 재기동 전까지 유지한다([INFRA-050] 보안 리뷰 L3).
        for key in removed:
            environ.pop(key, None)
        environ.update(applied)
