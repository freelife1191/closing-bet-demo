#!/bin/bash
# Next.js 16 업그레이드 롤백 스크립트
# 사용법: ./scripts/rollback-upgrade.sh

set -e

FRONTEND_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

echo "=========================================="
echo "  Next.js 16 Upgrade Rollback Script"
echo "=========================================="
echo ""

# 백업 파일들이 존재하는지 확인
if [ ! -f "$FRONTEND_DIR/package.json.backup" ]; then
    echo "❌ Error: Backup files not found!"
    echo "   Expected: $FRONTEND_DIR/package.json.backup"
    exit 1
fi

echo "📦 Step 1: Restoring package.json..."
cp "$FRONTEND_DIR/package.json.backup" "$FRONTEND_DIR/package.json"
echo "   ✅ package.json restored"

echo ""
echo "📦 Step 2: Restoring package-lock.json..."
if [ -f "$FRONTEND_DIR/package-lock.json.backup" ]; then
    cp "$FRONTEND_DIR/package-lock.json.backup" "$FRONTEND_DIR/package-lock.json"
    echo "   ✅ package-lock.json restored"
else
    echo "   ⚠️  package-lock.json.backup not found, skipping..."
fi

echo ""
echo "📦 Step 3: Restoring next.config.js..."
if [ -f "$FRONTEND_DIR/next.config.js.backup" ]; then
    cp "$FRONTEND_DIR/next.config.js.backup" "$FRONTEND_DIR/next.config.js"
    echo "   ✅ next.config.js restored"
else
    echo "   ⚠️  next.config.js.backup not found, skipping..."
fi

echo ""
echo "📦 Step 4: Restoring tsconfig.json..."
if [ -f "$FRONTEND_DIR/tsconfig.json.backup" ]; then
    cp "$FRONTEND_DIR/tsconfig.json.backup" "$FRONTEND_DIR/tsconfig.json"
    echo "   ✅ tsconfig.json restored"
else
    echo "   ⚠️  tsconfig.json.backup not found, skipping..."
fi

echo ""
echo "🧹 Step 5: Cleaning node_modules..."
rm -rf "$FRONTEND_DIR/node_modules"
echo "   ✅ node_modules removed"

echo ""
echo "📦 Step 6: Reinstalling dependencies..."
cd "$FRONTEND_DIR"
npm install --silent
echo "   ✅ Dependencies reinstalled"

echo ""
echo "✅ Rollback complete!"
echo ""
echo "🔍 Next steps:"
echo "   1. Run tests: npm run test:baseline"
echo "   2. Check build: npm run build"
echo "   3. Start dev server: npm run dev"
echo ""
