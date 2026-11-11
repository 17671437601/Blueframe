import { HighlightStore } from "../src/stores/highlights";

const batch = {
  id: "b", project_id: "p", analysis_version_id: "a", status: "queued",
  target_count: 2, min_duration_ms: 8000, max_duration_ms: 20000,
  burn_subtitles: true, created_at: "2026-01-01T00:00:00+00:00", clips: [],
};

describe("HighlightStore", () => {
  it("creates a batch, tracks its job and retries failed clips", async () => {
    const api = {
      listHighlightBatches: vi.fn().mockResolvedValue([]),
      listAnalyses: vi.fn().mockResolvedValue([
        { id: "a", version: 2, accepted: true, analysis: { episode_summary: "", characters: [], conflicts: [], explosions: [], edit_candidates: [], media_duration_ms: 0 } },
      ]),
      jobs: vi.fn().mockResolvedValue([]),
      createHighlightBatch: vi.fn().mockResolvedValue({
        batch, job: { id: "j", job_type: "render_highlights", status: "queued", progress: 0 },
      }),
      retryHighlightBatch: vi.fn().mockResolvedValue({
        batch: { ...batch, status: "queued" },
        job: { id: "j2", job_type: "render_highlights", status: "queued", progress: 0 },
      }),
    };
    const store = new HighlightStore(api as never);

    await store.refresh("p");
    expect(store.latestAnalysis?.id).toBe("a");

    await store.create("p", {
      analysis_version_id: "a", target_count: 2, min_duration_ms: 8000,
      max_duration_ms: 20000, burn_subtitles: true, idempotency_key: "x",
    });
    expect(store.batches[0].id).toBe("b");
    expect(store.jobs[0].job_type).toBe("render_highlights");

    await store.retry("p", "b");
    expect(api.retryHighlightBatch).toHaveBeenCalledWith("p", "b", expect.any(String));
    expect(store.batches[0].status).toBe("queued");
  });
});
