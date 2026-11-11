<script setup lang="ts">
import { computed, onMounted, ref } from "vue";
import { useRouter } from "vue-router";

import type { ProjectSummary } from "../api/client";
import { formatDateTime, projectStatusLabel, projectTypeLabel } from "../format";
import { useProjectStore } from "../stores/projects";

type ProjectType = ProjectSummary["project_type"];

const router = useRouter();
const projects = useProjectStore();
const filter = ref<"" | ProjectType>("");
const error = ref("");

const CREATE_OPTIONS: Array<{ type: ProjectType; title: string; description: string; path: string; icon: string }> = [
  { type: "drama", title: "短剧生产", description: "多集素材，剧情分析后生成高光、重组与解说成片", path: "/drama", icon: "◆" },
  { type: "movie", title: "影视解说", description: "原片识别，事实解说脚本、配音字幕与渲染", path: "/movie", icon: "▶" },
  { type: "variants", title: "视频变体", description: "从主成片批量生成可复现的画幅与包装版本", path: "/variants", icon: "◇" },
  { type: "live", title: "直播切片", description: "授权直播源录制、分段并自动生成可审阅切片", path: "/live", icon: "◉" },
];

const FILTERS: Array<{ value: "" | ProjectType; label: string }> = [
  { value: "", label: "全部" },
  { value: "drama", label: "短剧" },
  { value: "movie", label: "影视解说" },
  { value: "variants", label: "视频变体" },
  { value: "live", label: "直播切片" },
];

const WORKSPACE_ROUTES: Record<ProjectType, string> = {
  drama: "/drama",
  movie: "/movie",
  variants: "/variants",
  live: "/live",
};

const sortedProjects = computed(() =>
  [...projects.projects].sort((left, right) =>
    (right.updated_at ?? right.created_at ?? "").localeCompare(left.updated_at ?? left.created_at ?? ""),
  ),
);
const visibleProjects = computed(() =>
  filter.value ? sortedProjects.value.filter((project) => project.project_type === filter.value) : sortedProjects.value,
);
const counts = computed(() =>
  Object.fromEntries(
    FILTERS.map((item) => [
      item.value,
      item.value ? projects.projects.filter((project) => project.project_type === item.value).length : projects.projects.length,
    ]),
  ) as Record<string, number>,
);

function openProject(project: ProjectSummary): void {
  void router.push(`${WORKSPACE_ROUTES[project.project_type]}/${project.id}`);
}

onMounted(async () => {
  try {
    await projects.refresh();
  } catch {
    error.value = "项目列表读取失败，请确认本地服务已启动。";
  }
});
</script>

<template>
  <section class="projects-workspace">
    <header class="wizard-heading">
      <div><p class="eyebrow">PROJECT LIBRARY</p><h2>创作项目</h2><p>按创作类型归档所有项目，进入项目后完成分析与成片。</p></div>
      <span class="step-count">{{ projects.projects.length }} 个</span>
    </header>

    <div class="project-create" aria-label="新建项目">
      <button v-for="option in CREATE_OPTIONS" :key="option.type" class="type-card" type="button" @click="router.push(option.path)">
        <span class="type-card__icon" :class="`type-card__icon--${option.type}`" aria-hidden="true">{{ option.icon }}</span>
        <span class="type-card__copy"><strong>{{ option.title }}</strong><small>{{ option.description }}</small></span>
        <span class="type-card__plus" aria-hidden="true">＋</span>
      </button>
    </div>

    <div class="filter-tabs" role="tablist" aria-label="项目类型筛选">
      <button
        v-for="item in FILTERS"
        :key="item.value"
        type="button"
        role="tab"
        :aria-selected="filter === item.value"
        :class="{ active: filter === item.value }"
        @click="filter = item.value"
      >{{ item.label }}<em>{{ counts[item.value] }}</em></button>
    </div>

    <section class="panel project-library">
      <header><div><p class="eyebrow">ALL PROJECTS</p><h3>项目列表</h3></div><span class="panel-count">{{ visibleProjects.length }} 个</span></header>
      <div class="project-list">
        <button v-for="project in visibleProjects" :key="project.id" class="project-row" type="button" @click="openProject(project)">
          <div class="project-thumb" :class="`project-thumb--${project.project_type}`"><span>▶</span></div>
          <div class="project-copy"><strong>{{ project.name }}</strong><small>{{ projectTypeLabel(project.project_type) }} · {{ formatDateTime(project.updated_at ?? project.created_at) }}</small></div>
          <span class="project-status" :class="`project-status--${project.status}`">{{ projectStatusLabel(project.status) }}</span>
          <span class="project-arrow" aria-hidden="true">→</span>
        </button>
        <p v-if="!visibleProjects.length" class="panel-empty">{{ error || (filter ? "该类型下还没有项目。" : "还没有项目，从上方选择一种创作类型开始。") }}</p>
      </div>
    </section>

    <p v-if="error && visibleProjects.length" class="workflow-error" role="alert">{{ error }}</p>
  </section>
</template>
