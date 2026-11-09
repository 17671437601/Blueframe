import { DiagnosticsStore } from "../src/stores/diagnostics";

describe("DiagnosticsStore", () => {
  it("loads privacy summary and exports a support bundle", async () => {
    const api = {
      diagnosticsSummary: vi.fn().mockResolvedValue({ job_count: 4, failed_jobs: 1, metric_count: 8 }),
      exportDiagnostics: vi.fn().mockResolvedValue({ filename: "blueframe-diagnostics.zip" }),
    };
    const store = new DiagnosticsStore(api as never);
    await store.load(); await store.export();
    expect(store.summary.metric_count).toBe(8);
    expect(store.filename).toBe("blueframe-diagnostics.zip");
  });
});
