import { reactive } from "vue";

import type { ApiClient, CommentaryScriptVersion, EditPlan, JobSummary, ProjectSummary } from "../api/client";

type MovieApi = Pick<ApiClient, "getProject" | "listCommentary" | "listEditPlans" | "jobs" | "generateCommentary" | "saveCommentary" | "synthesizeCommentary" | "saveEditPlan" | "renderEditPlan">;

export class MovieStore {
  project: ProjectSummary | null = null;
  scripts: CommentaryScriptVersion[] = [];
  plans: EditPlan[] = [];
  jobs: JobSummary[] = [];
  busy = false;
  error: string | null = null;

  constructor(private readonly api: MovieApi) {}

  async refresh(projectId: string) {
    const [project, scripts, plans, jobs] = await Promise.all([
      this.api.getProject(projectId), this.api.listCommentary(projectId), this.api.listEditPlans(projectId), this.api.jobs(),
    ]);
    this.project = project; this.scripts = scripts; this.plans = plans;
    this.jobs = jobs.filter((job) => job.payload?.project_id === projectId);
  }

  async generate(projectId: string, voice: string) {
    return this.run(async () => {
      const job = await this.api.generateCommentary(projectId, {
        voice, consent_to_send_transcript: true, idempotency_key: `commentary:${crypto.randomUUID()}`,
      });
      this.jobs.unshift(job); return job;
    });
  }

  async save(projectId: string, script: CommentaryScriptVersion, title: string, voice: string, texts: string[]) {
    return this.run(async () => {
      const saved = await this.api.saveCommentary(projectId, script.id, {
        title, voice, sentences: texts.filter((text) => text.trim()).map((text) => ({ text: text.trim(), citations: [], manual: true })),
      });
      this.scripts.unshift(saved); return saved;
    });
  }

  async synthesize(projectId: string, scriptId: string) {
    return this.run(async () => {
      const job = await this.api.synthesizeCommentary(projectId, scriptId, `voice:${scriptId}:${crypto.randomUUID()}`);
      this.jobs.unshift(job); return job;
    });
  }

  async createFullLengthPlan(projectId: string) {
    if (!this.project?.sources?.length) throw new Error("素材尚未完成探测，请稍后刷新");
    const durations = new Map(this.project.sources.map((source) => [source.id, Number(source.media_info?.duration_ms || 0)]));
    const cited = (this.scripts[0]?.sentences || []).flatMap((sentence) => sentence.citations).map((citation) => {
      const duration = durations.get(citation.source_id) || 0;
      return {
        source_id: citation.source_id, source_start_ms: Math.max(0, citation.start_ms - 1000),
        source_end_ms: Math.min(duration, citation.end_ms + 1500), source_duration_ms: duration,
      };
    }).filter((segment) => segment.source_duration_ms > 0 && segment.source_end_ms - segment.source_start_ms >= 500);
    const raw = cited.length ? cited : this.project.sources.map((source) => ({
      source_id: source.id, source_start_ms: 0,
      source_end_ms: Number(source.media_info?.duration_ms || 0), source_duration_ms: Number(source.media_info?.duration_ms || 0),
    }));
    const segments = raw.sort((a, b) => a.source_id.localeCompare(b.source_id) || a.source_start_ms - b.source_start_ms).reduce<typeof raw>((merged, item) => {
      const previous = merged.at(-1);
      if (previous && previous.source_id === item.source_id && item.source_start_ms <= previous.source_end_ms) {
        previous.source_end_ms = Math.max(previous.source_end_ms, item.source_end_ms); return merged;
      }
      merged.push({ ...item }); return merged;
    }, []).filter((segment) => segment.source_end_ms - segment.source_start_ms >= 500);
    if (!segments.length) throw new Error("素材时长尚不可用，请等待本地探测完成");
    return this.run(async () => {
      const plan = await this.api.saveEditPlan(projectId, {
        title: cited.length ? "解说证据片段" : "全片解说", kind: "commentary",
        target_duration_ms: segments.reduce((sum, item) => sum + item.source_end_ms - item.source_start_ms, 0),
        segments, idempotency_key: `movie-plan:${projectId}`,
      });
      this.plans.unshift(plan); return plan;
    });
  }

  async render(projectId: string, planId: string, scriptId: string) {
    return this.run(async () => {
      const job = await this.api.renderEditPlan(projectId, planId, scriptId); this.jobs.unshift(job); return job;
    });
  }

  private async run<T>(operation: () => Promise<T>): Promise<T> {
    this.busy = true; this.error = null;
    try { return await operation(); }
    catch (error) { this.error = error instanceof Error ? error.message : "影视解说操作失败"; throw error; }
    finally { this.busy = false; }
  }
}

let currentStore: ReturnType<typeof reactive<MovieStore>> | undefined;
export function configureMovieStore(api: MovieApi) { currentStore = reactive(new MovieStore(api)); return currentStore; }
export function useMovieStore() { if (!currentStore) throw new Error("Movie store has not been configured"); return currentStore; }
