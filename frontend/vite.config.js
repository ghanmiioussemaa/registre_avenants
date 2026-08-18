import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

// En développement, le frontend (port 5173) proxie les appels /api vers l'API
// Flask (port 5050) pour éviter tout souci de CORS et garder des chemins relatifs
// identiques entre dev et prod (où Flask sert directement frontend/dist).
export default defineConfig({
  plugins: [react()],
  server: {
    port: 5173,
    proxy: {
      "/api": {
        target: "http://localhost:5050",
        changeOrigin: true,
      },
    },
  },
});
