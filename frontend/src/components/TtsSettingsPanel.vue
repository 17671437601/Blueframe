<script setup lang="ts">
import { computed, onMounted, ref } from "vue";

import { useTtsSettingsStore } from "../stores/ttsSettings";

const store = useTtsSettingsStore();
const defaultVoice = ref("zh_female_vv_uranus_bigtts");
const apiKey = ref("");
const saved = ref(false);
const configured = computed(() => store.status.configured);

onMounted(async () => {
  await store.load();
  defaultVoice.value = store.status.default_voice || defaultVoice.value;
});

async function submit() {
  saved.value = false;
  await store.save(defaultVoice.value, apiKey.value);
  apiKey.value = "";
  saved.value = true;
}
</script>

<template>
  <form class="settings-card" @submit.prevent="submit">
    <div class="provider-heading"><span>声</span><div><h3>火山引擎 Seed-TTS 2.0</h3><p>逐句合成 · 本地缓存 · 自动对齐</p></div><b class="provider-state">{{ configured ? "已连接" : "未配置" }}</b></div>
    <label class="field">默认音色<input v-model.trim="defaultVoice" name="defaultVoice" required placeholder="zh_female_vv_uranus_bigtts" /></label>
    <label class="field">API Key<input v-model="apiKey" name="ttsApiKey" type="password" :required="!configured" autocomplete="new-password" placeholder="已配置时留空可保留原密钥" /></label>
    <p class="privacy-note">API Key 只保存在 Windows 凭据管理器；生成的语音按文本、音色和语速缓存到项目目录。</p>
    <p v-if="store.error" class="workflow-error">{{ store.error }}</p><p v-if="saved" class="workflow-message">语音配置已安全保存</p>
    <div class="wizard-actions"><button class="button button--primary" :disabled="store.busy">{{ store.busy ? "保存中…" : "保存语音配置" }}</button></div>
  </form>
</template>
