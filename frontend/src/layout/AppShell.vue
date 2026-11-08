<script setup lang="ts">
import { computed, ref } from "vue";
import { RouterLink, RouterView, useRoute } from "vue-router";

import StatusBanner from "../components/StatusBanner.vue";
import { routeDefinitions } from "../router";
import type { ConnectionState } from "../stores/system";

const props = defineProps<{
  connection: ConnectionState;
  accountMode: "online" | "grace" | "readonly";
  graceRemainingSeconds: number | null;
  runningTaskCount: number;
  refreshing?: boolean;
}>();

defineEmits<{ retry: [] }>();

const route = useRoute();
const drawerOpen = ref(false);
const bannerKind = computed(() => {
  if (props.connection === "offline") return "offline";
  if (props.accountMode === "readonly") return "readonly";
  if (props.accountMode === "grace") return "grace";
  if (props.connection === "degraded") return "degraded";
  return "none";
});
const icons = ["⌂", "◆", "▶", "◇", "◉", "▦", "≋", "⚙"];
const navigationRoutes = routeDefinitions.filter((item) => item.meta.navigation !== false);
</script>

<template>
  <div class="app-frame" :class="{ 'drawer-open': drawerOpen }">
    <a class="skip-link" href="#main-content">跳到主要内容</a>
    <aside id="primary-nav" class="sidebar" aria-label="主导航">
      <div class="brand">
        <span class="brand__mark" aria-hidden="true"><i></i><i></i><i></i></span>
        <span><b>蓝帧</b><small>BlueFrame Studio</small></span>
      </div>
      <nav>
        <RouterLink
          v-for="(item, index) in navigationRoutes"
          :key="item.path"
          :to="item.path"
          :aria-current="route.path === item.path ? 'page' : undefined"
          @click="drawerOpen = false"
        >
          <span class="nav-icon" aria-hidden="true">{{ icons[index] }}</span>
          <span>{{ item.meta.title }}</span>
          <em v-if="item.path === '/tasks' && runningTaskCount">{{ runningTaskCount }}</em>
        </RouterLink>
      </nav>
      <div class="sidebar__footer">
        <span class="service-dot" :class="connection"></span>
        <div><b>本地创作引擎</b><small>{{ connection === 'online' ? '服务运行正常' : '等待连接' }}</small></div>
      </div>
    </aside>
    <button
      v-if="drawerOpen"
      class="drawer-scrim"
      aria-label="关闭导航"
      type="button"
      @click="drawerOpen = false"
    ></button>
    <section class="workspace">
      <header class="topbar">
        <button class="menu-button" type="button" aria-controls="primary-nav" :aria-expanded="drawerOpen" @click="drawerOpen = !drawerOpen">
          <span aria-hidden="true">☰</span><span class="sr-only">打开导航</span>
        </button>
        <div class="page-title">
          <small>{{ route.meta.eyebrow }}</small>
          <h1>{{ route.meta.fullTitle || route.meta.title }}</h1>
        </div>
        <div class="topbar__status" aria-label="任务状态">
          <span class="pulse"></span>
          {{ runningTaskCount ? `${runningTaskCount} 个任务运行中` : "当前无运行任务" }}
        </div>
        <button class="profile-button" type="button" aria-label="账号与授权">蓝</button>
      </header>
      <StatusBanner
        :kind="bannerKind"
        :grace-remaining-seconds="graceRemainingSeconds"
        :refreshing="refreshing"
        @retry="$emit('retry')"
      />
      <main id="main-content" tabindex="-1">
        <RouterView />
      </main>
    </section>
  </div>
</template>
