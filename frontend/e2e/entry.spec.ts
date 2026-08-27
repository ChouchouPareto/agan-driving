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

test("图片题目可识别、确认并进入可信问答", async ({ page }) => {
  await page.goto("/enter");
  await page.getByRole("button", { name: "进入服务" }).click();
  const png = Buffer.from("iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mNk+A8AAQUBAScY42YAAAAASUVORK5CYII=", "base64");
  await page.locator('input[type="file"]').first().setInputFiles({ name: "question.png", mimeType: "image/png", buffer: png });
  await expect(page.getByText("请确认识别内容")).toBeVisible();
  await page.getByRole("button", { name: "确认并提问" }).click();
  await expect(page).toHaveURL(/questionId=/);
  await page.getByRole("button", { name: "提交问题" }).click();
  await expect(page.getByText("减速慢行，并让右方道路来车先行。")).toBeVisible();
});

test("校长认领回复后由学员确认关闭", async ({ browser }) => {
  const student = await browser.newContext(); const studentPage = await student.newPage();
  await studentPage.goto("/enter"); await studentPage.getByRole("button", { name: "进入服务" }).click();
  await studentPage.getByLabel("输入题目或科目一问题").fill("请告诉我一个没有任何来源的新规定");
  await studentPage.getByRole("button", { name: "提交问题" }).click();
  await expect(studentPage.getByRole("button", { name: "提交给校长" })).toBeVisible();
  await studentPage.getByRole("button", { name: "提交给校长" }).click();
  const detailLink = studentPage.getByRole("link", { name: /查看处理详情/ }); await expect(detailLink).toBeVisible();
  const href = await detailLink.getAttribute("href"); expect(href).toBeTruthy();

  const staff = await browser.newContext(); const staffPage = await staff.newPage();
  await staffPage.goto("/staff/enter"); await staffPage.getByRole("button", { name: "进入校长工作台" }).click();
  await expect(staffPage).toHaveURL(/staff\/tickets$/); await staffPage.getByRole("link", { name: /查看并处理/ }).first().click();
  await staffPage.getByRole("button", { name: "认领并开始处理" }).click();
  await staffPage.getByPlaceholder("给学员明确、可执行的解释…").fill("请以现行题库规则为准，这个说法目前没有可靠依据。");
  await staffPage.getByRole("button", { name: "发送给学员" }).click();
  await expect(staffPage.getByText("已回复，等待学员确认解决。")).toBeVisible();

  await studentPage.goto(href!); await expect(studentPage.getByText("请以现行题库规则为准，这个说法目前没有可靠依据。")).toBeVisible();
  await studentPage.getByRole("button", { name: "校长说好了" }).click();
  await expect(studentPage.getByText("你已确认解决")).toBeVisible();
  await student.close(); await staff.close();
});
