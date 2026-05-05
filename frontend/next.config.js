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
        source: '/api/:path((?!auth).*)',
        destination: (process.env.API_URL || process.env.NEXT_PUBLIC_API_URL)
          ? `${process.env.API_URL || process.env.NEXT_PUBLIC_API_URL}/api/:path*`
          : 'http://127.0.0.1:5501/api/:path*',
      },
    ];
  },
  transpilePackages: ['react-markdown', 'remark-gfm'],
  logging: {
    fetches: {
      fullUrl: false,
    },
  },
};

module.exports = nextConfig;
