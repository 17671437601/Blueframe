import { AssetStore } from "../src/stores/assets";

describe("AssetStore", () => {
  it("imports provenance and keeps partial errors visible", async () => {
    const api = {
      listAssets: vi.fn().mockResolvedValue([]),
      importAssets: vi.fn().mockResolvedValue({ items: [{ id: "a", filename: "海报.png", asset_type: "image", sha256: "x", origin: "自有", license_name: "授权", ownership: "linked", available: true, metadata: {} }], errors: [{ relative_path: "坏文件.txt", message: "unsupported" }] }),
    };
    const store = new AssetStore(api as never);
    await store.import({ root_id: "r", relative_paths: ["海报.png", "坏文件.txt"], origin: "自有", license_name: "授权", ownership: "linked" });
    expect(store.assets).toHaveLength(1);
    expect(store.importErrors).toHaveLength(1);
  });
});
