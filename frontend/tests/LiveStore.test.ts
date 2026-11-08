import { LiveStore } from "../src/stores/live";

describe("LiveStore", () => {
  it("starts and stops an authorized recording without retaining URL", async () => {
    const api = {
      getProject: vi.fn().mockResolvedValue({ id: "p", name: "Live", project_type: "live", status: "ready" }),
      listRecordings: vi.fn().mockResolvedValue([]), jobs: vi.fn().mockResolvedValue([]),
      startRecording: vi.fn().mockResolvedValue({ id: "s", project_id: "p", platform: "douyin", display_name: "主播", intent_active: true, status: "recording", reconnect_count: 0, segments: [] }),
      stopRecording: vi.fn().mockResolvedValue({ id: "s", project_id: "p", platform: "douyin", display_name: "主播", intent_active: false, status: "stopped", reconnect_count: 0, segments: [] }),
      reconnectRecording: vi.fn(), createProject: vi.fn(),
    };
    const store = new LiveStore(api as never);
    await store.start("p", "主播", "https://example/live.flv", true);
    await store.stop("p", "s");
    expect(api.startRecording).toHaveBeenCalledWith("p", expect.objectContaining({ authorization_confirmed: true }));
    expect(JSON.stringify(store.sessions)).not.toContain("live.flv");
  });
});
