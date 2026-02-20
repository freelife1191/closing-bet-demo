/** @type {import('next').NextConfig} */
const nextConfig = {
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
  experimental: {
    proxyTimeout: 120000,
  },
  logging: {
    fetches: {
      fullUrl: false,
    },
  },
  devIndicators: false,
};

module.exports = nextConfig;