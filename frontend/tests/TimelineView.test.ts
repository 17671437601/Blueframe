import { mount } from "@vue/test-utils";

import TimelineView from "../src/views/TimelineView.vue";
import type { EditPlan } from "../src/api/client";

const plan: EditPlan = {
  id: "plan-1", version: 1, title: "高光", kind: "highlight", target_duration_ms: 5000,
  segments: [
    { source_id: "s1", source_start_ms: 0, source_end_ms: 2000, source_duration_ms: 10000 },
    { source_id: "s2", source_start_ms: 1000, source_end_ms: 4000, source_duration_ms: 10000 },
  ],
};

describe("TimelineView", () => {
  it("reorders, trims, undoes and shows duration", async () => {
    const save = vi.fn().mockResolvedValue(undefined);
    const wrapper = mount(TimelineView, {
      props: { projectId: "p1", plan, save, render: vi.fn(), refresh: vi.fn(), openOutput: vi.fn() },
    });
    expect(wrapper.text()).toContain("5.0 秒");
    await wrapper.get('[data-testid="move-down-0"]').trigger("click");
    expect(wrapper.findAll("[data-segment]")[0].text()).toContain("s2");
    await wrapper.get('[data-testid="undo"]').trigger("click");
    expect(wrapper.findAll("[data-segment]")[0].text()).toContain("s1");
    await wrapper.get('[data-testid="save-plan"]').trigger("click");
    expect(save).toHaveBeenCalled();
  });

  it("queues render and can open delivery folder", async () => {
    const render = vi.fn().mockResolvedValue(undefined);
    const openOutput = vi.fn().mockResolvedValue(undefined);
    const wrapper = mount(TimelineView, {
      props: { projectId: "p1", plan, save: vi.fn(), render, refresh: vi.fn(), openOutput },
    });
    await wrapper.get('[data-testid="render-plan"]').trigger("click");
    await wrapper.get('[data-testid="open-output"]').trigger("click");
    expect(render).toHaveBeenCalledWith("p1", "plan-1");
    expect(openOutput).toHaveBeenCalledWith("p1");
  });
});
