import { LegacyImportStore } from "../src/stores/legacyImport";

describe("LegacyImportStore", () => {
  it("requires preview hash before confirmed import", async () => {
    const api = {
      previewLegacyImport: vi.fn().mockResolvedValue({ source_hash: "a".repeat(64), migration_version: "legacy-v1", projects: [], excluded_tables: ["account"], warnings: [] }),
      confirmLegacyImport: vi.fn().mockResolvedValue({ source_hash: "a".repeat(64), imported: 1, skipped: 0, project_ids: ["p"] }),
    };
    const store = new LegacyImportStore(api as never);
    await store.preview("r", "video.db"); await store.confirm("r", "video.db");
    expect(api.confirmLegacyImport).toHaveBeenCalledWith(expect.objectContaining({ expected_source_hash: "a".repeat(64), confirmed: true }));
  });
});
