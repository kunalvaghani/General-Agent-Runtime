import type { NextConfig } from "next";
const endpoint = new URL(process.env.GAR_BACKEND_URL || "http://127.0.0.1:8000");
if (!['127.0.0.1','localhost','[::1]'].includes(endpoint.hostname) || endpoint.protocol !== 'http:' || endpoint.username || endpoint.password || endpoint.search || endpoint.hash || endpoint.pathname !== '/') throw new Error("GAR_BACKEND_URL must be a loopback HTTP origin");
const testDist = process.env.GAR_TEST_DIST_DIR;
if (testDist && !/^\.next-test-[a-f0-9]{32}$/.test(testDist)) throw new Error("Invalid test build directory");
const config: NextConfig = { poweredByHeader: false, distDir: testDist || ".next",
  async rewrites() { return [{source:"/api/v1/:path*",destination:`${endpoint.origin}/api/v1/:path*`}]; } };
export default config;
