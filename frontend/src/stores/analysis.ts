import { reactive } from "vue";

import type { ApiClient, JobSummary, StoryAnalysisVersion } from "../api/client";

type AnalysisApi = Pick<ApiClient, "listAnalyses" | "jobs" | "startAnalysis" | "acceptAnalysis">;

export class AnalysisStore {
  analyses: StoryAnalysisVersion[] = [];
  jobs: JobSummary[] = [];
  busy = false;
  error: string | null = null;

  constructor(private readonly api: AnalysisApi) {}

  async refresh(projectId: string) {
    const [analyses, jobs] = await Promise.all([this.api.listAnalyses(projectId), this.api.jobs()]);
    this.analyses = analyses;
    this.jobs = jobs.filter((job) => job.payload?.project_id === projectId && job.job_type === "analyze_project");
  }

  async start(projectId: string) {
    this.busy = true;
    this.error = null;
    try {
      const job = await this.api.startAnalysis(projectId, `analysis:${projectId}:${crypto.randomUUID()}`);
      this.jobs.unshift(job);
    } catch (error) {
      this.error = error instanceof Error ? error.message : "启动智能分析失败";
      throw error;
    } finally {
      this.busy = false;
    }
  }

  async accept(projectId: string, version: number) {
    await this.api.acceptAnalysis(projectId, version);
    await this.refresh(projectId);
  }
}

let currentStore: ReturnType<typeof reactive<AnalysisStore>> | undefined;
export function configureAnalysisStore(api: AnalysisApi) {
  currentStore = reactive(new AnalysisStore(api));
  return currentStore;
}
export function useAnalysisStore() {
  if (!currentStore) throw new Error("Analysis store has not been configured");
  return currentStore;
}
