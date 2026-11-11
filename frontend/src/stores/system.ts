import { reactive } from "vue";

import type { AccountAccess, ApiClient, JobSummary } from "../api/client";

export type ConnectionState = "online" | "offline" | "degraded";

export class SystemStore {
  connection: ConnectionState = "offline";
  accountMode: AccountAccess["mode"] = "online";
  graceRemainingSeconds: number | null = null;
  jobs: JobSummary[] = [];
  refreshing = false;

  constructor(private readonly api: Pick<ApiClient, "systemStatus" | "accountAccess" | "jobs">) {}

  get canRetry(): boolean {
    return this.connection !== "online";
  }

  get runningTaskCount(): number {
    return this.jobs.filter((job) => ["queued", "running", "pausing"].includes(job.status)).length;
  }

  get bannerKind(): "none" | "offline" | "grace" | "readonly" | "degraded" {
    if (this.connection === "offline") return "offline";
    if (this.accountMode === "readonly") return "readonly";
    if (this.accountMode === "grace") return "grace";
    if (this.connection === "degraded") return "degraded";
    return "none";
  }

  async refresh(): Promise<void> {
    this.refreshing = true;
    const [system, account, jobs] = await Promise.allSettled([
      this.api.systemStatus(),
      this.api.accountAccess(),
      this.api.jobs(),
    ]);

    if (system.status === "rejected") {
      this.connection = "offline";
      this.refreshing = false;
      return;
    }

    this.connection = account.status === "fulfilled" && jobs.status === "fulfilled" ? "online" : "degraded";
    if (account.status === "fulfilled") {
      this.accountMode = account.value.mode;
      this.graceRemainingSeconds = account.value.grace_remaining_seconds ?? null;
    }
    if (jobs.status === "fulfilled") this.jobs = jobs.value;
    this.refreshing = false;
  }
}

let currentStore: ReturnType<typeof reactive<SystemStore>> | undefined;

export function configureSystemStore(api: Pick<ApiClient, "systemStatus" | "accountAccess" | "jobs">) {
  currentStore = reactive(new SystemStore(api));
  return currentStore;
}

export function useSystemStore() {
  if (!currentStore) throw new Error("System store has not been configured");
  return currentStore;
}
