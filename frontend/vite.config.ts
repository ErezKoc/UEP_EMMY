import tailwindcss from "@tailwindcss/vite";
import react from "@vitejs/plugin-react";
import { defineConfig } from "vite";

export default defineConfig({
  plugins: [react(), tailwindcss()],
  server: {
    port: 5173,
    proxy: {
      // Forward API and media requests to the FastAPI backend in development.
      // Use IPv4 explicitly so Windows does not resolve localhost to an IPv6
      // address that Docker Desktop is not ready to accept.
      "/v1": "http://127.0.0.1:8000",
      "/media": "http://127.0.0.1:8000",
    },
  },
});
