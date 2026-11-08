import { expect, test } from "@playwright/test";

test("live workspace shows recording, reconnect and processed clips on narrow layout", async ({ page }) => {
  await page.setViewportSize({ width: 1024, height: 700 });
  await page.route("**/api/v1/**", async (route) => {
    const path = new URL(route.request().url()).pathname;
    if (path.endsWith("/system/status")) return route.fulfill({ json: { status: "ok" } });
    if (path.endsWith("/account/access")) return route.fulfill({ json: { mode: "online" } });
    if (path.endsWith("/jobs")) return route.fulfill({ json: [{ id: "j", job_type: "process_live_segment", status: "running", progress: 55, payload: { project_id: "p" } }] });
    if (path === "/api/v1/projects/p") return route.fulfill({ json: { id: "p", name: "授权直播", project_type: "live", status: "processing" } });
    if (path.endsWith("/recordings")) return route.fulfill({ json: [{ id: "s", project_id: "p", platform: "douyin", display_name: "测试主播", intent_active: true, status: "recording", reconnect_count: 1, segments: [{ id: "g", sequence: 0, status: "processed", filename: "segment-000000.mkv", duration_ms: 60000, size_bytes: 10485760 }] }] });
    if (path.endsWith("/reconnect")) return route.fulfill({ json: { id: "s", project_id: "p", platform: "douyin", display_name: "测试主播", intent_active: true, status: "reconnecting", reconnect_count: 2, segments: [] } });
    return route.fulfill({ status: 404, json: {} });
  });
  await page.goto("/#/live/p");
  await expect(page.getByRole("heading", { name: "授权直播", exact: true })).toBeVisible();
  await expect(page.getByText("测试主播")).toBeVisible();
  await expect(page.getByText("segment-000000.mkv")).toBeVisible();
  await expect(page.getByRole("button", { name: "手动重连" })).toBeVisible();
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= document.documentElement.clientWidth)).toBe(true);
});
