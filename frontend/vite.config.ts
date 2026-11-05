import { defineConfig } from "vite";

// The dev server runs on 5173 and forwards API and WebSocket traffic to FastAPI.
// Add http://localhost:5173 to ALLOWED_ORIGINS when using the dev server.
const backend = "http://127.0.0.1:8000";

export default defineConfig({
  server: {
    port: 5173,
    strictPort: true,
    proxy: {
      "/api": { target: backend },
      "/ws": { target: backend, ws: true },
    },
  },
  build: {
    outDir: "dist",
    emptyOutDir: true,
  },
});
