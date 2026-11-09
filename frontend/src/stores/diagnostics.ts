import { reactive } from "vue";
import type { ApiClient, DiagnosticsSummary } from "../api/client";

type DiagnosticsApi = Pick<ApiClient, "diagnosticsSummary" | "exportDiagnostics">;

export class DiagnosticsStore {
  summary: DiagnosticsSummary = { job_count: 0, failed_jobs: 0, metric_count: 0 };
  filename = ""; busy = false; error: string | null = null;
  constructor(private readonly api: DiagnosticsApi) {}
  async load() { this.summary = await this.api.diagnosticsSummary(); }
  async export() {
    this.busy = true; this.error = null;
    try { const result = await this.api.exportDiagnostics(); this.filename = result.filename; return result; }
    catch (error) { this.error = error instanceof Error ? error.message : "诊断包导出失败"; throw error; }
    finally { this.busy = false; }
  }
}

let currentStore: ReturnType<typeof reactive<DiagnosticsStore>> | undefined;
export function configureDiagnosticsStore(api: DiagnosticsApi) { currentStore = reactive(new DiagnosticsStore(api)); return currentStore; }
export function useDiagnosticsStore() { if (!currentStore) throw new Error("Diagnostics store has not been configured"); return currentStore; }
