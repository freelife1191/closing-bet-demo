#!/bin/bash
# 저장소의 검증된 버전을 적용한다. 임의의 최신 버전으로 올리지는 않는다.
set -euo pipefail

PROJECT_ROOT="$( cd "$( dirname "${BASH_SOURCE[0]}" )/.." && pwd )"
cd "$PROJECT_ROOT"

for required in requirements.txt frontend/package.json frontend/package-lock.json; do
  [ -f "$required" ] || { echo "❌ 필수 파일 없음: $required" >&2; exit 1; }
done
command -v node >/dev/null || { echo "❌ Node.js가 필요합니다." >&2; exit 1; }
command -v npm >/dev/null || { echo "❌ npm이 필요합니다." >&2; exit 1; }

if [ ! -x venv/bin/python ]; then
  echo "📦 Python 가상환경 생성..."
  python3.11 -m venv venv
fi

echo "📦 Python 의존성 확인·적용..."
venv/bin/python -m pip install --quiet --disable-pip-version-check -r requirements.txt
check_output=$(venv/bin/python -m pip check 2>&1) || {
  echo "$check_output" >&2
  exit 1
}
echo "✅ Python 의존성 확인 완료"

cd "$PROJECT_ROOT/frontend"
stamp="node_modules/.project-dependencies.sha256"
fingerprint() {
  node <<'JS'
const fs = require('node:fs');
const crypto = require('node:crypto');
const hash = crypto.createHash('sha256');
for (const file of ['package.json', 'package-lock.json', 'node_modules/.package-lock.json']) {
  hash.update(file + '\0');
  hash.update(fs.existsSync(file) ? fs.readFileSync(file) : 'missing');
}
hash.update(JSON.stringify([process.version, process.platform, process.arch]));
process.stdout.write(hash.digest('hex'));
JS
}

wanted=$(fingerprint)
previous=$(cat "$stamp" 2>/dev/null || true)
reason=""
if [ ! -f node_modules/.bin/next ] || [ ! -f node_modules/.package-lock.json ]; then
  reason="최초 설치 또는 설치 파일 누락"
elif [ -z "$previous" ]; then
  reason="최초 설치 상태 기록"
elif [ "$previous" != "$wanted" ]; then
  reason="패키지 정의·잠금 파일·Node 환경 변경"
elif ! npm ls --all --json >/dev/null 2>&1; then
  reason="설치된 패키지 의존성 검사 실패"
fi

if [ -z "$reason" ]; then
  echo "✅ 프론트엔드 의존성 변경 없음"
else
  echo "📦 프론트엔드: $reason — npm ci 실행..."
  install_log=$(mktemp)
  trap 'rm -f "$install_log"' EXIT
  # 정상 설치의 패키지 목록·funding·반복 경고를 축약한다. 실패 원문은 보존한다.
  if npm ci --no-fund --no-audit >"$install_log" 2>&1; then
    echo "✅ 프론트엔드 패키지 설치 완료"
  else
    cat "$install_log" >&2
    exit 1
  fi
  npm ls --all --json >/dev/null
  fingerprint > "$stamp"
fi

echo "✅ 의존성 준비 완료"
