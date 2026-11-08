import { ProviderSettingsStore } from "../src/stores/providerSettings";

describe("ProviderSettingsStore", () => {
  it("loads and saves volcengine configuration without retaining the key", async () => {
    const api = {
      getVolcengineConfig: vi.fn().mockResolvedValue({ configured: false, model: null }),
      saveVolcengineConfig: vi.fn().mockResolvedValue({ configured: true, model: "ep-test" }),
    };
    const store = new ProviderSettingsStore(api);
    await store.load();
    await store.save("ep-test", "secret");
    expect(api.saveVolcengineConfig).toHaveBeenCalledWith({ model: "ep-test", api_key: "secret" });
    expect(store.status).toEqual({ configured: true, model: "ep-test" });
    expect(JSON.stringify(store)).not.toContain("secret");
  });
});
