import path from "path";
/** @type {import('next').NextConfig} */
const nextConfig = {
  reactStrictMode: true,
  outputFileTracingRoot: path.resolve("."),
  typescript: {
    ignoreBuildErrors: false,
  },
};

export default nextConfig;
