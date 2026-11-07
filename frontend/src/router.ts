import { createRouter, createWebHashHistory } from "vue-router";

import PlaceholderView from "./views/PlaceholderView.vue";
import WorkbenchView from "./views/WorkbenchView.vue";

export const routeDefinitions = [
  { path: "/", name: "workbench", component: WorkbenchView, meta: { title: "工作台", eyebrow: "总览" } },
  { path: "/drama", name: "drama", component: PlaceholderView, meta: { title: "短剧", fullTitle: "短剧生产", eyebrow: "创作流程" } },
  { path: "/movie", name: "movie", component: PlaceholderView, meta: { title: "电影", fullTitle: "电影解说", eyebrow: "智能解说" } },
  { path: "/variants", name: "variants", component: PlaceholderView, meta: { title: "变体", fullTitle: "视频变体", eyebrow: "批量生成" } },
  { path: "/live", name: "live", component: PlaceholderView, meta: { title: "直播", fullTitle: "直播切片", eyebrow: "实时处理" } },
  { path: "/assets", name: "assets", component: PlaceholderView, meta: { title: "资产", fullTitle: "素材中心", eyebrow: "媒体管理" } },
  { path: "/tasks", name: "tasks", component: PlaceholderView, meta: { title: "任务", fullTitle: "任务中心", eyebrow: "运行队列" } },
  { path: "/settings", name: "settings", component: PlaceholderView, meta: { title: "设置", fullTitle: "系统设置", eyebrow: "偏好与服务" } },
];

export const router = createRouter({
  history: createWebHashHistory(),
  routes: routeDefinitions,
});
