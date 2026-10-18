import { defineConfig, devices } from "@playwright/test";

const externalUrl = process.env.PLAYWRIGHT_BASE_URL;

export default defineConfig({
  testDir: "./e2e",
  workers: 1,
  use: {
    baseURL: externalUrl ?? "http://127.0.0.1:3100",
    trace: "retain-on-failure",
    channel: "chrome",
  },
  webServer: externalUrl
    ? undefined
    : [
        {
          command: "rm -f ../data/e2e.db && APP_ENV=test APP_SECRET=e2e-only-secret-with-at-least-32-characters LEARNER_INVITATION_CODE=E2E-LEARNER STAFF_INVITATION_CODE=E2E-STAFF DATABASE_URL=sqlite:///../data/e2e.db DASHSCOPE_API_KEY= RAG_ENABLED=false ../backend/.venv/bin/uvicorn app.main:app --app-dir ../backend --host 127.0.0.1 --port 8100",
          url: "http://127.0.0.1:8100/docs",
          reuseExistingServer: false,
          timeout: 30_000,
        },
        {
          command: "BACKEND_API_URL=http://127.0.0.1:8100/api/v1 SESSION_COOKIE_SECURE=false npm run build && mkdir -p .next/standalone/.next && cp -R .next/static .next/standalone/.next/ && cp -R public .next/standalone/ && cd .next/standalone && BACKEND_API_URL=http://127.0.0.1:8100/api/v1 SESSION_COOKIE_SECURE=false HOSTNAME=127.0.0.1 PORT=3100 node server.js",
          url: "http://127.0.0.1:3100/enter",
          reuseExistingServer: false,
          timeout: 30_000,
        },
      ],
  projects: [
    { name: "desktop-chromium", use: { ...devices["Desktop Chrome"] } },
    { name: "mobile-chromium", use: { ...devices["Pixel 5"] } },
  ],
});
