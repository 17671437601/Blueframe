<script setup lang="ts">
import { computed, onMounted, onUnmounted, ref } from "vue";

import type { JobSummary } from "../api/client";
import { formatDateTime, jobStatusLabel, jobTypeLabel, stageLabel } from "../format";
import { useProjectStore } from "../stores/projects";
import { useTasksStore } from "../stores/tasks";

const tasks = useTasksStore();
const projects = useProjectStore();
const filter = ref<"all" | "active" | "failed" | "completed">("all");
const message = ref("");
let timer: number | undefined;

const FILTERS = [
  { value: "all", label: "全部" },
  { value: "active", label: "运行中" },
  { value: "failed", label: "失败" },
  { value: "completed", label: "已完成" },
] as const;

const ACTIVE_STATUSES = ["queued", "running", "pausing", "paused", "interrupted"];

const visibleJobs = computed(() => {
  if (filter.value === "active") return tasks.jobs.filter((job) => ACTIVE_STATUSES.includes(job.status));
  if (filter.value === "failed") return tasks.jobs.filter((job) => job.status === "failed");
  if (filter.value === "completed") return tasks.jobs.filter((job) => job.status === "completed");
  return tasks.jobs;
});
const counts = computed(() => ({
  all: tasks.jobs.length,
  active: tasks.jobs.filter((job) => ACTIVE_STATUSES.includes(job.status)).length,
  failed: tasks.jobs.filter((job) => job.status === "failed").length,
  completed: tasks.jobs.filter((job) => job.status === "completed").length,
}));

function projectName(job: JobSummary): string {
  const projectId = job.payload?.project_id;
  if (typeof projectId !== "string") return "未关联项目";
  return projects.projects.find((project) => project.id === projectId)?.name ?? "未知项目";
}

function canPause(job: JobSummary): boolean {
  return job.status === "running";
}

function canResume(job: JobSummary): boolean {
  return job.status === "paused" || job.status === "interrupted";
}

function canCancel(job: JobSummary): boolean {
  return ["queued", "running", "pausing", "paused"].includes(job.status);
}

async function load(): Promise<void> {
  await Promise.allSettled([tasks.refresh(), projects.refresh()]);
}

async function control(action: "pause" | "resume" | "cancel", job: JobSummary): Promise<void> {
  message.value = "";
  try {
    await tasks[action](job.id);
    message.value = `${jobTypeLabel(job.job_type)}任务已${action === "pause" ? "请求暂停" : action === "resume" ? "重新排队" : "请求取消"}`;
  } catch (error) {
    message.value = error instanceof Error ? error.message : "任务操作失败";
  }
}

onMounted(async () => {
  await load();
  timer = window.setInterval(() => {
    if (!tasks.busy) void tasks.refresh().catch(() => undefined);
  }, 5000);
});

onUnmounted(() => {
  if (timer !== undefined) window.clearInterval(timer);
});
</script>

<template>
  <section class="tasks-workspace">
    <header class="wizard-heading">
      <div><p class="eyebrow">RUN QUEUE</p><h2>任务中心</h2><p>本地服务中的真实任务队列，可暂停、继续或取消。</p></div>
      <button class="button button--light" data-testid="tasks-refresh" type="button" :disabled="tasks.busy" @click="load">{{ tasks.busy ? "刷新中…" : "刷新" }}</button>
    </header>

    <div class="filter-tabs" role="tablist" aria-label="任务筛选">
      <button
        v-for="item in FILTERS"
        :key="item.value"
        type="button"
        role="tab"
        :aria-selected="filter === item.value"
        :class="{ active: filter === item.value }"
        :data-testid="`task-filter-${item.value}`"
        @click="filter = item.value"
      >{{ item.label }}<em>{{ counts[item.value] }}</em></button>
    </div>

    <div class="task-list">
      <article v-for="job in visibleJobs" :key="job.id" class="task-row">
        <div class="task-row__main">
          <strong>{{ jobTypeLabel(job.job_type) }}</strong>
          <small>{{ projectName(job) }} · #{{ job.id.slice(0, 8) }}</small>
        </div>
        <div class="task-row__progress">
          <span><i :style="{ width: `${Math.round(job.progress)}%` }"></i></span>
          <small>{{ stageLabel(job.stage) || "等待阶段更新" }} · {{ Math.round(job.progress) }}%</small>
        </div>
        <div class="task-row__state">
          <span class="task-status" :class="`task-status--${job.status}`">{{ jobStatusLabel(job.status) }}</span>
          <small>{{ formatDateTime(job.updated_at) }}</small>
        </div>
        <div class="task-row__actions">
          <button v-if="canPause(job)" type="button" :disabled="tasks.busy" :data-testid="`task-pause-${job.id}`" @click="control('pause', job)">暂停</button>
          <button v-if="canResume(job)" type="button" :disabled="tasks.busy" :data-testid="`task-resume-${job.id}`" @click="control('resume', job)">继续</button>
          <button v-if="canCancel(job)" class="danger" type="button" :disabled="tasks.busy" :data-testid="`task-cancel-${job.id}`" @click="control('cancel', job)">取消</button>
        </div>
        <p v-if="job.error_summary" class="task-row__error">{{ job.error_summary }}</p>
      </article>
      <p v-if="!visibleJobs.length" class="panel-empty">{{ tasks.error ? "任务列表读取失败，请重试。" : "该分类下暂无任务。" }}</p>
    </div>

    <p v-if="message" class="workflow-message" role="status">{{ message }}</p>
    <p v-if="tasks.error" class="workflow-error" role="alert">{{ tasks.error }}</p>
  </section>
</template>
