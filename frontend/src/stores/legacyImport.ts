import { reactive } from "vue";
import type { ApiClient, LegacyImportResult, LegacyPreviewReport } from "../api/client";

type LegacyApi = Pick<ApiClient, "previewLegacyImport" | "confirmLegacyImport">;

export class LegacyImportStore {
  report: LegacyPreviewReport | null = null;
  result: LegacyImportResult | null = null;
  busy = false;
  error: string | null = null;

  constructor(private readonly api: LegacyApi) {}

  async preview(rootId: string, relativePath: string) {
    this.busy = true; this.error = null; this.result = null;
    try { this.report = await this.api.previewLegacyImport({ root_id: rootId, relative_path: relativePath }); return this.report; }
    catch (error) { this.error = error instanceof Error ? error.message : "旧版项目检查失败"; throw error; }
    finally { this.busy = false; }
  }

  async confirm(rootId: string, relativePath: string) {
    if (!this.report) throw new Error("请先预览旧版数据库");
    this.busy = true; this.error = null;
    try {
      this.result = await this.api.confirmLegacyImport({
        root_id: rootId, relative_path: relativePath,
        expected_source_hash: this.report.source_hash, confirmed: true,
      });
      return this.result;
    } catch (error) { this.error = error instanceof Error ? error.message : "旧版项目导入失败"; throw error; }
    finally { this.busy = false; }
  }
}

let currentStore: ReturnType<typeof reactive<LegacyImportStore>> | undefined;
export function configureLegacyImportStore(api: LegacyApi) { currentStore = reactive(new LegacyImportStore(api)); return currentStore; }
export function useLegacyImportStore() { if (!currentStore) throw new Error("Legacy import store has not been configured"); return currentStore; }
