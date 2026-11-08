import { reactive } from "vue";

import type { ApiClient, VolcengineTtsStatus } from "../api/client";

type TtsApi = Pick<ApiClient, "getVolcengineTtsConfig" | "saveVolcengineTtsConfig">;

export class TtsSettingsStore {
  status: VolcengineTtsStatus = { configured: false, default_voice: null };
  busy = false;
  error: string | null = null;

  constructor(private readonly api: TtsApi) {}

  async load() {
    this.status = await this.api.getVolcengineTtsConfig();
  }

  async save(defaultVoice: string, apiKey: string) {
    this.busy = true;
    this.error = null;
    try {
      this.status = await this.api.saveVolcengineTtsConfig({
        default_voice: defaultVoice,
        ...(apiKey ? { api_key: apiKey } : {}),
      });
    } catch (error) {
      this.error = error instanceof Error ? error.message : "保存语音配置失败";
      throw error;
    } finally {
      this.busy = false;
    }
  }
}

let currentStore: ReturnType<typeof reactive<TtsSettingsStore>> | undefined;

export function configureTtsSettingsStore(api: TtsApi) {
  currentStore = reactive(new TtsSettingsStore(api));
  return currentStore;
}

export function useTtsSettingsStore() {
  if (!currentStore) throw new Error("TTS settings store has not been configured");
  return currentStore;
}
