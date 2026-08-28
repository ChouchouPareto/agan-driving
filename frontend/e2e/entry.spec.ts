import { expect, test } from "@playwright/test";

async function enterAsStudent(page: import("@playwright/test").Page) {
  await page.goto("/enter");
  await page.getByRole("button", { name: "进入服务" }).click();
  await expect(page).toHaveURL(/\/ask/);
}

async function ask(page: import("@playwright/test").Page, message: string) {
  await page.getByLabel("给超级驾陪发消息").fill(message);
  await page.getByRole("button", { name: "发送消息" }).click();
}

test("入口页可键盘操作且无水平滚动", async ({ page }) => {
  await page.goto("/enter");
  await expect(page.getByRole("heading", { name: "使用驾校邀请码进入" })).toBeVisible();
  await page.getByLabel("邀请码").focus();
  await expect(page.getByLabel("邀请码")).toBeFocused();
  expect(await page.evaluate(() => document.documentElement.scrollWidth > document.documentElement.clientWidth)).toBe(false);
});

test("邀请进入后完成文字问答并可刷新恢复", async ({ page, context }) => {
  await enterAsStudent(page);
  expect(await page.evaluate(() => localStorage.getItem("access_token"))).toBeNull();
  const session = (await context.cookies()).find((cookie) => cookie.name === "student_session");
  expect(session?.httpOnly).toBe(true);
  await ask(page, "驾驶机动车通过没有交通信号灯控制的交叉路口应该怎样行驶？");
  await expect(page.getByRole("article")).toBeVisible({ timeout: 10_000 });
  await expect(page).toHaveURL(/conversationId=/);
  await page.reload();
  await expect(page.getByRole("article")).toBeVisible();
});

test("关键断点和减少动画模式下布局稳定", async ({ page }) => {
  await page.emulateMedia({ reducedMotion: "reduce" });
  for (const viewport of [{ width: 390, height: 844 }, { width: 844, height: 390 }, { width: 768, height: 900 }, { width: 1280, height: 900 }, { width: 1440, height: 900 }]) {
    await page.setViewportSize(viewport);
    await page.goto("/enter");
    expect(await page.evaluate(() => document.documentElement.scrollWidth > document.documentElement.clientWidth), `${viewport.width}x${viewport.height} 不应水平溢出`).toBe(false);
    await expect(page.getByRole("button", { name: "进入服务" })).toBeVisible();
  }
});

test("图片题目可识别、确认并进入可信问答", async ({ page }) => {
  await enterAsStudent(page);
  const png = Buffer.from("iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mNk+A8AAQUBAScY42YAAAAASUVORK5CYII=", "base64");
  await page.locator('input[type="file"]').first().setInputFiles({ name: "question.png", mimeType: "image/png", buffer: png });
  await expect(page.getByText("请确认识别内容")).toBeVisible();
  await page.getByRole("button", { name: "确认并提问" }).click();
  await expect(page).toHaveURL(/conversationId=/);
  await expect(page.getByRole("article")).toBeVisible({ timeout: 10_000 });
});

test("校长认领回复后由学员确认关闭", async ({ browser }) => {
  const student = await browser.newContext();
  const studentPage = await student.newPage();
  await enterAsStudent(studentPage);
  await ask(studentPage, "驾驶机动车遇到宇宙飞船时应该让谁先行？");
  await expect(studentPage.getByRole("button", { name: "答案有问题" })).toBeVisible();
  await studentPage.getByRole("button", { name: "答案有问题" }).click();
  const detailLink = studentPage.getByRole("link", { name: /查看处理详情/ });
  await expect(detailLink).toBeVisible();
  const href = await detailLink.getAttribute("href");
  expect(href).toBeTruthy();

  const staff = await browser.newContext();
  const staffPage = await staff.newPage();
  await staffPage.goto("/staff/enter");
  await staffPage.getByRole("button", { name: "进入校长工作台" }).click();
  await expect(staffPage).toHaveURL(/staff\/tickets$/);
  await staffPage.getByRole("link", { name: /查看并处理/ }).first().click();
  await staffPage.getByRole("button", { name: "认领并开始处理" }).click();
  await staffPage.getByPlaceholder("给学员明确、可执行的解释…").fill("请以现行题库规则为准，这个说法目前没有可靠依据。");
  await staffPage.getByRole("button", { name: "发送给学员" }).click();
  await expect(staffPage.getByText("已回复，等待学员确认解决。")).toBeVisible();

  await studentPage.goto(href!);
  await expect(studentPage.getByText("请以现行题库规则为准，这个说法目前没有可靠依据。")).toBeVisible();
  await studentPage.getByRole("button", { name: "确认已解决" }).click();
  await expect(studentPage.getByText("你已确认解决")).toBeVisible();
  await student.close();
  await staff.close();
});
