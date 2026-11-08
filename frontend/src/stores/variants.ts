import { reactive } from "vue";
import type { ApiClient, AssetSummary, JobSummary, ProjectSummary, VariantBatchSummary } from "../api/client";

type VariantApi = Pick<ApiClient, "getProject" | "listVariantBatches" | "listAssets" | "jobs" | "createVariantBatch" | "retryVariantBatch">;
type CreatePayload = Parameters<VariantApi["createVariantBatch"]>[1];

export class VariantStore {
  project: ProjectSummary | null = null;
  batches: VariantBatchSummary[] = [];
  overlays: AssetSummary[] = [];
  jobs: JobSummary[] = [];
  busy = false;
  error: string | null = null;
  constructor(private readonly api: VariantApi) {}
  async refresh(projectId: string) {
    const [project, batches, overlays, jobs] = await Promise.all([
      this.api.getProject(projectId), this.api.listVariantBatches(projectId), this.api.listAssets("image"), this.api.jobs(),
    ]);
    this.project = project; this.batches = batches; this.overlays = overlays.filter((asset) => asset.available);
    this.jobs = jobs.filter((job) => job.payload?.project_id === projectId && job.job_type === "render_variant_batch");
  }
  async create(projectId: string, payload: CreatePayload) {
    return this.run(async () => {
      const result = await this.api.createVariantBatch(projectId, payload);
      this.batches.unshift(result.batch); this.jobs.unshift(result.job); return result;
    });
  }
  async retry(projectId: string, batchId: string) {
    return this.run(async () => {
      const result = await this.api.retryVariantBatch(projectId, batchId, `retry:${batchId}:${crypto.randomUUID()}`);
      const index = this.batches.findIndex((batch) => batch.id === batchId);
      if (index >= 0) this.batches[index] = result.batch; this.jobs.unshift(result.job); return result;
    });
  }
  private async run<T>(operation: () => Promise<T>) {
    this.busy = true; this.error = null;
    try { return await operation(); }
    catch (error) { this.error = error instanceof Error ? error.message : "变体任务操作失败"; throw error; }
    finally { this.busy = false; }
  }
}

let currentStore: ReturnType<typeof reactive<VariantStore>> | undefined;
export function configureVariantStore(api: VariantApi) { currentStore = reactive(new VariantStore(api)); return currentStore; }
export function useVariantStore() { if (!currentStore) throw new Error("Variant store has not been configured"); return currentStore; }
