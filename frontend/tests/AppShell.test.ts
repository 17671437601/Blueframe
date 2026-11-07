import { mount } from "@vue/test-utils";
import { createMemoryHistory, createRouter } from "vue-router";

import AppShell from "../src/layout/AppShell.vue";
import PlaceholderView from "../src/views/PlaceholderView.vue";

const labels = ["工作台", "短剧", "电影", "变体", "直播", "资产", "任务", "设置"];

async function mountShell(path = "/") {
  const paths = ["/", "/drama", "/movie", "/variants", "/live", "/assets", "/tasks", "/settings"];
  const router = createRouter({
    history: createMemoryHistory(),
    routes: paths.map((routePath, index) => ({
      path: routePath,
      component: PlaceholderView,
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
  it("renders the eight destinations, active route and task status", async () => {
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
