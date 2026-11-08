import { reactive } from "vue";
import type { ApiClient, JobSummary, ProjectSummary, RecordingSessionSummary } from "../api/client";

type LiveApi = Pick<ApiClient, "createProject" | "getProject" | "listRecordings" | "jobs" | "startRecording" | "stopRecording" | "reconnectRecording">;

export class LiveStore {
  project: ProjectSummary | null = null;
  sessions: RecordingSessionSummary[] = [];
  jobs: JobSummary[] = [];
  busy = false;
  error: string | null = null;
  constructor(private readonly api: LiveApi) {}
  async createProject(name: string, rootId: string) {
    return this.run(() => this.api.createProject({ name, project_type: "live", root_id: rootId, output_relative_path: "BlueFrame-直播交付", config: { segment_seconds: 60 }, idempotency_key: crypto.randomUUID() }));
  }
  async refresh(projectId: string) {
    const [project, sessions, jobs] = await Promise.all([this.api.getProject(projectId), this.api.listRecordings(projectId), this.api.jobs()]);
    this.project = project; this.sessions = sessions; this.jobs = jobs.filter((job) => job.payload?.project_id === projectId);
  }
  async start(projectId: string, displayName: string, playbackUrl: string, confirmed: boolean) {
    return this.run(async () => {
      const session = await this.api.startRecording(projectId, { platform: "douyin", display_name: displayName, playback_url: playbackUrl, authorization_confirmed: confirmed });
      this.sessions.unshift(session); return session;
    });
  }
  async stop(projectId: string, sessionId: string) { return this.replace(await this.run(() => this.api.stopRecording(projectId, sessionId))); }
  async reconnect(projectId: string, sessionId: string) { return this.replace(await this.run(() => this.api.reconnectRecording(projectId, sessionId))); }
  private replace(session: RecordingSessionSummary) { const index = this.sessions.findIndex((item) => item.id === session.id); if (index >= 0) this.sessions[index] = session; return session; }
  private async run<T>(operation: () => Promise<T>) {
    this.busy = true; this.error = null;
    try { return await operation(); }
    catch (error) { this.error = error instanceof Error ? error.message : "直播操作失败"; throw error; }
    finally { this.busy = false; }
  }
}

let currentStore: ReturnType<typeof reactive<LiveStore>> | undefined;
export function configureLiveStore(api: LiveApi) { currentStore = reactive(new LiveStore(api)); return currentStore; }
export function useLiveStore() { if (!currentStore) throw new Error("Live store has not been configured"); return currentStore; }
