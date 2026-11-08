import { mount } from "@vue/test-utils";

import DramaView from "../src/views/DramaView.vue";
import { configureProjectStore } from "../src/stores/projects";

it("walks through four steps and starts a real project workflow", async () => {
  const api = {
    createProject: vi.fn().mockResolvedValue({ id: "project-1", name: "都市悬疑" }),
    addProjectSources: vi.fn().mockResolvedValue([{ id: "source-1" }]),
    transcribeProject: vi.fn().mockResolvedValue({ id: "job-1" }),
    listProjects: vi.fn().mockResolvedValue([]),
  };
  configureProjectStore(api as never);
  const bridge = {
    select_media_files: vi.fn().mockResolvedValue({ rootId: "root-id", files: ["第一集.mp4"] }),
  };
  window.pywebview = { api: bridge } as never;
  const wrapper = mount(DramaView);

  await wrapper.get('[data-testid="choose-media"]').trigger("click");
  await vi.waitFor(() => expect(wrapper.text()).toContain("第一集.mp4"));
  await wrapper.get('input[name="project-name"]').setValue("都市悬疑");
  for (let step = 0; step < 3; step += 1) {
    await wrapper.get('[data-testid="next-step"]').trigger("click");
  }
  expect(wrapper.text()).toContain("确认并启动");
  await wrapper.get('[data-testid="start-project"]').trigger("click");
  await vi.waitFor(() => expect(api.transcribeProject).toHaveBeenCalledWith("project-1"));
  await vi.waitFor(() => expect(wrapper.text()).toContain("项目已创建"));
});
