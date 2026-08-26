import { test, expect } from "@playwright/test";
test("入口页可键盘操作且无水平滚动", async ({ page }) => { await page.goto("/enter"); await expect(page.getByRole("heading", { name: "使用驾校邀请码进入" })).toBeVisible(); await page.getByLabel("邀请码").focus(); await expect(page.getByLabel("邀请码")).toBeFocused(); const overflow = await page.evaluate(() => document.documentElement.scrollWidth > document.documentElement.clientWidth); expect(overflow).toBe(false); });

test("邀请进入后完成文字问答并可刷新恢复", async ({ page, context }) => {
  await page.goto("/enter");
  await page.getByRole("button", { name: "进入服务" }).click();
  await expect(page).toHaveURL(/\/ask/);
  expect(await page.evaluate(() => localStorage.getItem("access_token"))).toBeNull();
  const session = (await context.cookies()).find(cookie => cookie.name === "student_session");
  expect(session?.httpOnly).toBe(true);
  await page.getByRole("button", { name: "提交问题" }).click();
  await expect(page.getByText("减速慢行，并让右方道路来车先行。")).toBeVisible();
  await expect(page).toHaveURL(/questionId=/);
  await page.reload();
  await expect(page.getByText("减速慢行，并让右方道路来车先行。")).toBeVisible();
});

test("关键断点和减少动画模式下布局稳定", async ({ page }) => {
  await page.emulateMedia({ reducedMotion: "reduce" });
  for (const viewport of [{ width: 390, height: 844 }, { width: 844, height: 390 }, { width: 768, height: 900 }, { width: 1280, height: 900 }, { width: 1440, height: 900 }]) {
    await page.setViewportSize(viewport); await page.goto("/enter");
    const overflow = await page.evaluate(() => document.documentElement.scrollWidth > document.documentElement.clientWidth);
    expect(overflow, `${viewport.width}x${viewport.height} 不应水平溢出`).toBe(false);
    await expect(page.getByRole("button", { name: "进入服务" })).toBeVisible();
  }
});
