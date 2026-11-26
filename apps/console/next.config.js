/** @type {import('next').NextConfig} */
const nextConfig = {
  reactStrictMode: true,
  // Allows an isolated build (e2e) that never overwrites a running dev server's .next output.
  distDir: process.env.NEXT_DIST_DIR || '.next',
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
