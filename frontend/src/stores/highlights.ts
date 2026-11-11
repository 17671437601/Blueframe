import { reactive } from "vue";

import type { ApiClient, HighlightBatchSummary, JobSummary, StoryAnalysisVersion } from "../api/client";

type HighlightsApi = Pick<
  ApiClient,
  "listHighlightBatches" | "listAnalyses" | "jobs" | "createHighlightBatch" | "retryHighlightBatch"
>;
type CreatePayload = Parameters<HighlightsApi["createHighlightBatch"]>[1];

export class HighlightStore {
  batches: HighlightBatchSummary[] = [];
  analyses: StoryAnalysisVersion[] = [];
  jobs: JobSummary[] = [];
  busy = false;
  error: string | null = null;

  constructor(private readonly api: HighlightsApi) {}

  get latestAnalysis(): StoryAnalysisVersion | null {
    return this.analyses.find((item) => item.accepted) ?? this.analyses[0] ?? null;
  }

  async refresh(projectId: string) {
    const [batches, analyses, jobs] = await Promise.all([
      this.api.listHighlightBatches(projectId),
      this.api.listAnalyses(projectId),
      this.api.jobs(),
    ]);
    this.batches = batches;
    this.analyses = analyses;
    this.jobs = jobs.filter(
      (job) => job.payload?.project_id === projectId && job.job_type === "render_highlights",
    );
  }

  async create(projectId: string, payload: CreatePayload) {
    return this.run(async () => {
      const result = await this.api.createHighlightBatch(projectId, payload);
      this.batches.unshift(result.batch);
      this.jobs.unshift(result.job);
      return result;
    });
  }

  async retry(projectId: string, batchId: string) {
    return this.run(async () => {
      const result = await this.api.retryHighlightBatch(
        projectId,
        batchId,
        `highlight-retry:${batchId}:${crypto.randomUUID()}`,
      );
      const index = this.batches.findIndex((batch) => batch.id === batchId);
      if (index >= 0) this.batches[index] = result.batch;
      this.jobs.unshift(result.job);
      return result;
    });
  }

  private async run<T>(operation: () => Promise<T>) {
    this.busy = true;
    this.error = null;
    try {
      return await operation();
    } catch (error) {
      this.error = error instanceof Error ? error.message : "高光切片操作失败";
      throw error;
    } finally {
      this.busy = false;
    }
  }
}

let currentStore: ReturnType<typeof reactive<HighlightStore>> | undefined;

export function configureHighlightStore(api: HighlightsApi) {
  currentStore = reactive(new HighlightStore(api));
  return currentStore;
}

export function useHighlightStore() {
  if (!currentStore) throw new Error("Highlight store has not been configured");
  return currentStore;
}
