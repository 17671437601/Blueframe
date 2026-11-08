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
}

export interface ProjectSummary {
  id: string;
  name: string;
  project_type: "drama" | "movie" | "variants" | "live";
  status: string;
  sources?: Array<{ id: string; relative_path: string; media_info?: Record<string, unknown> }>;
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
  };
}
