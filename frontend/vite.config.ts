import { defineConfig, loadEnv } from "vite"
import react from "@vitejs/plugin-react"

import { cloudflare } from "@cloudflare/vite-plugin";

export default defineConfig(({ mode }) => {
  const env = loadEnv(mode, process.cwd(), "")
  const apiTarget = env.VITE_API_URL || "https://api.echoforge.biz"

  return {
    plugins: [react(), cloudflare()],
    server: {
      proxy: {
        "/api": {
          target: apiTarget,
          changeOrigin: true,
          rewrite: (path) => path.replace(/^\/api/, "/api"),
        },
      },
    },
  };
})