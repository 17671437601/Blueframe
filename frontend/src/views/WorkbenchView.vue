<script setup lang="ts">
import { computed, onMounted } from "vue";
import { useRouter } from "vue-router";

import type { ProjectSummary } from "../api/client";
import {
  formatDateTime,
  isWithinDays,
  jobStatusLabel,
  jobTypeLabel,
  projectStatusLabel,
  projectTypeLabel,
  stageLabel,
} from "../format";
import { useProjectStore } from "../stores/projects";
import { useProviderSettingsStore } from "../stores/providerSettings";
import { useSystemStore } from "../stores/system";

const router = useRouter();
const projects = useProjectStore();
const provider = useProviderSettingsStore();
const system = useSystemStore();

const ACTIVE_JOB_STATUSES = ["queued", "running", "pausing"];
const WORKSPACE_ROUTES: Record<ProjectSummary["project_type"], string> = {
  drama: "/drama",
  movie: "/movie",
  variants: "/variants",
  live: "/live",
};

const recentProjects = computed(() =>
  [...projects.projects]
    .sort((left, right) => (right.created_at ?? "").localeCompare(left.created_at ?? ""))
    .slice(0, 4),
);
const weeklyProjectCount = computed(
  () => projects.projects.filter((project) => isWithinDays(project.created_at, 7)).length,
);
const activeJobs = computed(() => system.jobs.filter((job) => ACTIVE_JOB_STATUSES.includes(job.status)));
const queuedCount = computed(() => system.jobs.filter((job) => job.status === "queued").length);
const runningCount = computed(() => system.jobs.filter((job) => job.status === "running").length);
const failedJobs = computed(() => system.jobs.filter((job) => job.status === "failed"));
const currentJob = computed(
  () => activeJobs.value.find((job) => job.status === "running") ?? activeJobs.value[0] ?? null,
);
const providerLabel = computed(() => (provider.status.configured ? "已配置" : "未配置"));
const providerHint = computed(() => provider.status.model || "前往设置配置");

function projectName(projectId: unknown): string {
  if (typeof projectId !== "string") return "未知项目";
  return projects.projects.find((project) => project.id === projectId)?.name ?? "未知项目";
}

function openProject(project: ProjectSummary): void {
  void router.push(`${WORKSPACE_ROUTES[project.project_type]}/${project.id}`);
}

async function load(): Promise<void> {
  await Promise.allSettled([projects.refresh(), system.refresh(), provider.load()]);
}

onMounted(load);
</script>

<template>
  <div class="workbench">
    <section class="hero-panel">
      <div>
        <p class="eyebrow">BLUEFRAME CREATIVE OS</p>
        <h2>把素材，变成下一条好故事。</h2>
        <p>从智能分析、剧情重组到成片交付，在一个安静、有序的工作流里完成。</p>
        <div class="hero-actions">
          <button class="button button--primary" type="button" @click="router.push('/projects')"><span>＋</span> 新建创作项目</button>
          <button class="button button--ghost" type="button" @click="router.push('/settings')">导入已有项目</button>
        </div>
      </div>
      <div class="hero-visual" aria-hidden="true">
        <span class="orb"></span>
        <span class="frame frame--one"></span>
        <span class="frame frame--two"></span>
        <span class="play">▶</span>
      </div>
    </section>

    <section class="metrics" aria-label="工作区概览">
      <article><span class="metric-icon metric-icon--blue">▦</span><div><small>项目总数</small><strong>{{ projects.projects.length }}</strong><em>本周新增 {{ weeklyProjectCount }} 个</em></div></article>
      <article><span class="metric-icon metric-icon--violet">⏱</span><div><small>运行中任务</small><strong>{{ activeJobs.length }}</strong><em>排队 {{ queuedCount }} · 运行 {{ runningCount }}</em></div></article>
      <article><span class="metric-icon metric-icon--amber">⚡</span><div><small>失败任务</small><strong>{{ failedJobs.length }}</strong><em :class="{ danger: failedJobs.length }">共 {{ system.jobs.length }} 个任务</em></div></article>
      <article><span class="metric-icon metric-icon--cyan">◇</span><div><small>AI 服务</small><strong :class="{ 'service-ok': provider.status.configured }">{{ providerLabel }}</strong><em>{{ providerHint }}</em></div></article>
    </section>

    <div class="content-grid">
      <section class="panel recent-panel">
        <header><div><p class="eyebrow">RECENT</p><h3>最近项目</h3></div><span class="panel-count">共 {{ projects.projects.length }} 个</span></header>
        <div class="project-list">
          <button v-for="project in recentProjects" :key="project.id" class="project-row" type="button" @click="openProject(project)">
            <div class="project-thumb" :class="`project-thumb--${project.project_type}`"><span>▶</span></div>
            <div class="project-copy"><strong>{{ project.name }}</strong><small>{{ projectTypeLabel(project.project_type) }} · {{ formatDateTime(project.created_at) }}</small></div>
            <span class="project-status" :class="`project-status--${project.status}`">{{ projectStatusLabel(project.status) }}</span>
            <span class="project-arrow" aria-hidden="true">→</span>
          </button>
          <p v-if="!recentProjects.length" class="panel-empty">{{ system.connection === "offline" ? "本地服务离线，暂时无法读取项目。" : "还没有项目，从「新建创作项目」开始。" }}</p>
        </div>
      </section>

      <section class="panel task-panel">
        <header><div><p class="eyebrow">PROCESSING</p><h3>运行中任务</h3></div><span v-if="activeJobs.length" class="live-chip"><i></i> LIVE</span></header>
        <article v-if="currentJob" class="active-task">
          <div class="task-heading"><span class="task-symbol">◆</span><div><strong>{{ projectName(currentJob.payload?.project_id) }}</strong><small>{{ jobTypeLabel(currentJob.job_type) }}</small></div><b>{{ Math.round(currentJob.progress) }}%</b></div>
          <div class="stage-line"><span><i :style="{ width: `${Math.round(currentJob.progress)}%` }"></i></span></div>
          <div class="task-meta"><span>{{ stageLabel(currentJob.stage) || jobStatusLabel(currentJob.status) }}</span><span>更新于 {{ formatDateTime(currentJob.updated_at) }}</span></div>
          <div class="stage-steps"><span class="active">● {{ jobStatusLabel(currentJob.status) }}</span><span>尝试 {{ currentJob.attempts ?? 0 }} 次</span><span>共 {{ activeJobs.length }} 个运行中</span><span>#{{ currentJob.id.slice(0, 8) }}</span></div>
        </article>
        <p v-else class="panel-empty task-empty">{{ system.connection === "offline" ? "本地服务离线，暂时无法读取任务。" : "当前没有运行中的任务。" }}</p>
        <button class="all-tasks" type="button" @click="router.push('/tasks')">打开任务中心</button>
      </section>
    </div>
  </div>
</template>
