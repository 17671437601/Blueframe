import { createRouter, createWebHashHistory } from "vue-router";

import WorkbenchView from "./views/WorkbenchView.vue";
import ProjectsView from "./views/ProjectsView.vue";
import DramaView from "./views/DramaView.vue";
import SettingsView from "./views/SettingsView.vue";
import AnalysisView from "./views/AnalysisView.vue";
import HighlightsView from "./views/HighlightsView.vue";
import StoryView from "./views/StoryView.vue";
import TimelineView from "./views/TimelineView.vue";
import MovieView from "./views/MovieView.vue";
import AssetsView from "./views/AssetsView.vue";
import VariantsView from "./views/VariantsView.vue";
import LiveView from "./views/LiveView.vue";
import TasksView from "./views/TasksView.vue";

export const routeDefinitions = [
  { path: "/", name: "workbench", component: WorkbenchView, meta: { title: "工作台", eyebrow: "总览" } },
  { path: "/projects", name: "projects", component: ProjectsView, meta: { title: "项目", fullTitle: "创作项目", eyebrow: "项目库" } },
  { path: "/drama", name: "drama", component: DramaView, meta: { title: "短剧", fullTitle: "短剧生产", eyebrow: "创作流程", navigation: false } },
  { path: "/drama/:projectId", name: "drama-analysis", component: AnalysisView, props: true, meta: { title: "短剧", fullTitle: "剧情分析", eyebrow: "智能审阅", navigation: false } },
  { path: "/drama/:projectId/highlights", name: "drama-highlights", component: HighlightsView, props: true, meta: { title: "短剧", fullTitle: "高光切片", eyebrow: "批量出片", navigation: false } },
  { path: "/drama/:projectId/story", name: "drama-story", component: StoryView, props: true, meta: { title: "短剧", fullTitle: "主线成片", eyebrow: "整剧混剪", navigation: false } },
  { path: "/drama/:projectId/edit", name: "drama-edit", component: TimelineView, props: true, meta: { title: "短剧", fullTitle: "成片编辑", eyebrow: "时间线", navigation: false } },
  { path: "/movie", name: "movie", component: MovieView, meta: { title: "电影", fullTitle: "电影解说", eyebrow: "智能解说", navigation: false } },
  { path: "/movie/:projectId", name: "movie-project", component: MovieView, meta: { title: "电影", fullTitle: "影视解说工作台", eyebrow: "智能解说", navigation: false } },
  { path: "/variants", name: "variants", component: VariantsView, meta: { title: "变体", fullTitle: "视频变体", eyebrow: "批量生成", navigation: false } },
  { path: "/variants/:projectId", name: "variants-project", component: VariantsView, meta: { title: "变体", fullTitle: "变体生产工作台", eyebrow: "批量生成", navigation: false } },
  { path: "/live", name: "live", component: LiveView, meta: { title: "直播", fullTitle: "直播切片", eyebrow: "实时处理", navigation: false } },
  { path: "/live/:projectId", name: "live-project", component: LiveView, meta: { title: "直播", fullTitle: "直播切片工作台", eyebrow: "实时处理", navigation: false } },
  { path: "/assets", name: "assets", component: AssetsView, meta: { title: "素材", fullTitle: "素材中心", eyebrow: "媒体管理" } },
  { path: "/tasks", name: "tasks", component: TasksView, meta: { title: "任务", fullTitle: "任务中心", eyebrow: "运行队列" } },
  { path: "/settings", name: "settings", component: SettingsView, meta: { title: "设置", fullTitle: "系统设置", eyebrow: "偏好与服务" } },
];

export const router = createRouter({
  history: createWebHashHistory(),
  routes: routeDefinitions,
});
