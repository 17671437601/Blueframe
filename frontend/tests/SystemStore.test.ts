import { createApiClient } from "../src/api/client";
import { SystemStore } from "../src/stores/system";

describe("local API boundary", () => {
  it("sends the launch token only to the configured loopback origin", async () => {
    const fetcher = vi.fn().mockImplementation(() =>
      Promise.resolve(new Response("{}", { status: 200 })),
    );
    const client = createApiClient("http://127.0.0.1:43127", "launch-secret", fetcher);

    await client.request("/api/v1/system/status");
    await client.request("https://example.com/telemetry");

    expect(fetcher.mock.calls[0][1].headers.get("X-BlueFrame-Session")).toBe("launch-secret");
    expect(fetcher.mock.calls[1][1].headers.has("X-BlueFrame-Session")).toBe(false);
    expect(fetcher.mock.calls[0][0]).not.toContain("launch-secret");
    expect(localStorage.length).toBe(0);
  });
});

describe("SystemStore", () => {
  it("keeps the shell recoverable when the API is offline", async () => {
    const api = {
      systemStatus: vi.fn().mockRejectedValue(new TypeError("unreachable")),
      accountAccess: vi.fn(),
      jobs: vi.fn(),
    };
    const store = new SystemStore(api);

    await store.refresh();

    expect(store.connection).toBe("offline");
    expect(store.canRetry).toBe(true);
  });

  it("preserves backend supplied grace time and distinguishes readonly", async () => {
    const api = {
      systemStatus: vi.fn().mockResolvedValue({ status: "ok" }),
      accountAccess: vi
        .fn()
        .mockResolvedValueOnce({ mode: "grace", grace_remaining_seconds: 3661 })
        .mockResolvedValueOnce({ mode: "readonly", grace_remaining_seconds: 0 }),
      jobs: vi.fn().mockResolvedValue([]),
    };
    const store = new SystemStore(api);

    await store.refresh();
    expect(store.accountMode).toBe("grace");
    expect(store.graceRemainingSeconds).toBe(3661);

    await store.refresh();
    expect(store.accountMode).toBe("readonly");
    expect(store.bannerKind).toBe("readonly");
  });
});
