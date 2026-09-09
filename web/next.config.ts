import type { NextConfig } from "next";
const endpoint = new URL(process.env.GAR_BACKEND_URL || "http://127.0.0.1:8000");
if (!['127.0.0.1','localhost','[::1]'].includes(endpoint.hostname) || endpoint.protocol !== 'http:' || endpoint.username || endpoint.password || endpoint.search || endpoint.hash || endpoint.pathname !== '/') throw new Error("GAR_BACKEND_URL must be a loopback HTTP origin");
const config: NextConfig = { poweredByHeader: false,
  async rewrites() { return [{source:"/api/v1/:path*",destination:`${endpoint.origin}/api/v1/:path*`}]; } };
export default config;
