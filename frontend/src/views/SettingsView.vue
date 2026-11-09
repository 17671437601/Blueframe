<script setup lang="ts">
import { computed, onMounted, ref } from "vue";

import { useProviderSettingsStore } from "../stores/providerSettings";
import TtsSettingsPanel from "../components/TtsSettingsPanel.vue";
import LegacyImportPanel from "../components/LegacyImportPanel.vue";

const props = withDefaults(defineProps<{
  configured?: boolean;
  model?: string;
  busy?: boolean;
  save?: (model: string, apiKey: string) => Promise<void>;
}>(), { configured: false, model: "", busy: false, save: undefined });

const store = props.save ? null : useProviderSettingsStore();
const model = ref(props.model || store?.status.model || "");
const apiKey = ref("");
const saved = ref(false);
const isConfigured = computed(() => store?.status.configured ?? props.configured);
const isBusy = computed(() => store?.busy ?? props.busy);
const error = computed(() => store?.error ?? null);

onMounted(async () => {
  if (!store) return;
  await store.load();
  model.value = store.status.model || "";
});

async function submit() {
  saved.value = false;
  if (props.save) await props.save(model.value, apiKey.value);
  else await store!.save(model.value, apiKey.value);
  apiKey.value = "";
  saved.value = true;
}
</script>

<template>
  <section class="settings-workspace">
    <header class="wizard-heading">
      <div><p class="eyebrow">REMOTE AI</p><h2>智能服务设置</h2><p>配置火山引擎方舟模型；密钥保存在 Windows 凭据管理器中。</p></div>
      <span class="step-count">{{ isConfigured ? "已连接" : "未配置" }}</span>
    </header>
    <form class="settings-card" @submit.prevent="submit">
      <div class="provider-heading"><span>火</span><div><h3>火山引擎 Ark</h3><p>Responses API · JSON Schema 严格输出</p></div></div>
      <label class="field">模型或推理接入点 ID<input v-model.trim="model" name="model" required placeholder="例如 ep-2026..." /></label>
      <label class="field">API Key<input v-model="apiKey" name="apiKey" type="password" :required="!isConfigured" autocomplete="new-password" placeholder="已配置时留空可保留原密钥" /></label>
      <p class="privacy-note">默认仅发送字幕文本，不上传原始视频或关键帧。密钥不会写入项目文件、日志或前端缓存。</p>
      <p v-if="error" class="workflow-error">{{ error }}</p><p v-if="saved" class="workflow-message">配置已安全保存</p>
      <div class="wizard-actions"><button class="button button--primary" :disabled="isBusy">{{ isBusy ? "保存中…" : "保存配置" }}</button></div>
    </form>
    <TtsSettingsPanel />
    <LegacyImportPanel />
  </section>
</template>
