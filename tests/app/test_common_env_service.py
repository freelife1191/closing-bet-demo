#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Common Env Service 단위 테스트
"""

import stat
import threading
import time
from pathlib import Path

import pytest

from services import common_env_service
from services.common_env_service import (
    _env_file_lock,
    read_masked_env_vars,
    update_env_file,
)


def test_read_masked_env_vars_masks_sensitive_and_skips_empty(tmp_path: Path):
    env_path = tmp_path / ".env"
    env_path.write_text(
        "\n".join(
            [
                # 24자를 넘는 값은 앞뒤 네 자를 남긴다
                "OPENAI_API_KEY=abcd1234567890123456789wxyz",
                # 24자 이하는 전부 가린다. 16자 앱 비밀번호가 절반을 흘리던 자리다
                "SMTP_PASSWORD=abcdefghijklmnop",
                "SMTP_PORT=587",
                "SMTP_USER=",
                "# comment",
            ]
        )
        + "\n",
        encoding="utf-8",
    )

    result = read_masked_env_vars(str(env_path))
    assert result["SMTP_PORT"] == "587"
    assert result["OPENAI_API_KEY"].startswith("abcd")
    assert result["OPENAI_API_KEY"].endswith("wxyz")
    assert result["SMTP_PASSWORD"] == "*" * 16
    assert "SMTP_USER" not in result


def test_update_env_file_preserves_masked_input_and_deletes_empty(tmp_path: Path):
    env_path = tmp_path / ".env"
    env_path.write_text(
        "OPENAI_API_KEY=secret-value\nSMTP_HOST=old\nSMTP_USER=1\n",
        encoding="utf-8",
    )

    environ: dict[str, str] = {}
    update_env_file(
        str(env_path),
        {
            "OPENAI_API_KEY": "****",  # 마스킹 값은 변경 금지
            "SMTP_HOST": "new",
            "SMTP_USER": "",
            "TELEGRAM_CHAT_ID": "ok",
        },
        environ,
    )

    content = env_path.read_text(encoding="utf-8")
    assert "OPENAI_API_KEY=secret-value" in content
    assert "SMTP_HOST=new" in content
    assert "SMTP_USER=" not in content
    assert "TELEGRAM_CHAT_ID=ok" in content
    assert environ["SMTP_HOST"] == "new"
    assert environ["TELEGRAM_CHAT_ID"] == "ok"


def test_read_masked_env_vars_omits_authorization_keys(tmp_path: Path):
    """[INFRA-044] 인가 판정 근거는 관리자 화면 응답에도 실리지 않는다."""
    env_path = tmp_path / ".env"
    env_path.write_text(
        "ADMIN_EMAILS=owner@example.com\nADMIN_API_TOKEN=token-value\nSMTP_PORT=587\n",
        encoding="utf-8",
    )

    result = read_masked_env_vars(str(env_path))
    assert "ADMIN_EMAILS" not in result
    assert "ADMIN_API_TOKEN" not in result
    # 전부 거르는 코드도 위 두 줄을 통과하므로 허용 키가 실리는 것을 함께 잰다.
    assert result["SMTP_PORT"] == "587"


def test_update_env_file_rejects_authorization_keys(tmp_path: Path):
    """[INFRA-044] 설정 화면으로 인가 판정 근거를 덮어쓸 수 없다.

    `is_admin_email` 은 매 요청 `os.environ` 을 다시 읽는다. 이 필터가 뚫리면 요청을
    처리한 워커의 명단만 바뀌어, 같은 관리자의 같은 요청이 어느 워커에 닿느냐에 따라
    통과와 거부로 갈린다.
    """
    env_path = tmp_path / ".env"
    env_path.write_text(
        "ADMIN_EMAILS=owner@example.com\nSMTP_HOST=old\n", encoding="utf-8"
    )

    environ: dict[str, str] = {}
    update_env_file(
        str(env_path),
        {
            "ADMIN_EMAILS": "attacker@example.com",
            "ADMIN_API_TOKEN": "forged",
            "SMTP_HOST": "new",
        },
        environ,
    )

    content = env_path.read_text(encoding="utf-8")
    assert "ADMIN_EMAILS=owner@example.com" in content
    assert "ADMIN_API_TOKEN" not in content
    assert "ADMIN_EMAILS" not in environ
    assert "ADMIN_API_TOKEN" not in environ
    assert "SMTP_HOST=new" in content
    assert environ["SMTP_HOST"] == "new"


def test_update_env_file_rejects_newline_in_value(tmp_path: Path):
    """[INFRA-044] 허용 키의 값에 개행을 넣어 목록 밖의 줄을 쓸 수 없다.

    키만 검사하면 값 하나가 두 줄이 되어 필터를 그대로 지나간다. `.env` 는
    restart_all.sh 와 stop_all.sh 가 source 하므로 주입한 줄은 다음 기동에서 셸
    명령으로도 실행된다.
    """
    env_path = tmp_path / ".env"
    env_path.write_text("SMTP_HOST=old\n", encoding="utf-8")

    environ: dict[str, str] = {}
    update_env_file(
        str(env_path),
        {
            # 기존 줄을 갱신하는 경로
            "SMTP_HOST": "smtp.example.com\nADMIN_EMAILS=attacker@example.com",
            # 새 키를 덧붙이는 경로
            "EMAIL_RECIPIENTS": "a@b.c\rADMIN_API_TOKEN=forged",
            "SMTP_PORT": "587",
        },
        environ,
    )

    content = env_path.read_text(encoding="utf-8")
    assert "ADMIN_EMAILS" not in content
    assert "ADMIN_API_TOKEN" not in content
    assert "SMTP_HOST=old" in content
    assert "EMAIL_RECIPIENTS" not in content
    assert "SMTP_HOST" not in environ
    # 개행이 없는 값은 그대로 반영되어야 한다.
    assert "SMTP_PORT=587" in content
    assert environ["SMTP_PORT"] == "587"


def test_update_env_file_rejects_interpolation_in_value(tmp_path: Path):
    """[INFRA-044] 값에 다른 키를 참조해 가려 둔 비밀을 끌어다 쓸 수 없다.

    python-dotenv 와 @next/env 가 `${VAR}` 와 맨 `$VAR` 를 보간하므로, 이것이 통과하면
    서버가 발송 대상 주소에 자기 토큰을 실어 보낸다. 읽는 쪽에서는 막을 수 없다.
    @next/env 에는 보간을 끄는 인자가 없다.
    """
    env_path = tmp_path / ".env"
    env_path.write_text("SMTP_HOST=old\n", encoding="utf-8")

    environ: dict[str, str] = {}
    update_env_file(
        str(env_path),
        {
            "DISCORD_WEBHOOK_URL": "https://x.test/${ADMIN_API_TOKEN}",
            "SMTP_PASSWORD": "$INTERNAL_IDENTITY_SECRET",
            "SMTP_USER": "u@x.test$(id)",
            # `$` 로 끝나거나 기호가 이어지는 값은 보간되지 않으므로 통과해야 한다.
            "TELEGRAM_BOT_TOKEN": "pass!word$",
            "TELEGRAM_CHAT_ID": "has$!bang",
            "SMTP_HOST": "new",
        },
        environ,
    )

    content = env_path.read_text(encoding="utf-8")
    assert "ADMIN_API_TOKEN" not in content
    assert "INTERNAL_IDENTITY_SECRET" not in content
    assert "$(id)" not in content
    assert "SMTP_PASSWORD" not in content
    assert "SMTP_USER" not in content
    # 전부 거부하는 코드도 위 다섯 줄을 통과하므로 정상 값 셋을 함께 잰다.
    assert "SMTP_HOST=new" in content
    assert "TELEGRAM_BOT_TOKEN=pass!word$" in content
    assert "TELEGRAM_CHAT_ID=has$!bang" in content


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
    # 모드만 보면 쓰기가 실패해도 통과한다. 값이 실제로 바뀌었는지 함께 본다.
    assert env_path.read_text(encoding="utf-8") == "OPENAI_API_KEY=new-value\n"


def test_update_env_file_does_not_create_file_when_nothing_to_write(tmp_path: Path):
    """버려진 입력만 왔을 때 빈 .env 를 만들어 두지 않는다.

    ADMIN_API_TOKEN 은 EDITABLE_ENV_KEYS 밖이라 필터에서 전부 떨어지고 두 번째 이른 반환에
    걸린다. 두 이른 반환 가운데 하나라도 사라지면 open(w) 가 존재하지 않던 파일을 빈 채로
    만들고, 아래 단언이 그때 실패한다. FileNotFoundError 는 나지 않는다. open(w) 가
    fchmod 보다 먼저 파일을 만들기 때문이다.
    """
    env_path = tmp_path / ".env"

    update_env_file(str(env_path), {"ADMIN_API_TOKEN": "blocked"}, {})

    assert not env_path.exists()


def test_update_env_file_keeps_environ_and_file_intact_when_write_fails(
    tmp_path: Path, monkeypatch
):
    """저장이 실패하면 그 워커의 메모리도 디스크도 바뀌지 않는다.

    종전에는 environ 을 루프 안에서 먼저 고쳤으므로, 저장이 실패해도 그 워커만 새 값을
    들고 있었다. is_admin_email 은 매 요청 os.environ 을 다시 읽으므로, 같은 요청이
    어느 워커에 닿느냐에 따라 다르게 동작했다([INFRA-050]).

    파일 쪽 단언은 원자적 교체가 실제로 걸렸는지를 함께 잰다. open(w) 로 되돌리면 이미
    잘린 빈 파일이 남아 이 줄이 실패한다.
    """
    env_path = tmp_path / ".env"
    env_path.write_text("SMTP_HOST=old\n", encoding="utf-8")

    def failing_write(file_path, content, **kwargs):
        raise OSError("no space left on device")

    monkeypatch.setattr(common_env_service, "atomic_write_text", failing_write)

    environ = {"SMTP_HOST": "old"}
    with pytest.raises(OSError):
        update_env_file(str(env_path), {"SMTP_HOST": "new"}, environ)

    assert environ == {"SMTP_HOST": "old"}
    assert env_path.read_text(encoding="utf-8") == "SMTP_HOST=old\n"


def test_read_masked_env_vars_refuses_to_read_through_a_symlink(tmp_path: Path):
    """조회도 링크를 따라가지 않는다.

    저장만 O_NOFOLLOW 로 고치면 관리자가 화면에서 보는 파일과 저장이 닿는 파일이 갈린다.
    .env 가 링크인 상태에서 화면을 열면 대상의 값이 뜨는데, PLAIN_ENV_KEYS 인
    SMTP_HOST·SMTP_PORT·AI_PROVIDER 는 마스킹 없이 그대로 나간다. 그 상태에서 저장을
    누르면 ELOOP 로 500 이 나므로 두 경로의 판정이 어긋난다([INFRA-050] 적대적 리뷰).
    """
    victim = tmp_path / "victim.txt"
    victim.write_text("SMTP_HOST=leaked.example.com\n", encoding="utf-8")
    env_path = tmp_path / ".env"
    env_path.symlink_to(victim)

    with pytest.raises(OSError):
        read_masked_env_vars(str(env_path))


def test_update_env_file_refuses_to_read_through_a_symlink(tmp_path: Path):
    """`.env` 가 다른 파일의 링크면 아무것도 하지 않고 실패한다.

    종전 open(r) 은 링크를 따라가 대상의 내용을 읽었고, 줄 루프가 data 에 없는 키를
    무조건 보존하므로 그 내용이 그대로 새 .env 로 옮겨 붙었다. 실측하면 대상에 둔
    ADMIN_API_TOKEN 과 ADMIN_EMAILS 가 그대로 .env 에 나타났다. EDITABLE_ENV_KEYS
    필터가 막으려던 바로 그 키들이 파일 경로로 주입된 것이다([INFRA-050] 적대적 리뷰 H2).

    os.replace 로 쓰기 쪽만 닫았을 때 이 검사가 통과해 버렸다. 그때는 대상 파일이 안
    바뀐 것만 쟀기 때문이다. 그래서 지금은 세 가지를 함께 본다. 예외가 나는가, 대상이
    보존되는가, 그리고 .env 가 여전히 링크인가. 마지막 것이 「아무것도 하지 않았다」를
    잰다.

    운영 배포의 루트 .env 는 일반 파일이라 이 경로를 밟지 않는다. restart_all.sh 가
    만드는 링크는 frontend/.env → ../.env 로 가리키는 쪽이다.
    """
    victim = tmp_path / "victim.txt"
    victim.write_text(
        "ADMIN_API_TOKEN=attacker-chosen\nADMIN_EMAILS=attacker@evil.test\n",
        encoding="utf-8",
    )
    env_path = tmp_path / ".env"
    env_path.symlink_to(victim)

    with pytest.raises(OSError):
        update_env_file(str(env_path), {"SMTP_HOST": "new"}, {})

    assert victim.read_text(encoding="utf-8") == (
        "ADMIN_API_TOKEN=attacker-chosen\nADMIN_EMAILS=attacker@evil.test\n"
    )
    # 링크가 그대로 남아야 한다. 일반 파일로 굳었다면 대상 내용이 옮겨 붙은 것이다.
    assert env_path.is_symlink()


def test_concurrent_env_saves_keep_both_updates_and_leave_no_debris(
    tmp_path: Path, monkeypatch
):
    """저장 요청 둘이 겹쳐도 두 갱신이 모두 남고 쓰레기 줄이 생기지 않는다.

    화면이 이 경합을 유발하는 자리를 둘 갖고 있다. SettingsModal.tsx:167 의 「저장」
    버튼은 envVars 전체를 보내고, :279 의 알림 테스트는 발송 직전에 알림 키만 따로
    보낸다. gunicorn 이 --workers 2 --threads 8 로 뜨므로 둘은 동시에 처리된다.

    잠금이 닫는 갱신 소실과 원자적 교체가 닫는 꼬리 잔존을 함께 잰다. 각각을 아래
    단언 옆에 적었다([INFRA-050]).

    지연을 읽기와 쓰기 사이에 넣어 경합 창을 강제로 넓힌다. 잠금이 없으면 나중에 뜬
    쪽이 앞선 쪽의 지연 중에 옛 내용을 읽어 소실이 확정된다.

    두 번째 스레드를 띄우는 시점을 Event 로 잡는다. 고정된 sleep 으로 어림하면 부하가
    심한 기계에서 그 시간 안에 첫 읽기가 끝나지 않아 두 저장이 겹치지 않고, 잠금을
    걷어낸 상태에서도 검사가 통과한다. 남는 가정은 「두 번째가 첫 쪽의 0.3 초 지연 안에
    읽기에 닿는다」 하나인데, 잠금이 있는 코드에서 두 스레드가 동시에 읽는 상태를 만들
    방법은 없으므로(그것이 잠금의 목적이다) 이 가정은 없앨 수 없다. 실효의 증거는 아래
    돌연변이다. 잠금을 무동작으로 바꾸면 이 검사가 값 단언에서 실패한다.

    아래 꼬리 단언의 실효 범위를 밝혀 둔다. 이 검사는 원자적 교체를 되돌리는 돌연변이도
    실패시키지만, 꼬리를 재서가 아니라 위 wait 가 시간 초과로 걸려서다. 지연이
    atomic_write_text 에 걸려 있으므로 그 호출을 없애면 write_started 가 설정되지 않는다.
    즉 그때 실패하는 것은 「꼬리가 남았다」가 아니라 「검사의 전제가 무너졌다」이며, 꼬리
    단언 자체는 최종 상태의 불변식으로만 남는다. 원자적 교체 회귀를 그 내용으로 잡는
    것은 narrows_file_mode(모드)와 keeps_environ_and_file_intact(예외 전파),
    refuses_to_read_through_a_symlink(링크) 셋이다. 돌연변이 셋으로 확인했다.
    """
    env_path = tmp_path / ".env"
    env_path.write_text(
        "SMTP_HOST=old\nDISCORD_WEBHOOK_URL=old-hook\n",
        encoding="utf-8",
    )

    real_write = common_env_service.atomic_write_text
    write_started = threading.Event()

    # ponytail: 0.3 초 안에 두 번째 스레드가 읽기를 마쳐야 회귀를 잡는다. 통과 상태에서는
    # 잠금이 바로 그 순서를 막으므로 두 스레드가 동시에 읽었음을 확인할 방법이 없고,
    # 결정론적 판정은 이 구조로 나오지 않는다. 실효의 증거는 돌연변이다.
    def slow_write(file_path, content, **kwargs):
        write_started.set()
        time.sleep(0.3)
        real_write(file_path, content, **kwargs)

    monkeypatch.setattr(common_env_service, "atomic_write_text", slow_write)

    errors: list[Exception] = []

    def save(payload: dict[str, str]):
        try:
            update_env_file(str(env_path), payload, {})
        except Exception as error:  # noqa: BLE001 - 스레드 밖으로 옮겨 보고한다
            errors.append(error)

    # 길이를 일부러 다르게 준다. 두 쓰기의 길이가 같으면 꼬리가 남지 않아 위험 하나가
    # 검사에서 빠진다.
    save_button = threading.Thread(
        target=save, args=({"SMTP_HOST": "smtp.a-very-long-host.example.com"},)
    )
    test_button = threading.Thread(target=save, args=({"DISCORD_WEBHOOK_URL": "h"},))
    save_button.start()
    # 먼저 뜬 쪽이 읽기를 마치고 쓰기 단계에 **실제로 들어갔음**을 확인한 뒤 두 번째를
    # 띄운다. 고정된 sleep 으로 어림하면 부하가 심한 기계에서 그 시간 안에 읽기가 끝나지
    # 않아 두 저장이 겹치지 않고, 잠금을 걷어낸 상태에서도 검사가 통과한다.
    assert write_started.wait(timeout=10), "첫 저장이 쓰기 단계에 도달하지 못했다"
    test_button.start()
    save_button.join()
    test_button.join()

    assert not errors
    content = env_path.read_text(encoding="utf-8")
    # 잠금이 없으면 이 둘 가운데 하나가 실패한다. 나중에 시작한 쪽이 옛 내용을 읽어
    # 덮기 때문이다.
    assert "SMTP_HOST=smtp.a-very-long-host.example.com" in content
    assert "DISCORD_WEBHOOK_URL=h" in content
    # 꼬리 잔존을 잰다. open(w) 는 여는 시점에만 잘라내므로 두 기술자가 각자 offset 0
    # 에서 쓰면 짧은 쪽 뒤에 긴 쪽의 꼬리가 키 없는 줄로 남고, 이 파일의 파서가 = 없는
    # 줄을 보존해 영구히 남는다.
    for line in content.splitlines():
        assert "=" in line, f"키 없는 줄이 남았다: {line!r}"


def test_env_file_lock_creates_narrow_lock_file(tmp_path: Path):
    """잠금 파일이 0600 으로 만들어지고, 나간 뒤에도 남아 재사용된다.

    이 보장은 **최초 생성에만** 걸린다. os.open 의 모드 인자는 파일이 이미 있으면
    무시되므로, 누가 미리 넓은 모드로 만들어 두면 그 모드가 그대로 남는다. 그 상태를
    강제로 좁히지 않는 이유는 구현 주석에 적었다([INFRA-050] 보안 리뷰 L1). 그러니 이
    검사는 「항상 0600 이다」가 아니라 「이 코드가 새로 만들 때는 0600 이다」를 잰다.
    """
    env_path = tmp_path / ".env"
    lock_path = tmp_path / ".env.lock"

    with _env_file_lock(str(env_path)):
        assert lock_path.exists()
        assert stat.S_IMODE(lock_path.stat().st_mode) == 0o600

    # 나간 뒤에도 파일은 남는다. 지우면 다음 진입이 새 inode 를 만들어 그 사이 잠금이
    # 배타되지 않는 창이 생긴다.
    assert lock_path.exists()


def test_perplexity_key_is_no_longer_editable(tmp_path: Path):
    # [VCP-046] 운영 .env 에 값이 남아 있어도 화면으로 읽거나 쓰지 않는다
    env_path = tmp_path / ".env"
    env_path.write_text("PERPLEXITY_API_KEY=pplx-secret-value-0000000000\n", encoding="utf-8")

    assert "PERPLEXITY_API_KEY" not in read_masked_env_vars(str(env_path))
    result = update_env_file(str(env_path), {"PERPLEXITY_API_KEY": "x"}, {})
    assert result["rejected"] == {"PERPLEXITY_API_KEY": "unsupported_key"}
    assert "pplx-secret-value" in env_path.read_text(encoding="utf-8")
