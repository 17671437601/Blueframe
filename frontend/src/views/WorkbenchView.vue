<script setup lang="ts">
import { useRouter } from "vue-router";

const router = useRouter();
const recentProjects = [
  { title: "都市悬疑 · 第 12 集", meta: "今天 10:24 · 16:9", progress: 72, accent: "#246bfd" },
  { title: "逆风翻盘 · 精华版", meta: "昨天 18:40 · 9:16", progress: 100, accent: "#7b61ff" },
  { title: "夏夜回声 · 预告", meta: "11 月 2 日 · 16:9", progress: 38, accent: "#00a7b7" },
];
</script>

<template>
  <div class="workbench">
    <section class="hero-panel">
      <div>
        <p class="eyebrow">BLUEFRAME CREATIVE OS</p>
        <h2>把素材，变成下一条好故事。</h2>
        <p>从智能分析、剧情重组到成片交付，在一个安静、有序的工作流里完成。</p>
        <div class="hero-actions">
          <button class="button button--primary" type="button" @click="router.push('/drama')"><span>＋</span> 新建创作项目</button>
          <button class="button button--ghost" type="button">导入已有项目</button>
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
      <article><span class="metric-icon metric-icon--blue">▦</span><div><small>本周项目</small><strong>12</strong><em>↑ 18%</em></div></article>
      <article><span class="metric-icon metric-icon--violet">⏱</span><div><small>节省创作时间</small><strong>28.5h</strong><em>本月累计</em></div></article>
      <article><span class="metric-icon metric-icon--cyan">◇</span><div><small>AI 服务</small><strong class="service-ok">运行正常</strong><em>火山引擎 · 低延迟</em></div></article>
      <article><span class="metric-icon metric-icon--amber">⚡</span><div><small>平均阶段耗时</small><strong>4m 12s</strong><em>较上周 -9%</em></div></article>
    </section>

    <div class="content-grid">
      <section class="panel recent-panel">
        <header><div><p class="eyebrow">RECENT</p><h3>最近项目</h3></div><button type="button">查看全部 →</button></header>
        <div class="project-list">
          <article v-for="project in recentProjects" :key="project.title" class="project-row">
            <div class="project-thumb" :style="{ '--accent': project.accent }"><span>▶</span></div>
            <div class="project-copy"><strong>{{ project.title }}</strong><small>{{ project.meta }}</small></div>
            <div class="project-progress"><span><i :style="{ width: `${project.progress}%` }"></i></span><small>{{ project.progress }}%</small></div>
            <button type="button" :aria-label="`${project.title} 更多操作`">•••</button>
          </article>
        </div>
      </section>

      <section class="panel task-panel">
        <header><div><p class="eyebrow">PROCESSING</p><h3>运行中任务</h3></div><span class="live-chip"><i></i> LIVE</span></header>
        <article class="active-task">
          <div class="task-heading"><span class="task-symbol">◆</span><div><strong>都市悬疑 · 第 12 集</strong><small>智能剧情分析</small></div><b>68%</b></div>
          <div class="stage-line"><span><i></i></span></div>
          <div class="task-meta"><span>正在识别高光片段</span><span>预计剩余 2m 18s</span></div>
          <div class="stage-steps"><span class="done">✓ 素材解析</span><span class="done">✓ 字幕识别</span><span class="active">● 剧情分析</span><span>○ 方案生成</span></div>
        </article>
        <button class="all-tasks" type="button">打开任务中心</button>
      </section>
    </div>
  </div>
</template>
