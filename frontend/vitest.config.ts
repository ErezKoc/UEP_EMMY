/// <reference types="vitest" />
import react from "@vitejs/plugin-react";
import { defineConfig } from "vitest/config";

/*
 * Kept apart from `vite.config.ts` on purpose.
 *
 * That file loads the Cloudflare plugin and a hosting JSON in "sites" mode and
 * configures a dev proxy to FastAPI, none of which a jsdom test run has any use
 * for - and the Cloudflare plugin in particular is slow to start. Tailwind is
 * left out for the same reason: nothing here asserts on a computed style.
 */
export default defineConfig({
  plugins: [react()],
  test: {
    environment: "jsdom",
    globals: false,
    setupFiles: ["./src/test/setup.ts"],
    include: ["src/**/*.test.{ts,tsx}"],
    css: false,
  },
});
