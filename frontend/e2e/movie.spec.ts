import { expect, test } from "@playwright/test";

test("movie workflow imports native media and opens the real workspace", async ({ page }) => {
  await page.addInitScript(() => {
    (window as any).pywebview = { api: {
      get_bootstrap: async () => ({ apiBaseUrl: window.location.origin, sessionToken: "test-token" }),
      select_media_files: async () => ({ rootId: "root-a", files: ["悬疑电影.mp4"] }),
    } };
  });
  await page.route("**/api/v1/**", async (route) => {
    const url = new URL(route.request().url());
    const path = url.pathname;
    if (path.endsWith("/system/status")) return route.fulfill({ json: { status: "ok" } });
    if (path.endsWith("/account/access")) return route.fulfill({ json: { mode: "online" } });
    if (path.endsWith("/jobs")) return route.fulfill({ json: [] });
    if (path === "/api/v1/projects" && route.request().method() === "POST") return route.fulfill({ json: { id: "movie-a", name: "悬疑电影", project_type: "movie", status: "active" } });
    if (path.endsWith("/sources")) return route.fulfill({ json: [{ id: "source-a", relative_path: "悬疑电影.mp4", media_info: { duration_ms: 90000 } }] });
    if (path.endsWith("/transcribe")) return route.fulfill({ json: { id: "job-a", job_type: "transcribe_project", status: "queued", progress: 0 } });
    if (path === "/api/v1/projects/movie-a") return route.fulfill({ json: { id: "movie-a", name: "悬疑电影", project_type: "movie", status: "active", sources: [{ id: "source-a", relative_path: "悬疑电影.mp4", media_info: { duration_ms: 90000 } }] } });
    if (path.endsWith("/commentary") || path.endsWith("/edit-plans")) return route.fulfill({ json: [] });
    return route.fulfill({ status: 404, json: {} });
  });

  await page.goto("/#/movie");
  await expect(page.getByRole("heading", { name: "创建影视解说项目" })).toBeVisible();
  await page.getByTestId("movie-choose-media").click();
  await expect(page.getByText("悬疑电影.mp4")).toBeVisible();
  await page.getByRole("button", { name: "创建并开始识别" }).click();
  await expect(page.getByRole("heading", { name: "悬疑电影" })).toBeVisible();
  await expect(page.getByTestId("generate-commentary")).toBeVisible();
  await expect(page.getByTestId("render-commentary")).toBeVisible();
});
