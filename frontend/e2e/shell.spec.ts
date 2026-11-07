import { expect, test } from "@playwright/test";

const sizes = [
  { name: "desktop", width: 1366, height: 768 },
  { name: "narrow", width: 1024, height: 700 },
];

for (const size of sizes) {
  test(`${size.name} shell stays usable while the API is offline`, async ({ page }) => {
    await page.setViewportSize(size);
    await page.goto("/");

    await expect(page.getByRole("heading", { name: "把素材，变成下一条好故事。" })).toBeVisible();
    await expect(page.getByRole("button", { name: /新建创作项目/ })).toBeVisible();
    await expect(page.getByText("本地服务暂时离线")).toBeVisible();
    await expect(page.getByTestId("retry")).toBeVisible();

    const overflow = await page.evaluate(() => document.documentElement.scrollWidth > document.documentElement.clientWidth);
    expect(overflow).toBe(false);

    if (size.width < 1120) {
      await expect(page.getByLabel("主导航")).not.toBeInViewport();
      await page.getByRole("button", { name: "打开导航" }).click();
      await expect(page.getByLabel("主导航")).toBeInViewport();
      await expect(page.getByRole("link", { name: /任务/ })).toBeVisible();
    } else {
      await expect(page.getByLabel("主导航")).toBeInViewport();
    }
  });
}
