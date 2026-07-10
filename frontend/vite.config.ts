import tailwindcss from "@tailwindcss/vite";
import react from "@vitejs/plugin-react";
import { defineConfig } from "vite";

export default defineConfig({
  plugins: [react(), tailwindcss()],
  server: {
    port: 5173,
    proxy: {
      // Forward API and media requests to the FastAPI backend in development.
      "/v1": "http://localhost:8000",
      "/media": "http://localhost:8000",
    },
  },
});
