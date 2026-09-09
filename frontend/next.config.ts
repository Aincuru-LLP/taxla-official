import type { NextConfig } from 'next';

// Default to localhost dev backend. Override with BACKEND_URL env var in
// staging/prod (e.g. https://api.taxla.example).
const backendUrl = process.env.BACKEND_URL || 'http://127.0.0.1:8000';

const nextConfig: NextConfig = {
  async rewrites() {
    return [
      {
        source: '/api/:path*',
        destination: `${backendUrl}/api/:path*`,
      },
    ];
  },
};

export default nextConfig;