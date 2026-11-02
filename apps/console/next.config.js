/** @type {import('next').NextConfig} */
const nextConfig = {
  reactStrictMode: true,
  async rewrites() {
    return [
      {
        source: '/api/:path*',
        destination: (process.env.API_BASE_URL || 'http://localhost:8010') + '/v1/:path*',
      },
    ];
  },
};

module.exports = nextConfig;
