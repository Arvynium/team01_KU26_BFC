import type { NextConfig } from 'next';

const nextConfig: NextConfig = {
  poweredByHeader: false,
  images: { unoptimized: true },
  async rewrites() {
    const backend = (process.env.BACKEND_URL || 'http://backend:8000').replace(/\/$/, '');
    return [{ source: '/api/:path*', destination: `${backend}/api/:path*` }];
  },
};

export default nextConfig;
