/** @type {import('next').NextConfig} */
const nextConfig = {
  async rewrites() {
    return [
      {
        source: '/api/:path((?!auth).*)',
        destination: (process.env.API_URL || process.env.NEXT_PUBLIC_API_URL)
          ? `${process.env.API_URL || process.env.NEXT_PUBLIC_API_URL}/api/:path*`
          : 'http://127.0.0.1:5001/api/:path*',
      },
    ];
  },
};

module.exports = nextConfig;
