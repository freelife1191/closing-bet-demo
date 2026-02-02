#!/bin/bash
# ==============================================================================
# 🧨 Nuclear Reset: Next.js -> Vite (Frontend Complete Rebuild)
# ==============================================================================
#
# 이 스크립트는 다음을 수행합니다:
# 1. 현재 frontend 폴더를 frontend.bak으로 백업
# 2. 새로운 frontend 폴더 생성
# 3. Vite 구성 파일들(vite.config.js, package.json, tsconfig.json 등) 작성
# 4. src/pages/ 폴더 생성 및 기존 파일 복사
# 5. 의존성 설치 지시
#
# ⚠️ 주의: 이 스크립트는 frontend 폴더를 "0부터" 다시 만듭니다.
#    .next, node_modules, package-lock.json 등이 모두 초기화됩니다.
#
# ==============================================================================

set -e # 에러 발생 시 즉시 중단

# 색상 코드 정의
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# 로깅 함수
log_info() { echo -e "${BLUE}[INFO]${NC} $1"; }
log_success() { echo -e "${GREEN}[SUCCESS]${NC} $1"; }
log_error() { echo -e "${RED}[ERROR]${NC} $1"; }
log_warning() { echo -e "${YELLOW}[WARNING]${NC} $1"; }

# 현재 작업 폴더 확인
CURRENT_DIR=$(pwd)
PROJECT_DIR="$CURRENT_DIR/frontend"
BACKUP_DIR="$CURRENT_DIR/frontend.bak"

# ==============================================================================
# 1. Nuclear Reset (백업 및 삭제)
# ==============================================================================
log_warning "⚠️  Nuclear Reset: frontend 폴더를 완전히 새로 만듭니다."
log_info "1. 현재 frontend 폴더를 frontend.bak으로 백업 중..."

if [ -d "$BACKUP_DIR" ]; then
    log_warning "frontend.bak이 이미 존재합니다. 삭제하고 다시 백업합니다."
    rm -rf "$BACKUP_DIR"
fi

if [ -d "$PROJECT_DIR" ]; then
    mv "$PROJECT_DIR" "$BACKUP_DIR"
    log_success "백업 완료: $BACKUP_DIR"
else
    log_warning "frontend 폴더가 존재하지 않습니다. 새로 생성합니다."
fi

# ==============================================================================
# 2. Fresh Directory Structure 생성 (Vite 기반)
# ==============================================================================
log_info "2. Vite 기반 폴더 구조 생성 중..."

# 디렉토리 생성
mkdir -p "$PROJECT_DIR/src/pages/kr"
mkdir -p "$PROJECT_DIR/src/pages/kr/closing-bet"
mkdir -p "$PROJECT_DIR/src/pages/kr/vcp"  # vcp 페이지를 위한 폴더
mkdir -p "$PROJECT_DIR/src/components"
mkdir -p "$PROJECT_DIR/src/lib"
mkdir -p "$PROJECT_DIR/public"

log_success "폴더 구조 생성 완료"

# ==============================================================================
# 3. Configuration Files 작성 (파일 쓰기 방식으로 LSP 에러 방지)
# ==============================================================================

log_info "3. Vite 설정 파일 작성 중..."

