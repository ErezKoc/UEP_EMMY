import tailwindcss from "@tailwindcss/vite";
import react from "@vitejs/plugin-react";
import { defineConfig } from "vite";
import hostingConfig from "./.openai/hosting.json";

const PLACEHOLDER_DATABASE_ID = "00000000-0000-4000-8000-000000000000";

export default defineConfig(async ({ mode }) => {
  const plugins = [react(), tailwindcss()];

  if (mode === "sites") {
    const { cloudflare } = await import("@cloudflare/vite-plugin");
    plugins.push(
      cloudflare({
        config: {
          // Sites packages the primary Worker from dist/server/index.js.
          name: "server",
          main: "./worker/index.ts",
          compatibility_date: "2026-05-22",
          compatibility_flags: ["nodejs_compat"],
          assets: {
            binding: "ASSETS",
            not_found_handling: "single-page-application",
            run_worker_first: ["/v1/*", "/media/*", "/healthz"],
          },
          d1_databases: hostingConfig.d1
            ? [
                {
                  binding: hostingConfig.d1,
                  database_name: "uep-emmy-demo",
                  database_id: PLACEHOLDER_DATABASE_ID,
                },
              ]
            : [],
          r2_buckets: hostingConfig.r2
            ? [{ binding: hostingConfig.r2, bucket_name: "uep-emmy-media" }]
            : [],
        },
      }),
    );
  }

  return {
    plugins,
    server: {
      port: 5173,
      proxy:
        mode === "sites"
          ? undefined
          : {
              // Keep the existing FastAPI development workflow unchanged.
              "/v1": "http://127.0.0.1:8000",
              "/media": "http://127.0.0.1:8000",
            },
    },
  };
});
