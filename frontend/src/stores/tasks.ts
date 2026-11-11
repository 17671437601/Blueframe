import { reactive } from "vue";

import type { ApiClient, JobSummary } from "../api/client";

type TasksApi = Pick<ApiClient, "jobs" | "pauseJob" | "resumeJob" | "cancelJob">;

export class TasksStore {
  jobs: JobSummary[] = [];
  busy = false;
  error: string | null = null;

  constructor(private readonly api: TasksApi) {}

  async refresh(): Promise<void> {
    try {
      this.jobs = await this.api.jobs();
      this.error = null;
    } catch (error) {
      this.error = error instanceof Error ? error.message : "任务列表读取失败";
      throw error;
    }
  }

  pause(jobId: string) {
    return this.control(() => this.api.pauseJob(jobId), "暂停任务失败");
  }

  resume(jobId: string) {
    return this.control(() => this.api.resumeJob(jobId), "继续任务失败");
  }

  cancel(jobId: string) {
    return this.control(() => this.api.cancelJob(jobId), "取消任务失败");
  }

  private async control(operation: () => Promise<JobSummary>, message: string): Promise<JobSummary> {
    this.busy = true;
    this.error = null;
    try {
      const job = await operation();
      const index = this.jobs.findIndex((item) => item.id === job.id);
      if (index >= 0) this.jobs[index] = job;
      else this.jobs.unshift(job);
      return job;
    } catch (error) {
      this.error = error instanceof Error ? error.message : message;
      throw error;
    } finally {
      this.busy = false;
    }
  }
}

let currentStore: ReturnType<typeof reactive<TasksStore>> | undefined;

export function configureTasksStore(api: TasksApi) {
  currentStore = reactive(new TasksStore(api));
  return currentStore;
}

export function useTasksStore() {
  if (!currentStore) throw new Error("Tasks store has not been configured");
  return currentStore;
}
