import { reactive } from "vue";

import type { ApiClient, JobSummary, StoryAnalysisVersion, StoryBatchSummary } from "../api/client";

type StoryApi = Pick<
  ApiClient,
  "listStoryBatches" | "listAnalyses" | "jobs" | "createStoryBatch" | "retryStoryBatch"
>;
type CreatePayload = Parameters<StoryApi["createStoryBatch"]>[1];

export class StoryStore {
  batches: StoryBatchSummary[] = [];
  analyses: StoryAnalysisVersion[] = [];
  jobs: JobSummary[] = [];
  busy = false;
  error: string | null = null;

  constructor(private readonly api: StoryApi) {}

  get latestAnalysis(): StoryAnalysisVersion | null {
    return this.analyses.find((item) => item.accepted) ?? this.analyses[0] ?? null;
  }

  async refresh(projectId: string) {
    const [batches, analyses, jobs] = await Promise.all([
      this.api.listStoryBatches(projectId),
      this.api.listAnalyses(projectId),
      this.api.jobs(),
    ]);
    this.batches = batches;
    this.analyses = analyses;
    this.jobs = jobs.filter(
      (job) => job.payload?.project_id === projectId && job.job_type === "render_story_batch",
    );
  }

  async create(projectId: string, payload: CreatePayload) {
    return this.run(async () => {
      const result = await this.api.createStoryBatch(projectId, payload);
      this.batches.unshift(result.batch);
      this.jobs.unshift(result.job);
      return result;
    });
  }

  async retry(projectId: string, batchId: string) {
    return this.run(async () => {
      const result = await this.api.retryStoryBatch(
        projectId,
        batchId,
        `story-retry:${batchId}:${crypto.randomUUID()}`,
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
      this.error = error instanceof Error ? error.message : "主线成片操作失败";
      throw error;
    } finally {
      this.busy = false;
    }
  }
}

let currentStore: ReturnType<typeof reactive<StoryStore>> | undefined;

export function configureStoryStore(api: StoryApi) {
  currentStore = reactive(new StoryStore(api));
  return currentStore;
}

export function useStoryStore() {
  if (!currentStore) throw new Error("Story store has not been configured");
  return currentStore;
}
