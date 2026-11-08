export type Fetcher = typeof fetch;

export interface AccountAccess {
  mode: "online" | "grace" | "readonly";
  grace_remaining_seconds?: number | null;
}

export interface JobSummary {
  id: string;
  job_type: string;
  status: string;
  progress: number;
  payload?: Record<string, unknown>;
  error_summary?: string | null;
}

export interface StoryAnalysisVersion {
  id: string;
  project_id?: string;
  version: number;
  accepted: boolean;
  analysis: {
    episode_summary: string;
    characters: Array<{ name: string; role: string; description: string }>;
    conflicts: Array<{ start_ms: number; end_ms: number; summary: string }>;
    explosions: Array<{ start_ms: number; end_ms: number; title: string; reason: string; score: number }>;
    edit_candidates: Array<{ title: string; rationale: string; segments: Array<[number, number]> }>;
    media_duration_ms: number;
  };
}

export interface ProjectSummary {
  id: string;
  name: string;
  project_type: "drama" | "movie" | "variants" | "live";
  status: string;
  sources?: Array<{ id: string; relative_path: string; media_info?: Record<string, unknown> }>;
}

export interface EditSegment {
  source_id: string;
  source_start_ms: number;
  source_end_ms: number;
  source_duration_ms: number;
}

export interface EditPlan {
  id: string;
  project_id?: string;
  version: number;
  title: string;
  kind: "highlight" | "remix" | "commentary";
  target_duration_ms: number;
  duration_ms?: number;
  segments: EditSegment[];
}

export interface CreateProjectPayload {
  name: string;
  project_type: ProjectSummary["project_type"];
  root_id: string;
  output_relative_path: string;
  config: Record<string, unknown>;
  idempotency_key: string;
}

export interface VolcengineConfigStatus {
  configured: boolean;
  model: string | null;
}

export interface ApiClient {
  request<T>(path: string, init?: RequestInit): Promise<T>;
  systemStatus(): Promise<{ status: string }>;
  accountAccess(): Promise<AccountAccess>;
  jobs(): Promise<JobSummary[]>;
  listProjects(): Promise<ProjectSummary[]>;
  createProject(payload: CreateProjectPayload): Promise<ProjectSummary>;
  addProjectSources(projectId: string, relativePaths: string[]): Promise<ProjectSummary["sources"]>;
  transcribeProject(projectId: string): Promise<JobSummary>;
  getVolcengineConfig(): Promise<VolcengineConfigStatus>;
  saveVolcengineConfig(payload: { model: string; api_key?: string }): Promise<VolcengineConfigStatus>;
  listAnalyses(projectId: string): Promise<StoryAnalysisVersion[]>;
  startAnalysis(projectId: string, idempotencyKey: string): Promise<JobSummary>;
  acceptAnalysis(projectId: string, version: number): Promise<StoryAnalysisVersion>;
  getProject(projectId: string): Promise<ProjectSummary>;
  listEditPlans(projectId: string): Promise<EditPlan[]>;
  saveEditPlan(projectId: string, payload: Omit<EditPlan, "id" | "version" | "project_id" | "duration_ms"> & { idempotency_key: string }): Promise<EditPlan>;
  renderEditPlan(projectId: string, planId: string): Promise<JobSummary>;
}

export function createApiClient(
  baseUrl: string,
  sessionToken: string,
  fetcher: Fetcher = fetch,
): ApiClient {
  const base = new URL(baseUrl);

  async function request<T>(path: string, init: RequestInit = {}): Promise<T> {
    const target = new URL(path, `${base.href.replace(/\/$/, "")}/`);
    const headers = new Headers(init.headers);
    if (target.origin === base.origin) {
      headers.set("X-BlueFrame-Session", sessionToken);
    }
    headers.set("Accept", "application/json");
    if (init.body && !headers.has("Content-Type")) headers.set("Content-Type", "application/json");
    const response = await fetcher(target.href, { ...init, headers });
    if (!response.ok) {
      throw new Error(`API request failed (${response.status})`);
    }
    return response.json() as Promise<T>;
  }

  return {
    request,
    systemStatus: () => request("/api/v1/system/status"),
    accountAccess: () => request("/api/v1/account/access"),
    jobs: () => request("/api/v1/jobs"),
    listProjects: () => request("/api/v1/projects"),
    createProject: (payload) => request("/api/v1/projects", {
      method: "POST", body: JSON.stringify(payload),
    }),
    addProjectSources: (projectId, relativePaths) =>
      request(`/api/v1/projects/${projectId}/sources`, {
        method: "POST", body: JSON.stringify({ relative_paths: relativePaths }),
      }),
    transcribeProject: (projectId) =>
      request(`/api/v1/projects/${projectId}/transcribe`, { method: "POST" }),
    getVolcengineConfig: () => request("/api/v1/providers/volcengine"),
    saveVolcengineConfig: (payload) => request("/api/v1/providers/volcengine", {
      method: "PUT", body: JSON.stringify(payload),
    }),
    listAnalyses: (projectId) => request(`/api/v1/projects/${projectId}/analyses`),
    startAnalysis: (projectId, idempotencyKey) =>
      request(`/api/v1/projects/${projectId}/analyze`, {
        method: "POST",
        body: JSON.stringify({ consent_to_send_transcript: true, idempotency_key: idempotencyKey }),
      }),
    acceptAnalysis: (projectId, version) =>
      request(`/api/v1/projects/${projectId}/analyses/${version}/accept`, { method: "POST" }),
    getProject: (projectId) => request(`/api/v1/projects/${projectId}`),
    listEditPlans: (projectId) => request(`/api/v1/projects/${projectId}/edit-plans`),
    saveEditPlan: (projectId, payload) => request(`/api/v1/projects/${projectId}/edit-plans`, {
      method: "POST", body: JSON.stringify(payload),
    }),
    renderEditPlan: (projectId, planId) =>
      request(`/api/v1/projects/${projectId}/edit-plans/${planId}/render`, { method: "POST" }),
  };
}
