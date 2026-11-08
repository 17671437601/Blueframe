import { TtsSettingsStore } from "../src/stores/ttsSettings";

describe("TtsSettingsStore", () => {
  it("does not resend an empty API key", async () => {
    const saveVolcengineTtsConfig = vi.fn().mockResolvedValue({
      configured: true,
      default_voice: "voice-a",
    });
    const store = new TtsSettingsStore({
      getVolcengineTtsConfig: vi.fn(),
      saveVolcengineTtsConfig,
    });

    await store.save("voice-a", "");

    expect(saveVolcengineTtsConfig).toHaveBeenCalledWith({ default_voice: "voice-a" });
    expect(store.status.configured).toBe(true);
  });
});
