import { mount } from "@vue/test-utils";

import SettingsView from "../src/views/SettingsView.vue";

describe("SettingsView", () => {
  it("shows the privacy boundary and saves provider settings", async () => {
    const save = vi.fn().mockResolvedValue(undefined);
    const wrapper = mount(SettingsView, {
      props: { configured: false, model: "", busy: false, save },
      global: { stubs: { TtsSettingsPanel: true, LegacyImportPanel: true, DiagnosticsPanel: true } },
    });
    await wrapper.get('[name="model"]').setValue("ep-test");
    await wrapper.get('[name="apiKey"]').setValue("secret");
    await wrapper.get("form").trigger("submit");
    expect(save).toHaveBeenCalledWith("ep-test", "secret");
    expect(wrapper.text()).toContain("默认仅发送字幕文本");
  });
});
