import { reactive } from "vue";
import type { ApiClient, AssetSummary } from "../api/client";

type AssetApi = Pick<ApiClient, "listAssets" | "importAssets">;

export class AssetStore {
  assets: AssetSummary[] = [];
  importErrors: Array<{ relative_path: string; message: string }> = [];
  busy = false;
  error: string | null = null;
  constructor(private readonly api: AssetApi) {}
  async refresh(type?: string) { this.assets = await this.api.listAssets(type); }
  async import(payload: Parameters<AssetApi["importAssets"]>[0]) {
    this.busy = true; this.error = null; this.importErrors = [];
    try {
      const result = await this.api.importAssets(payload);
      this.assets.unshift(...result.items.filter((item) => !this.assets.some((old) => old.id === item.id)));
      this.importErrors = result.errors; return result;
    } catch (error) { this.error = error instanceof Error ? error.message : "素材导入失败"; throw error; }
    finally { this.busy = false; }
  }
}

let currentStore: ReturnType<typeof reactive<AssetStore>> | undefined;
export function configureAssetStore(api: AssetApi) { currentStore = reactive(new AssetStore(api)); return currentStore; }
export function useAssetStore() { if (!currentStore) throw new Error("Asset store has not been configured"); return currentStore; }
