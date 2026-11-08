import { VariantStore } from "../src/stores/variants";

describe("VariantStore", () => {
  it("creates and retries a recoverable batch", async () => {
    const api = {
      getProject: vi.fn().mockResolvedValue({ id: "p", name: "V", project_type: "variants", status: "active", sources: [{ id: "s" }] }),
      listVariantBatches: vi.fn().mockResolvedValue([]), listAssets: vi.fn().mockResolvedValue([]), jobs: vi.fn().mockResolvedValue([]),
      createVariantBatch: vi.fn().mockResolvedValue({ batch: { id: "b", status: "queued", items: [] }, job: { id: "j", job_type: "render_variant_batch", status: "queued", progress: 0 } }),
      retryVariantBatch: vi.fn().mockResolvedValue({ batch: { id: "b", status: "queued", items: [] }, job: { id: "j2", job_type: "render_variant_batch", status: "queued", progress: 0 } }),
    };
    const store = new VariantStore(api as never);
    await store.create("p", { source_id: "s", count: 3, seed: 9, width: 720, height: 1280, idempotency_key: "x" });
    await store.retry("p", "b");
    expect(store.batches[0].id).toBe("b");
    expect(api.retryVariantBatch).toHaveBeenCalled();
  });
});
