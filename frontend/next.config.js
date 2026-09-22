/** @type {import('next').NextConfig} */
const path = require('path');

const nextConfig = {
  devIndicators: false,
  // Turbopack/Tailwind file watcher가 상위 디렉토리(홈)의 stale package-lock.json을
  // workspace root로 잘못 추론해 page.tsx 경로 ENOENT가 발생하는 문제를 막는다.
  turbopack: {
    root: path.resolve(__dirname),
  },
  async rewrites() {
    return [
      {
        // system/env 는 같은 이름의 라우트 핸들러가 세션을 확인한 뒤 Flask 로
        // 중계한다. 파일시스템 라우트가 afterFiles rewrite 보다 앞서지만, 의도가
        // 드러나도록 여기서도 뺀다.
        source: '/api/:path((?!auth|system/env).*)',
        destination: (process.env.API_URL || process.env.NEXT_PUBLIC_API_URL)
          ? `${process.env.API_URL || process.env.NEXT_PUBLIC_API_URL}/api/:path*`
          : 'http://127.0.0.1:5501/api/:path*',
      },
    ];
  },
  experimental: {
    // 위 rewrite 로 Flask 에 중계할 때 Next 가 upstream 소켓에 거는 무활동 제한(ms).
    // 기본 30초는 챗봇이 종목·뉴스 문맥을 모으고 Gemini 첫 토큰을 기다리는 침묵보다
    // 짧아서, 스트림이 시작되기 전에 소켓을 끊고 평문 `Internal Server Error` 500 을
    // 보냈다([CHAT-036]). gunicorn 의 `--timeout 120` 과 같은 값이다.
    // ponytail: 침묵이 이 값에 가까워지면 SSE 하트비트(`: ping`)를 더한다
    proxyTimeout: 120_000,
  },
  transpilePackages: ['react-markdown', 'remark-gfm'],
  logging: {
    fetches: {
      fullUrl: false,
    },
  },
};

module.exports = nextConfig;