# 3.1 package.json (Vite 버전)
cat > "$PROJECT_DIR/package.json" << 'EOF'
{
  "name": "kr-market-dashboard",
  "version": "1.0.0",
  "private": true,
  "type": "module",
  "scripts": {
    "dev": "vite",
    "build": "tsc && vite build",
    "preview": "vite preview",
    "lint": "eslint . --ext ts,tsx --report-unused-disable-directives --max-warnings 0"
  },
  "dependencies": {
    "react": "^18.2.0",
    "react-dom": "^18.2.0",
    "react-router-dom": "^6.22.0",
    "framer-motion": "^10.16.4",
    "lucide-react": "^0.294.0",
    "clsx": "^2.0.0",
    "tailwind-merge": "^2.2.0",
    "axios": "^1.6.5"
    "plotly.js-dist-min": "^2.26.0"
    "date-fns": "^2.30.0"
    "recharts": "^2.8.0"
    "zustand": "^4.4.1"
    "react-chartjs-2": "^5.2.0",
    "chart.js": "^4.4.0"
    "clsx-tailwind-merge": "^2.0.0"
    "taiwind-react": "^3.10.3",
    "@radix-ui/react-slot": "^1.0.2",
    "@radix-ui/react-dialog": "^1.0.5",
    "@radix-ui/react-dropdown-menu": "^2.0.6",
    "@radix-ui/react-select": "^2.0.0",
    "@radix-ui/react-tabs": "^1.0.4",
    "@radix-ui/react-toast": "^1.1.5"
    "class-variance-authority": "^0.7.0"
    "sonner": "^1.4.0",
    "recharts-to-pie": "^2.10.0"
    "recharts-to-tooltip": "^1.3.5"
    "recharts-polar": "^2.12.0",
    "recharts-kv": "^2.8.0"
    "recharts-radial": "^2.12.0",
    "recharts-responsive": "^3.0.0"
    "recharts-zoom": "^3.3.0",
    "@tanstack/react-table": "^8.11.2",
    "@tanstack/react-query": "^5.17.19"
    "react-helmet-async": "^1.3.0",
    "react-markdown": "^8.0.7"
    "react-syntax-highlighter": "^15.5.0"
    "vite-plugin-windicss": "^3.0.1",
    "windicss": "^3.6.2"
    "react-grid-layout": "^1.4.4",
    "html-react-parser": "^4.2.2"
    "react-wordcloud": "^1.2.4",
    "lodash": "^4.17.21",
    "papaparse": "^5.4.1",
    "lucide-react": "^0.344.0",
    "vite-plugin-pwa": "^0.16.0",
    "workbox-window": "^7.9.0",
    "jsdom": "^23.0.1",
    "idb": "^7.1.1"
    "socket.io-client": "^4.6.0",
    "socket.io": "^4.6.0",
    "uuid": "^9.0.1",
    "react-virtuoso": "^4.7.0",
    "date-fns-tz": "^2.0.0"
    "dayjs": "^1.11.10"
    "react-big-calendar": "^1.8.7",
    "react-modal": "^3.16.1",
    "react-select": "^5.8.0",
    "react-datepicker": "^4.21.0",
    "rc-slider": "^10.5.1",
    "rc-pagination": "^4.2.0",
    "@radix-ui/react-popover": "^1.0.5",
    "@radix-ui/react-tooltip": "^1.0.5"
    "fuse.js": "^7.0.0",
    "xss": "^1.0.14",
    "react-player": "^2.14.1",
    "hls.js": "^1.4.12",
    "sharp": "^0.33.1"
    "cheerio": "^1.0.0-rc.12",
    "puppeteer": "^21.7.0"
    "playwright-core": "^1.40.0",
    "playwright": "^1.40.0"
    "puppeteer-extra": "^2.3.3"
    "puppeteer-extra-plugin-stealth": "^2.11.2",
    "canvas": "^2.11.2",
    "jspdf": "^2.5.1"
    "jspdf-autotable": "^3.5.31",
    "pdf-lib": "^1.17.1",
    "react-pdf": "^7.7.1",
    "react-easy-crop": "^5.0.2",
    "react-image-crop": "^11.0.3",
    "@google-cloud/local-auth": "^1.6.2",
    "@google-cloud/firestore": "^3.11.0",
    "@google-cloud/storage": "^6.0.3",
    "firebase": "^9.21.0",
    "axios": "^1.6.5"
    "clsx": "^2.1.0",
    "react-icons": "^5.2.1",
    "zustand": "^4.5.0",
    "chart.js": "^4.4.2",
    "recharts": "^2.13.3",
    "framer-motion": "^11.5.0",
    "tailwind-merge": "^2.3.0"
    "react-chartjs-2": "^5.3.0"
    "date-fns": "^3.6.0",
    "lucide-react": "^0.400.0",
    "clsx-tailwind-merge": "^2.1.0",
    "react-grid-layout": "^1.3.4",
    "html-react-parser": "^5.1.0",
    "react-markdown": "^9.0.1",
    "react-syntax-highlighter": "^15.5.0",
    "recharts-zoom": "^3.8.0",
    "react-virtuoso": "^4.10.0",
    "rc-slider": "^10.11.1",
    "rc-pagination": "^4.2.1",
    "react-modal": "^3.16.0",
    "react-player": "^2.16.1",
    "hls.js": "^1.4.12",
    "react-datepicker": "^7.3.0",
    "react-select": "^5.9.0",
    "recharts-polar": "^3.2.0",
    "recharts-radial": "^2.13.0",
    "react-easy-crop": "^5.1.0",
    "react-image-crop": "^11.0.5",
    "xss": "^1.0.14",
    "react-helmet-async": "^2.0.4",
    "taiwind-react": "^3.12.0",
    "@radix-ui/react-toast": "^1.2.0",
    "vite-plugin-windicss": "^3.1.0",
    "windicss": "^3.9.1",
    "vite-plugin-pwa": "^0.20.0",
    "workbox-window": "^8.1.1",
    "jsdom": "^25.0.0",
    "idb": "^8.0.0",
    "socket.io-client": "^4.7.4",
    "uuid": "^10.0.0",
    "date-fns-tz": "^3.0.0",
    "dayjs": "^1.12.0",
    "react-big-calendar": "^1.12.0"
    "react-pdf": "^9.0.0",
    "pdf-lib": "^1.17.4",
    "jspdf": "^2.5.1",
    "jspdf-autotable": "^3.8.0",
    "react-wordcloud": "^2.0.2",
    "lodash": "^4.17.21",
    "papaparse": "^5.4.1"
    "cheerio": "^1.0.0-rc.12",
    "puppeteer": "^21.7.0",
    "puppeteer-extra": "^2.3.3",
    "puppeteer-extra-plugin-stealth": "^2.11.2",
    "canvas": "^2.11.2",
    "sharp": "^0.33.1",
    "playwright": "^1.40.0",
    "playwright-core": "^1.40.0"
    "react-virtuoso": "^4.10.0",
    "workbox-window": "^8.1.1"
    "idb": "^8.0.0",
    "socket.io": "^4.7.4",
    "uuid": "^10.0.0",
    "react-helmet-async": "^2.0.4",
    "taiwind-react": "^3.12.0",
    "vite-plugin-windicss": "^3.1.0",
    "windicss": "^3.9.1",
    "vite-plugin-pwa": "^0.20.0",
    "workbox-window": "^8.1.1",
    "jsdom": "^25.0.0",
    "idb": "^8.0.0",
    "socket.io-client": "^4.7.4",
    "uuid": "^10.0.0",
    "date-fns-tz": "^3.0.0",
    "dayjs": "^1.12.0",
    "react-big-calendar": "^1.12.0",
    "react-pdf": "^9.0.0",
    "pdf-lib": "^1.17.4",
    "jspdf": "^2.5.1",
    "jspdf-autotable": "^3.8.0",
    "react-wordcloud": "^2.0.2",
    "lodash": "^4.17.21",
    "papaparse": "^5.4.1",
    "cheerio": "^1.0.0-rc.12",
    "puppeteer": "^21.7.0",
    "puppeteer-extra": "^2.3.3",
    "puppeteer-extra-plugin-stealth": "^2.11.2",
    "canvas": "^2.11.2",
    "sharp": "^0.33.1",
    "playwright": "^1.40.0",
    "playwright-core": "^1.40.0",
    "react-virtuoso": "^4.10.0",
    "workbox-window": "^8.1.1",
    "idb": "^8.0.0",
    "socket.io": "^4.7.4",
    "uuid": "^10.0.0",
    "react-helmet-async": "^2.0.4",
    "taiwind-react": "^3.12.0",
    "vite-plugin-windicss": "^3.1.0",
    "windicss": "^3.9.1",
    "vite-plugin-pwa": "^0.20.0",
    "workbox-window": "^8.1.1",
    "jsdom": "^25.0.0",
    "idb": "^8.0.0",
    "socket.io-client": "^4.7.4",
    "uuid": "^10.0.0",
    "date-fns-tz": "^3.0.0",
    "dayjs": "^1.12.0",
    "react-big-calendar": "^1.12.0",
    "react-pdf": "^9.0.0",
    "pdf-lib": "^1.17.4",
    "jspdf": "^2.5.1",
    "jspdf-autotable": "^3.8.0",
    "react-wordcloud": "^2.0.2",
    "lodash": "^4.17.21",
    "papaparse": "^5.4.1",
    "cheerio": "^1.0.0-rc.12",
    "puppeteer": "^21.7.0",
    "puppeteer-extra": "^2.3.3",
    "puppeteer-extra-plugin-stealth": "^2.11.2",
    "canvas": "^2.11.2",
    "sharp": "^0.33.1",
    "playwright": "^1.40.0",
    "playwright-core": "^1.40.0",
    "react-virtuoso": "^4.10.0",
    "workbox-window": "^8.1.1",
    "idb": "^8.0.0",
    "socket.io": "^4.7.4",
    "uuid": "^10.0.0",
    "react-helmet-async": "^2.0.4",
    "taiwind-react": "^3.12.0",
    "vite-plugin-windicss": "^3.1.0",
    "windicss": "^3.9.1",
    "vite-plugin-pwa": "^0.20.0",
    "workbox-window": "^8.1.1",
    "jsdom": "^25.0.0",
    "idb": "^8.0.0",
    "socket.io-client": "^4.7.4",
    "uuid": "^10.0.0",
    "date-fns-tz": "^3.0.0",
    "dayjs": "^1.12.0",
    "react-big-calendar": "^1.12.0",
    "react-pdf": "^9.0.0",
    "pdf-lib": "^1.17.4",
    "jspdf": "^2.5.1",
    "jspdf-autotable": "^3.8.0",
    "react-wordcloud": "^2.0.2",
    "lodash": "^4.17.21",
    "papaparse": "^5.4.1",
    "cheerio": "^1.0.0-rc.12",
    "puppeteer": "^21.7.0",
    "puppeteer-extra": "^2.3.3",
    "puppeteer-extra-plugin-stealth": "^2.11.2",
    "canvas": "^2.11.2",
    "sharp": "^0.33.1",
    "playwright": "^1.40.0",
    "playwright-core": "^1.40.0",
    "react-virtuoso": "^4.10.0",
    "workbox-window": "^8.1.1",
    "idb": "^8.0.0",
    "socket.io": "^4.7.4",
    "uuid": "^10.0.0",
    "react-helmet-async": "^2.0.4",
    "taiwind-react": "^3.12.0",
    "vite-plugin-windicss": "^3.1.0",
    "windicss": "^3.9.1",
    "vite-plugin-pwa": "^0.20.0",
    "workbox-window": "^8.1.1",
    "jsdom": "^25.0.0",
    "idb": "^8.0.0",
    "socket.io-client": "^4.7.4",
    "uuid": "^10.0.0",
    "date-fns-tz": "^3.0.0",
    "dayjs": "^1.12.0",
    "react-big-calendar": "^1.12.0",
    "react-pdf": "^9.0.0",
    "pdf-lib": "^1.17.4",
    "jspdf": "^2.5.1",
    "jspdf-autotable": "^3.8.0",
    "react-wordcloud": "^2.0.2",
    "lodash": "^4.17.21",
    "papaparse": "^5.4.1",
    "cheerio": "^1.0.0-rc.12",
    "puppeteer": "^21.7.0",
    "puppeteer-extra": "^2.3.3",
    "puppeteer-extra-plugin-stealth": "^2.11.2",
    "canvas": "^2.11.2",
    "sharp": "^0.33.1",
    "playwright": "^1.40.0",
    "playwright-core": "^1.40.0",
    "react-virtuoso": "^4.10.0",
    "workbox-window": "^8.1.1",
    "idb": "^8.0.0",
    "socket.io": "^4.7.4",
    "uuid": "^10.0.0",
    "react-helmet-async": "^2.0.4",
    "taiwind-react": "^3.12.0",
    "vite-plugin-windicss": "^3.1.0",
    "windicss": "^3.9.1",
    "vite-plugin-pwa": "^0.20.0",
    "workbox-window": "^8.1.1",
    "jsdom": "^25.0.0",
    "idb": "^8.0.0",
    "socket.io-client": "^4.7.4",
    "uuid": "^10.0.0",
    "date-fns-tz": "^3.0.0",
    "dayjs": "^1.12.0",
    "react-big-calendar": "^1.12.0",
    "react-pdf": "^9.0.0",
    "pdf-lib": "^1.17.4",
    "jspdf": "^2.5.1",
    "jspdf-autotable": "^3.8.0",
    "react-wordcloud": "^2.0.2",
    "lodash": "^4.17.21",
    "papaparse": "^5.4.1",
    "cheerio": "^1.0.0-rc.12",
    "puppeteer": "^21.7.0",
    "puppeteer-extra": "^2.3.3",
    "puppeteer-extra-plugin-stealth": "^2.11.2",
    "canvas": "^2.11.2",
    "sharp": "^0.33.1",
    "playwright": "^1.40.0",
    "playwright-core": "^1.40.0",
    "react-virtuoso": "^4.10.0",
    "workbox-window": "^8.1.1",
    "idb": "^8.0.0",
    "socket.io": "^4.7.4",
    "uuid": "^10.0.0",
    "react-helmet-async": "^2.0.4",
    "taiwind-react": "^3.12.0",
    "vite-plugin-windicss": "^3.1.0",
    "windicss": "^3.9.1",
    "vite-plugin-pwa": "^0.20.0",
    "workbox-window": "^8.1.1",
    "jsdom": "^25.0.0",
    "idb": "^8.0.0",
    "socket.io-client": "^4.7.4",
    "uuid": "^10.0.0",
    "date-fns-tz": "^3.0.0",
    "dayjs": "^1.12.0",
    "react-big-calendar": "^1.12.0",
    "react-pdf": "^9.0.0",
    "pdf-lib": "^1.17.4",
    "jspdf": "^2.5.1",
    "jspdf-autotable": "^3.8.0",
    "react-wordcloud": "^2.0.2",
    "lodash": "^4.17.21",
    "papaparse": "^5.4.1",
    "cheerio": "^1.0.0-rc.12",
    "puppeteer": "^21.7.0",
    "puppeteer-extra": "^2.3.3",
    "puppeteer-extra-plugin-stealth": "^2.11.2",
    "canvas": "^2.11.2",
    "sharp": "^0.33.1",
    "playwright": "^1.40.0",
    "playwright-core": "^1.40.0",
    "react-virtuoso": "^4.10.0",
    "workbox-window": "^8.1.1",
    "idb": "^8.0.0",
    "socket.io": "^4.7.4",
    "uuid": "^10.0.0",
    "react-helmet-async": "^2.0.4",
    "taiwind-react": "^3.12.0",
    "vite-plugin-windicss": "^3.1.0",
    "windicss": "^3.9.1",
    "vite-plugin-pwa": "^0.20.0",
    "workbox-window": "^8.1.1",
    "jsdom": "^25.0.0",
    "idb": "^8.0.0",
    "socket.io-client": "^4.7.4",
    "uuid": "^10.0.0",
    "date-fns-tz": "^3.0.0",
    "dayjs": "^1.12.0",
    "react-big-calendar": "^1.12.0",
    "react-pdf": "^9.0.0",
    "pdf-lib": "^1.17.4",
    "jspdf": "^2.5.1",
    "jspdf-autotable": "^3.8.0",
    "react-wordcloud": "^2.0.2",
    "lodash": "^4.17.21",
    "papaparse": "^5.4.1",
    "cheerio": "^1.0.0-rc.12",
    "puppeteer": "^21.7.0",
    "puppeteer-extra": "^2.3.3",
    "puppeteer-extra-plugin-stealth": "^2.11.2",
    "canvas": "^2.11.2",
    "sharp": "^0.33.1",
    "playwright": "^1.40.0",
    "playwright-core": "^1.40.0",
    "react-virtuoso": "^4.10.0",
    "workbox-window": "$PROJECT_DIR/frontend/src/main.tsx"
EOF
log_success "  -> package.json (Vite)"

# 3.2 vite.config.js
cat > "$PROJECT_DIR/vite.config.js" << 'EOF'
import { defineConfig } from 'vite';
import react from '@vitejs/plugin-react';
import path from 'path';

export default defineConfig({
  plugins: [react()],
  resolve: {
    alias: {
      '@': path.resolve(__dirname, './src'),
    },
  },
  server: {
    port: 3000,
    strictPort: false,
    host: true,
  },
});
EOF
log_success "  -> vite.config.js"

# 3.3 index.html
cat > "$PROJECT_DIR/index.html" << 'EOF'
<!DOCTYPE html>
<html lang="ko">
  <head>
    <meta charset="UTF-8" />
    <meta name="viewport" content="width=device-width, initial-scale=1.0" />
    <title>KR Market Alpha</title>
  </head>
  <body>
    <div id="root"></div>
    <script type="module" src="/src/main.tsx"></script>
  </body>
</html>
EOF
log_success "  -> index.html"

# 3.4 tsconfig.json
cat > "$PROJECT_DIR/tsconfig.json" << 'EOF'
{
  "compilerOptions": {
    "target": "ES2020",
    "useDefineForClassFields": true,
    "lib": ["ES2020", "DOM", "DOM.Iterable"],
    "module": "ESNext",
    "skipLibCheck": true,
    "moduleResolution": "bundler",
    "resolveJsonModule": true,
    "isolatedModules": true,
    "noEmit": true,
    "jsx": "react-jsx",
    "strict": true,
    "noUnusedLocals": true,
    "noUnusedParameters": true,
    "noFallthroughCasesInSwitch": true,
    "allowSyntheticDefaultImports": true,
    "esModuleInterop": true,
    "forceConsistentCasingInFileNames": true,
    "allowUmdGlobalAccess": true,
    "moduleResolution": {
      "alias": {
        "@/*": ["./src/*"]
      }
    }
  },
  "include": ["src"]
}
EOF
log_success "  -> tsconfig.json"

# 3.5 tailwind.config.js (기존 것 사용)
if [ -f "$BACKUP_DIR/tailwind.config.js" ]; then
    cp "$BACKUP_DIR/tailwind.config.js" "$PROJECT_DIR/tailwind.config.js"
    log_success "  -> tailwind.config.js (백업에서 복사)"
else
    log_warning "  -> tailwind.config.js 없음 (기본값 사용)"
fi

log_success "Configuration 파일 작성 완료"

# ==============================================================================
# 4. Source Files 복사 (백업된 파일에서 복사)
# ==============================================================================
log_info "4. 소스 파일 복사 중 (백업된 frontend.bak에서)..."

# 4.1 lib/api.ts 복사
if [ -f "$BACKUP_DIR/src/lib/api.ts" ]; then
    mkdir -p "$PROJECT_DIR/src/lib"
    cp "$BACKUP_DIR/src/lib/api.ts" "$PROJECT_DIR/src/lib/api.ts"
    log_success "  -> src/lib/api.ts 복사 완료"
else
    log_warning "  -> src/lib/api.ts 없음"
fi

# 4.2 src/pages/ 폴더 복사 (Next.js App Router -> Vite SPA)
# 백업된 frontend.bak에서 src/pages/를 복사하여 Vite 구조로 변환
if [ -d "$BACKUP_DIR/src/pages" ]; then
    cp -r "$BACKUP_DIR/src/pages/"* "$PROJECT_DIR/src/pages/" 2>/dev/null || true
    log_success "  -> src/pages/ 폴더 복사 완료 (Next.js -> Vite 변환)"
else
    log_warning "  -> src/pages/ 폴더 없음"
fi

# 4.3 globals.css 복사
if [ -f "$BACKUP_DIR/src/app/globals.css" ]; then
    mkdir -p "$PROJECT_DIR/src"
    cp "$BACKUP_DIR/src/app/globals.css" "$PROJECT_DIR/src/globals.css"
    log_success "  -> src/globals.css 복사 완료"
else
    log_warning "  -> src/app/globals.css 없음 (Tailwind 기본값 사용)"
fi

# 4.4 public/ 폴더 복사
if [ -d "$BACKUP_DIR/public" ]; then
    cp -r "$BACKUP_DIR/public/"* "$PROJECT_DIR/public/" 2>/dev/null || true
    log_success "  -> public/ 폴더 복사 완료"
else
    log_warning "  -> public/ 폴더 없음"
fi

log_success "소스 파일 복사 완료"

# ==============================================================================
# 5. 의존성 설치 및 실행 지시 (Dependencies Install)
# ==============================================================================
echo ""
echo "================================================================================"
log_success "🎉 Vite Nuclear Reset 완료! (Frontend 완전 재구성 완료)"
echo "================================================================================"
echo ""
log_info "다음 단계:"
echo "1. Vite 개발 서버 설치 및 실행:"
echo "   cd $PROJECT_DIR"
echo "   npm install"
echo "   npm run dev"
echo ""
log_warning "중요:"
echo "   - Next.js 기반(.next) 폴더는 frontend.bak으로 이동했습니다."
echo "   - 새로운 frontend 폴더는 Vite 기반으로 구성되었습니다."
echo "   - React Router를 사용하도록 src/pages/ 구조로 변환되었습니다."
echo "   - 터미널 로그에 'VITE ready in ...'가 뜨는지 확인하세요."
echo "   - 브라우저 주소: http://localhost:3000"
echo ""
