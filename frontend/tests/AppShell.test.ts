import { mount } from "@vue/test-utils";
import { defineComponent, h } from "vue";
import { createMemoryHistory, createRouter } from "vue-router";

import AppShell from "../src/layout/AppShell.vue";

const labels = ["工作台", "项目", "素材", "任务", "设置"];
const StubView = defineComponent({ render: () => h("div") });

async function mountShell(path = "/") {
  const paths = ["/", "/projects", "/assets", "/tasks", "/settings"];
  const router = createRouter({
    history: createMemoryHistory(),
    routes: paths.map((routePath, index) => ({
      path: routePath,
      component: StubView,
      meta: { title: labels[index] },
    })),
  });
  await router.push(path);
  await router.isReady();
  return mount(AppShell, {
    props: {
      connection: "online",
      accountMode: "online",
      graceRemainingSeconds: null,
      runningTaskCount: 2,
    },
    global: { plugins: [router] },
  });
}

describe("AppShell", () => {
  it("renders the five destinations, active route and task status", async () => {
    const wrapper = await mountShell("/tasks");
    for (const label of labels) expect(wrapper.text()).toContain(label);
    expect(wrapper.get('[aria-current="page"]').text()).toContain("任务");
    expect(wrapper.text()).toContain("2 个任务运行中");
  });

  it("keeps navigation and retry available while offline", async () => {
    const wrapper = await mountShell();
    await wrapper.setProps({ connection: "offline" });
    expect(wrapper.find("nav").exists()).toBe(true);
    expect(wrapper.get('[data-testid="retry"]').text()).toContain("重试");
  });
});
