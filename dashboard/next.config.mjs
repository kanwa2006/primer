import path from "path";
import { fileURLToPath } from "url";

const __dirname = path.dirname(fileURLToPath(import.meta.url));

/** @type {import('next').NextConfig} */
const nextConfig = {
  output: "export",
  trailingSlash: true,
  images: {
    unoptimized: true,
  },
  // Silence the workspace-root-inference warning (this project lives inside
  // a Python monorepo with its own package-lock.json at the parent level).
  outputFileTracingRoot: path.join(__dirname),
};

export default nextConfig;
