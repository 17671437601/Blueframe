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

export interface SourceCitation {
  source_id: string;
  start_ms: number;
  end_ms: number;
  quote: string;
}

export interface CommentarySentence {
  text: string;
  citations: SourceCitation[];
  manual: boolean;
}

export interface CommentaryScriptVersion {
  id: string;
  project_id: string;
  version: number;
  title: string;
  voice: string;
  sentences: CommentarySentence[];
  provider: string;
  model: string;
  created_at: string;
}

export interface AssetSummary {
  id: string;
  sha256: string;
  asset_type: "video" | "audio" | "image" | "font";
  filename: string;
  origin: string;
  license_name: string;
  ownership: "linked" | "managed";
  available: boolean;
  metadata: Record<string, unknown>;
  created_at?: string;
}

export interface VariantItemSummary {
  id: string;
  item_index: number;
  status: string;
  recipe: { seed: number; width: number; height: number; saturation: number; brightness: number; speed: number; audio_gain_db: number; video_bitrate: string; overlay_asset_id?: string | null };
  output_filename?: string | null;
  error_summary?: string | null;
}

export interface VariantBatchSummary {
  id: string;
  project_id: string;
  source_id: string;
  status: string;
  created_at: string;
  items: VariantItemSummary[];
}

export interface RecordingSessionSummary {
  id: string;
  project_id: string;
  platform: "douyin" | "authorized_url";
  display_name: string;
  intent_active: boolean;
  status: string;
  reconnect_count: number;
  error_summary?: string | null;
  created_at?: string;
  segments: Array<{ id: string; sequence: number; status: string; filename: string; duration_ms: number; size_bytes: number }>;
}

export interface LegacyPreviewReport {
  source_hash: string;
  migration_version: string;
  projects: Array<{ legacy_table: string; legacy_id: string; name: string; project_type: string; source_available: boolean; duration_ms: number }>;
  excluded_tables: string[];
  warnings: string[];
}

export interface LegacyImportResult {
  source_hash: string;
  imported: number;
  skipped: number;
  project_ids: string[];
}

export interface DiagnosticsSummary { job_count: number; failed_jobs: number; metric_count: number; }

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

