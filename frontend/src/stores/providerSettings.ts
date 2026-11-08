import { reactive } from "vue";

import type { ApiClient, VolcengineConfigStatus } from "../api/client";

type ProviderApi = Pick<ApiClient, "getVolcengineConfig" | "saveVolcengineConfig">;

export class ProviderSettingsStore {
  status: VolcengineConfigStatus = { configured: false, model: null };
  busy = false;
  error: string | null = null;

  constructor(private readonly api: ProviderApi) {}

  async load() {
    this.status = await this.api.getVolcengineConfig();
  }

  async save(model: string, apiKey: string) {
    this.busy = true;
    this.error = null;
    try {
      this.status = await this.api.saveVolcengineConfig({
        model,
        ...(apiKey ? { api_key: apiKey } : {}),
      });
    } catch (error) {
      this.error = error instanceof Error ? error.message : "保存火山引擎配置失败";
      throw error;
    } finally {
      this.busy = false;
    }
  }
}

let currentStore: ReturnType<typeof reactive<ProviderSettingsStore>> | undefined;

export function configureProviderSettingsStore(api: ProviderApi) {
  currentStore = reactive(new ProviderSettingsStore(api));
  return currentStore;
}

export function useProviderSettingsStore() {
  if (!currentStore) throw new Error("Provider settings store has not been configured");
  return currentStore;
}
