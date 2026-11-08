import { mount } from "@vue/test-utils";

import AnalysisView from "../src/views/AnalysisView.vue";

describe("AnalysisView", () => {
  it("requires privacy consent and starts a retryable analysis", async () => {
    const start = vi.fn().mockResolvedValue(undefined);
    const wrapper = mount(AnalysisView, {
      props: { projectId: "p1", analyses: [], jobs: [], start, accept: vi.fn(), refresh: vi.fn() },
    });
    expect(wrapper.get('[data-testid="start-analysis"]').attributes("disabled")).toBeDefined();
    await wrapper.get('[name="transcript-consent"]').setValue(true);
    await wrapper.get('[data-testid="start-analysis"]').trigger("click");
    expect(start).toHaveBeenCalledWith("p1");
    expect(wrapper.text()).toContain("仅发送字幕文本");
  });

  it("renders explosion candidates and accepts a version", async () => {
    const accept = vi.fn().mockResolvedValue(undefined);
    const wrapper = mount(AnalysisView, {
      props: {
        projectId: "p1", jobs: [], start: vi.fn(), accept, refresh: vi.fn(),
        analyses: [{ id: "a1", version: 1, accepted: false, analysis: {
          episode_summary: "主角反击", characters: [], conflicts: [], edit_candidates: [], media_duration_ms: 10000,
          explosions: [{ start_ms: 1000, end_ms: 2000, title: "反转", reason: "身份揭晓", score: 95 }],
        }}],
      },
    });
    expect(wrapper.text()).toContain("反转");
    await wrapper.get('[data-testid="accept-analysis"]').trigger("click");
    expect(accept).toHaveBeenCalledWith("p1", 1);
  });
});
