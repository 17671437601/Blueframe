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

export interface ApiClient {
  request<T>(path: string, init?: RequestInit): Promise<T>;
  systemStatus(): Promise<{ status: string }>;
  accountAccess(): Promise<AccountAccess>;
  jobs(): Promise<JobSummary[]>;
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
  };
}