export interface VolcengineTtsStatus {
  configured: boolean;
  default_voice: string | null;
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
  getVolcengineTtsConfig(): Promise<VolcengineTtsStatus>;
  saveVolcengineTtsConfig(payload: { default_voice: string; api_key?: string }): Promise<VolcengineTtsStatus>;
  listAnalyses(projectId: string): Promise<StoryAnalysisVersion[]>;
  startAnalysis(projectId: string, idempotencyKey: string): Promise<JobSummary>;
  acceptAnalysis(projectId: string, version: number): Promise<StoryAnalysisVersion>;
  getProject(projectId: string): Promise<ProjectSummary>;
  listEditPlans(projectId: string): Promise<EditPlan[]>;
  saveEditPlan(projectId: string, payload: Omit<EditPlan, "id" | "version" | "project_id" | "duration_ms"> & { idempotency_key: string }): Promise<EditPlan>;
  renderEditPlan(projectId: string, planId: string, scriptId?: string): Promise<JobSummary>;
  listCommentary(projectId: string): Promise<CommentaryScriptVersion[]>;
  generateCommentary(projectId: string, payload: { voice: string; consent_to_send_transcript: boolean; idempotency_key: string }): Promise<JobSummary>;
  saveCommentary(projectId: string, scriptId: string, payload: { title: string; voice: string; sentences: CommentarySentence[] }): Promise<CommentaryScriptVersion>;
  synthesizeCommentary(projectId: string, scriptId: string, idempotencyKey: string): Promise<JobSummary>;
  listAssets(assetType?: string): Promise<AssetSummary[]>;
  importAssets(payload: { root_id: string; relative_paths: string[]; origin: string; license_name: string; ownership: "linked" | "managed" }): Promise<{ items: AssetSummary[]; errors: Array<{ relative_path: string; message: string }> }>;
  listVariantBatches(projectId: string): Promise<VariantBatchSummary[]>;
  createVariantBatch(projectId: string, payload: { source_id: string; count: number; seed: number; width: number; height: number; overlay_asset_id?: string; idempotency_key: string }): Promise<{ batch: VariantBatchSummary; job: JobSummary }>;
  retryVariantBatch(projectId: string, batchId: string, idempotencyKey: string): Promise<{ batch: VariantBatchSummary; job: JobSummary }>;
  listRecordings(projectId: string): Promise<RecordingSessionSummary[]>;
  startRecording(projectId: string, payload: { platform: "douyin" | "authorized_url"; display_name: string; playback_url: string; authorization_confirmed: boolean }): Promise<RecordingSessionSummary>;
  stopRecording(projectId: string, sessionId: string): Promise<RecordingSessionSummary>;
  reconnectRecording(projectId: string, sessionId: string): Promise<RecordingSessionSummary>;
  previewLegacyImport(payload: { root_id: string; relative_path: string }): Promise<LegacyPreviewReport>;
  confirmLegacyImport(payload: { root_id: string; relative_path: string; expected_source_hash: string; confirmed: true }): Promise<LegacyImportResult>;
  diagnosticsSummary(): Promise<DiagnosticsSummary>;
  exportDiagnostics(): Promise<{ filename: string }>;
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
    getVolcengineTtsConfig: () => request("/api/v1/providers/volcengine-tts"),
    saveVolcengineTtsConfig: (payload) => request("/api/v1/providers/volcengine-tts", {
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
    renderEditPlan: (projectId, planId, scriptId) =>
      request(`/api/v1/projects/${projectId}/edit-plans/${planId}/render`, {
        method: "POST", ...(scriptId ? { body: JSON.stringify({ script_id: scriptId }) } : {}),
      }),
    listCommentary: (projectId) => request(`/api/v1/projects/${projectId}/commentary`),
    generateCommentary: (projectId, payload) => request(`/api/v1/projects/${projectId}/commentary/generate`, {
      method: "POST", body: JSON.stringify(payload),
    }),
    saveCommentary: (projectId, scriptId, payload) => request(`/api/v1/projects/${projectId}/commentary/${scriptId}`, {
      method: "PUT", body: JSON.stringify(payload),
    }),
    synthesizeCommentary: (projectId, scriptId, idempotencyKey) => request(`/api/v1/projects/${projectId}/commentary/${scriptId}/voice`, {
      method: "POST", body: JSON.stringify({ idempotency_key: idempotencyKey }),
    }),
    listAssets: (assetType) => request(`/api/v1/assets${assetType ? `?asset_type=${encodeURIComponent(assetType)}` : ""}`),
    importAssets: (payload) => request("/api/v1/assets", { method: "POST", body: JSON.stringify(payload) }),
    listVariantBatches: (projectId) => request(`/api/v1/projects/${projectId}/variant-batches`),
    createVariantBatch: (projectId, payload) => request(`/api/v1/projects/${projectId}/variant-batches`, { method: "POST", body: JSON.stringify(payload) }),
    retryVariantBatch: (projectId, batchId, idempotencyKey) => request(`/api/v1/projects/${projectId}/variant-batches/${batchId}/retry`, { method: "POST", body: JSON.stringify({ idempotency_key: idempotencyKey }) }),
    listRecordings: (projectId) => request(`/api/v1/projects/${projectId}/recordings`),
    startRecording: (projectId, payload) => request(`/api/v1/projects/${projectId}/recordings`, { method: "POST", body: JSON.stringify(payload) }),
    stopRecording: (projectId, sessionId) => request(`/api/v1/projects/${projectId}/recordings/${sessionId}/stop`, { method: "POST" }),
    reconnectRecording: (projectId, sessionId) => request(`/api/v1/projects/${projectId}/recordings/${sessionId}/reconnect`, { method: "POST" }),
    previewLegacyImport: (payload) => request("/api/v1/legacy-import/preview", { method: "POST", body: JSON.stringify(payload) }),
    confirmLegacyImport: (payload) => request("/api/v1/legacy-import/confirm", { method: "POST", body: JSON.stringify(payload) }),
    diagnosticsSummary: () => request("/api/v1/diagnostics/summary"),
    exportDiagnostics: () => request("/api/v1/diagnostics/export", { method: "POST" }),
  };
}
