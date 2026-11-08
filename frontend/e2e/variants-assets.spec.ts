import { expect, test } from "@playwright/test";

test("variant comparison exposes parameters and retries only failures", async ({ page }) => {
  let retried = false;
  await page.route("**/api/v1/**", async (route) => {
    const path = new URL(route.request().url()).pathname;
    if (path.endsWith("/system/status")) return route.fulfill({ json: { status: "ok" } });
    if (path.endsWith("/account/access")) return route.fulfill({ json: { mode: "online" } });
    if (path.endsWith("/jobs")) return route.fulfill({ json: [] });
    if (path === "/api/v1/projects/p") return route.fulfill({ json: { id: "p", name: "主成片变体", project_type: "variants", status: "ready", sources: [{ id: "s", relative_path: "master.mp4", media_info: { duration_ms: 1000 } }] } });
    if (path === "/api/v1/assets") return route.fulfill({ json: [{ id: "a", sha256: "x", asset_type: "image", filename: "品牌角标.png", origin: "品牌自有", license_name: "版权所有者授权", ownership: "linked", available: true, metadata: {} }] });
    if (path.endsWith("/retry")) { retried = true; return route.fulfill({ json: { batch: { id: "b", project_id: "p", source_id: "s", status: "queued", created_at: "2026-01-01", items: [] }, job: { id: "j", job_type: "render_variant_batch", status: "queued", progress: 0 } } }); }
    if (path.endsWith("/variant-batches")) return route.fulfill({ json: [{ id: "b", project_id: "p", source_id: "s", status: "partial", created_at: "2026-01-01", items: [{ id: "i", item_index: 0, status: "failed", recipe: { seed: 9, width: 720, height: 1280, saturation: 1.02, brightness: 0, speed: 1.03, audio_gain_db: -2, video_bitrate: "5M" }, error_summary: "fixture failure" }] }] });
    return route.fulfill({ status: 404, json: {} });
  });
  await page.goto("/#/variants/p");
  await expect(page.getByRole("heading", { name: "主成片变体" })).toBeVisible();
  await expect(page.getByText("720 × 1280")).toBeVisible();
  await expect(page.getByText(/速度 1.03×/)).toBeVisible();
  await page.getByRole("button", { name: "仅重试失败项" }).click();
  expect(retried).toBe(true);
});

test("asset center asks for origin and license provenance", async ({ page }) => {
  await page.route("**/api/v1/**", async (route) => {
    const path = new URL(route.request().url()).pathname;
    if (path.endsWith("/system/status")) return route.fulfill({ json: { status: "ok" } });
    if (path.endsWith("/account/access")) return route.fulfill({ json: { mode: "online" } });
    if (path.endsWith("/jobs")) return route.fulfill({ json: [] });
    if (path === "/api/v1/assets") return route.fulfill({ json: [] });
    return route.fulfill({ status: 404, json: {} });
  });
  await page.goto("/#/assets");
  await expect(page.getByRole("heading", { name: "授权素材中心" })).toBeVisible();
  await expect(page.getByText("素材来源")).toBeVisible();
  await expect(page.getByText("授权或许可证")).toBeVisible();
  await expect(page.getByText(/移动原文件后会明确标记/)).toBeVisible();
});
