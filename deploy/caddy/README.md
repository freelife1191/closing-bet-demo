# 운영 Caddy 설정

운영 서버(`close.highvalue.kr`)의 `/etc/caddy/Caddyfile` 가운데 이 프로젝트에 해당하는 부분입니다.
서버 파일에는 이 프로젝트와 무관한 다른 사이트 블록도 있으며, 이 파일은 그중 `(common)` 스니펫과
`:80`, `close.highvalue.kr` 블록의 기준본입니다. `(common)` 은 Caddyfile 전역 스니펫이라 다른 사이트
블록이 `import common` 하고 있으면 여기를 바꿀 때 그 사이트의 압축과 헤더도 함께 바뀝니다. 바꾸기
전에 서버에서 `grep -n "import common" /etc/caddy/Caddyfile` 로 누가 쓰는지 봅니다. `deploy/systemd/` 의 유닛
파일과 같은 이유로 저장소에 둡니다. 서버에만 있던 설정은 코드가 바뀌어도 따라오지 못하고, 그
어긋남은 장애로만 드러납니다. 앞으로는 여기를 고친 뒤 서버에 반영합니다.

내용은 세 부분입니다. `(common)` 스니펫이 압축과 보안 헤더 4종을 정하고, `:80` 블록이 호스트
이름 없는 요청에 Caddy 기본 페이지 대신 404 를 돌려주며, `close.highvalue.kr` 블록이 액세스
로그를 남기고 Next(`localhost:3500`)로 프록시합니다. Flask 는 loopback 에만 있으므로 여기서
직접 노출하지 않습니다. 이 네 가지는 `tests/scripts/test_service_lifecycle.py` 의 계약 테스트가
지킵니다. `reverse_proxy` 가 Next 하나뿐인 것도 그 테스트가 봅니다.

## 적용 절차

검증이 실패하면 덮어쓴 파일이 그대로 남아 다음 재부팅에서 Caddy 가 기동하지 못하므로, 먼저
백업을 떠 둡니다.

서버 파일 전체를 이 파일로 덮어쓰지 않습니다. 다른 사이트 블록이 사라집니다. 이 파일에 해당하는
세 블록만 서버 파일 안에서 같은 내용으로 맞춘 뒤 검증과 reload 를 합니다.

```bash
sudo cp /etc/caddy/Caddyfile /etc/caddy/Caddyfile.bak
sudoedit /etc/caddy/Caddyfile   # (common)·:80·close.highvalue.kr 블록을 이 파일과 같게 맞춥니다
sudo -u caddy caddy validate --config /etc/caddy/Caddyfile
sudo systemctl reload caddy

# 세 블록이 저장소 사본과 같아졌는지 봅니다. 주석·들여쓰기·빈 줄을 뺀 diff 가 비어야 정상입니다.
# 서버에서 세 블록의 순서가 저장소와 다르면 내용이 같아도 순서 차이가 그대로 나옵니다.
strip='s/#.*//; s/^[[:space:]]*//; s/[[:space:]]*$//; /^$/d'
diff <(sudo sed -n '/^(common) {/,/^}/p; /^:80 {/,/^}/p; /^close\.highvalue\.kr {/,/^}/p' /etc/caddy/Caddyfile | sed "$strip") <(sed "$strip" deploy/caddy/Caddyfile)
```

## 검증을 root 로 돌리지 않습니다

`caddy validate` 는 설정을 읽는 데서 그치지 않고 `log` 의 출력 파일을 실제로 엽니다. root 로
돌리면 `/var/log/caddy/close.highvalue.kr.log` 가 `root:root 0600` 으로 먼저 생기고, 그 뒤
`caddy` 사용자로 도는 서비스가 같은 파일을 열지 못해 `systemctl reload caddy` 가 permission
denied 로 실패합니다. 2026-09-22 적용 때 실제로 겪었습니다.

검증은 위 절차처럼 `sudo -u caddy` 로 돌립니다. 이미 root 로 돌렸다면 소유권을 되돌린 뒤
다시 reload 합니다.

```bash
sudo chown caddy:caddy /var/log/caddy/close.highvalue.kr.log
sudo systemctl reload caddy
```

## 적용 후 확인

```bash
# 보안 헤더와 압축이 응답에 실려야 합니다.
curl -s -o /dev/null -D - -H 'Accept-Encoding: gzip' https://close.highvalue.kr/ | grep -Ei 'strict-transport-security|content-encoding'
# 호스트 이름 없이 80 포트로 들어온 요청은 404 여야 합니다. <서버 주소> 는 도메인이 아닌 IP 입니다.
curl -s -o /dev/null -w '%{http_code}\n' http://<서버 주소>/
```
