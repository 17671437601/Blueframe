import { reactive } from "vue";

import type { ApiClient, EditPlan, EditSegment, JobSummary, ProjectSummary } from "../api/client";

type TimelineApi = Pick<ApiClient, "getProject" | "listEditPlans" | "saveEditPlan" | "renderEditPlan" | "jobs">;

export class TimelineStore {
  project: ProjectSummary | null = null;
  plans: EditPlan[] = [];
  jobs: JobSummary[] = [];
  busy = false;
  error: string | null = null;

  constructor(private readonly api: TimelineApi) {}

  async refresh(projectId: string) {
    const [project, plans, jobs] = await Promise.all([
      this.api.getProject(projectId), this.api.listEditPlans(projectId), this.api.jobs(),
    ]);
    this.project = project; this.plans = plans;
    this.jobs = jobs.filter((job) => job.job_type === "render_edit_plan" && job.payload?.project_id === projectId);
  }

  async save(projectId: string, draft: { title: string; kind: EditPlan["kind"]; target_duration_ms: number; segments: EditSegment[] }) {
    this.busy = true; this.error = null;
    try {
      const plan = await this.api.saveEditPlan(projectId, { ...draft, idempotency_key: `edit:${projectId}:${crypto.randomUUID()}` });
      this.plans.unshift(plan); return plan;
    } catch (error) {
      this.error = error instanceof Error ? error.message : "保存剪辑方案失败"; throw error;
    } finally { this.busy = false; }
  }

  async render(projectId: string, planId: string) {
    const job = await this.api.renderEditPlan(projectId, planId); this.jobs.unshift(job);
  }

  async openOutput(projectId: string) {
    if (!window.pywebview?.api?.open_project_output) throw new Error("请在 Native 桌面窗口中打开交付目录");
    await window.pywebview.api.open_project_output(projectId);
  }
}

let currentStore: ReturnType<typeof reactive<TimelineStore>> | undefined;
export function configureTimelineStore(api: TimelineApi) { currentStore = reactive(new TimelineStore(api)); return currentStore; }
export function useTimelineStore() { if (!currentStore) throw new Error("Timeline store has not been configured"); return currentStore; }
