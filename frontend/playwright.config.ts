import { defineConfig, devices } from "@playwright/test";
const externalUrl = process.env.PLAYWRIGHT_BASE_URL;
export default defineConfig({ testDir: "./e2e", workers: 1, use: { baseURL: externalUrl ?? "http://127.0.0.1:3000", trace: "retain-on-failure", channel: "chrome" }, webServer: externalUrl ? undefined : { command: "npm run dev -- --hostname 127.0.0.1", url: "http://127.0.0.1:3000/enter", reuseExistingServer: !process.env.CI }, projects: [{ name: "desktop-chromium", use: { ...devices["Desktop Chrome"] } }, { name: "mobile-chromium", use: { ...devices["Pixel 5"] } }] });
