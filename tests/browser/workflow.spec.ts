import { test, expect } from "@playwright/test";
import { readFileSync } from "node:fs";
import { randomBytes } from "node:crypto";
const credentials = JSON.parse(readFileSync(".local/browser.json", "utf8"));
test("360px administrator workflow, owner auditing, tag rebind, privacy and image fallback", async ({
  page,
  context,
}) => {
  const errors: string[] = [];
  page.on("pageerror", (e) => errors.push(e.message));
  await page.goto("/admin/login");
  await page.getByLabel("账号").fill(credentials.username);
  await page.getByLabel("密码", { exact: true }).fill(credentials.password);
  await page.getByRole("button", { name: "登录", exact: true }).click();
  await expect(page).toHaveURL(/\/admin\/garments$/);
  const suffix = randomBytes(4).toString("hex");
  async function garment(name: string) {
    await page.goto("/admin/garments/new");
    await page.getByLabel("名称（必填）").fill(name);
    await page
      .getByLabel("唯一实例编号")
      .fill("BROWSER-" + suffix + "-" + name);
    await page
      .getByLabel("简介", { exact: true })
      .fill("<img src=x onerror=alert(1)>纯文本");
    await page
      .getByLabel("可信 HTTPS 图片 URL")
      .fill("https://images.invalid/missing.png");
    await page.getByLabel("公开状态").selectOption("PUBLISHED");
    await page.getByRole("button", { name: "保存服装" }).click();
    await expect(page).toHaveURL(/\/admin\/garments\/[0-9a-f-]{36}$/);
    await expect(page.getByRole("status")).toContainText("保存成功");
    return page.url().split("/").pop()!;
  }
  const A = await garment("A"),
    B = await garment("B");
  await page.goto("/admin/garments/" + A);
  await page.getByLabel("新手机号").fill("13800000001");
  await page.getByLabel("变更原因（必填）").fill("浏览器虚拟登记");
  page.once("dialog", (d) => d.accept());
  await page.getByRole("button", { name: "确认修改所有者" }).click();
  await expect(page.getByRole("status")).toContainText("所有者已保存");
  async function tag(garmentName: string) {
    await page.goto("/admin/tags/new");
    await page.getByLabel("UID（必填）").fill(randomBytes(7).toString("hex"));
    await page.getByLabel("备注").fill("模拟测试 UID");
    await page.getByRole("button", { name: "创建标签" }).click();
    await expect(page).toHaveURL(/\/admin\/tags\/[0-9a-f-]{36}$/);
    const id = page.url().split("/").pop()!;
    const entry = await page.locator("#entry").inputValue();
    await page
      .getByLabel("按服装名称")
      .fill("BROWSER-" + suffix + "-" + garmentName);
    await page.getByRole("button", { name: "查找", exact: true }).click();
    await expect(page.getByRole("status")).toContainText("找到");
    await page.locator("#targets").selectOption(garmentName === "A" ? A : B);
    await page.getByLabel("绑定变更原因").fill("绑定模拟标签");
    page.once("dialog", (d) => d.accept());
    await page.getByRole("button", { name: "确认绑定变更" }).click();
    await expect(page.getByRole("status")).toContainText("绑定已保存");
    return { id, entry };
  }
  const TA = await tag("A"),
    TB = await tag("B");
  const publicPage = await context.newPage();
  await publicPage.route("https://images.invalid/**", (r) =>
    r.fulfill({ status: 404, body: "" }),
  );
  await publicPage.goto(TA.entry);
  await expect(publicPage).toHaveURL("/g/" + A);
  await expect(publicPage.getByRole("heading", { level: 1 })).toHaveText("A");
  await expect(publicPage.locator(".placeholder")).toBeVisible();
  await expect(publicPage.locator(".text")).toContainText(
    "<img src=x onerror=alert(1)>",
  );
  expect(await publicPage.locator("body").textContent()).not.toContain(
    "13800000001",
  );
  expect(
    await publicPage.evaluate(
      () => document.documentElement.scrollWidth <= innerWidth,
    ),
  ).toBe(true);
  await page.goto("/admin/tags/" + TB.id);
  await page.locator("#targets").selectOption("");
  await page.getByLabel("绑定变更原因").fill("释放 B");
  page.once("dialog", (d) => d.accept());
  await page.getByRole("button", { name: "确认绑定变更" }).click();
  await expect(page.getByRole("status")).toContainText("绑定已保存");
  await page.goto("/admin/tags/" + TA.id);
  await page.getByLabel("按服装名称").fill("BROWSER-" + suffix + "-B");
  await page.getByRole("button", { name: "查找", exact: true }).click();
  await expect(page.getByRole("status")).toContainText("找到");
  await page.locator("#targets").selectOption(B);
  await page.getByLabel("绑定变更原因").fill("A 改绑 B");
  page.once("dialog", (d) => d.accept());
  await page.getByRole("button", { name: "确认绑定变更" }).click();
  await expect(page.getByRole("status")).toContainText("绑定已保存");
  await publicPage.goto(TA.entry);
  await expect(publicPage.getByRole("heading", { level: 1 })).toHaveText("B");
  await page.locator("select[name=enabled]").selectOption("false");
  await page.getByRole("button", { name: "保存状态与备注" }).click();
  await expect(page.getByRole("status")).toContainText("保存成功");
  const disabled = await publicPage.goto(TA.entry);
  expect(disabled!.status()).toBe(410);
  await expect(publicPage.getByRole("heading")).toContainText("已停用");
  await page.goto("/admin/audit-logs?entityType=garment&entityId=" + A);
  await expect(page.locator("#content")).toContainText("浏览器虚拟登记");
  await expect(page.locator("#content")).toContainText("138****0001");
  expect(await page.locator("#content").textContent()).not.toContain(
    "13800000001",
  );
  expect(
    await page.evaluate(
      () => document.documentElement.scrollWidth <= innerWidth,
    ),
  ).toBe(true);
  await page.screenshot({ path: ".local/admin-mobile.png", fullPage: true });
  await publicPage.screenshot({
    path: ".local/public-mobile.png",
    fullPage: true,
  });
  await page.getByRole("button", { name: "退出", exact: true }).click();
  await expect(page).toHaveURL("/admin/login");
  await page.goto("/admin/tags");
  await expect(page).toHaveURL("/admin/login");
  expect(errors).toEqual([]);
});
test("invalid edit retains entered fields and prevents unsafe image schemes", async ({
  page,
}) => {
  await page.goto("/admin/login");
  await page.getByLabel("账号").fill(credentials.username);
  await page.getByLabel("密码", { exact: true }).fill(credentials.password);
  await page.getByRole("button", { name: "登录", exact: true }).click();
  await expect(page).toHaveURL("/admin/garments");
  await page.goto("/admin/garments/new");
  await page.getByLabel("名称（必填）").fill("保留内容");
  await page
    .getByLabel("唯一实例编号")
    .fill("retain-" + randomBytes(4).toString("hex"));
  await page
    .getByLabel("可信 HTTPS 图片 URL")
    .fill("http://insecure.example/image");
  await page.getByRole("button", { name: "保存服装" }).click();
  await expect(page.getByRole("status")).toContainText("输入不符合要求");
  await expect(page.getByLabel("名称（必填）")).toHaveValue("保留内容");
});
