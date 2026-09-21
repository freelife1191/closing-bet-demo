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
venv/bin/python -m pip install --disable-pip-version-check -r requirements.txt
venv/bin/python -m pip check

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
if [ -f node_modules/.bin/next ] && [ -f node_modules/.package-lock.json ] &&
   [ "$previous" = "$wanted" ] && npm ls --all --json >/dev/null 2>&1; then
  echo "✅ 프론트엔드 의존성 변경 없음"
else
  echo "📦 프론트엔드 의존성 변경 또는 설치 이상 감지: npm ci 실행..."
  npm ci --quiet
  npm ls --all --json >/dev/null
  fingerprint > "$stamp"
fi

echo "✅ 의존성 준비 완료"
