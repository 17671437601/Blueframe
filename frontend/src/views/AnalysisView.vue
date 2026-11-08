<script setup lang="ts">
import { computed, onMounted, ref } from "vue";

import type { JobSummary, StoryAnalysisVersion } from "../api/client";
import { useAnalysisStore } from "../stores/analysis";

const props = withDefaults(defineProps<{
  projectId: string;
  analyses?: StoryAnalysisVersion[];
  jobs?: JobSummary[];
  start?: (projectId: string) => Promise<void>;
  accept?: (projectId: string, version: number) => Promise<void>;
  refresh?: (projectId: string) => Promise<void>;
}>(), { analyses: () => [], jobs: () => [], start: undefined, accept: undefined, refresh: undefined });

const store = props.start ? null : useAnalysisStore();
const consent = ref(false);
const activeAnalyses = computed(() => store?.analyses ?? props.analyses);
const activeJobs = computed(() => store?.jobs ?? props.jobs);
const latest = computed(() => activeAnalyses.value[0]);
const running = computed(() => activeJobs.value.find((job) => ["queued", "running", "pausing"].includes(job.status)));
const failed = computed(() => activeJobs.value.find((job) => job.status === "failed"));

onMounted(() => props.refresh ? props.refresh(props.projectId) : store!.refresh(props.projectId));
async function start() { if (props.start) await props.start(props.projectId); else await store!.start(props.projectId); }
async function accept(version: number) { if (props.accept) await props.accept(props.projectId, version); else await store!.accept(props.projectId, version); }
</script>

<template>
  <section class="analysis-workspace">
    <header class="wizard-heading"><div><p class="eyebrow">STORY INTELLIGENCE</p><h2>剧情智能分析</h2><p>审阅剧情结构、高能点与候选剪辑方案。</p></div><button class="button button--light" @click="props.refresh ? props.refresh(projectId) : store!.refresh(projectId)">刷新</button></header>
    <div class="analysis-grid">
      <article class="panel analysis-control">
        <header><h3>远程分析</h3><span class="live-chip"><i />火山引擎 Ark</span></header>
        <div class="analysis-body">
          <label class="consent-row"><input v-model="consent" name="transcript-consent" type="checkbox" /><span><b>同意发送转写结果</b><small>仅发送字幕文本；不上传原视频和关键帧。</small></span></label>
          <button class="button button--primary" data-testid="start-analysis" :disabled="!consent || !!running" @click="start">{{ failed ? "重试智能分析" : running ? `分析中 ${Math.round(running.progress)}%` : "开始智能分析" }}</button>
          <p v-if="failed" class="workflow-error">{{ failed.error_summary || "分析失败，请检查服务配置后重试" }}</p>
        </div>
      </article>
      <article class="panel story-summary"><header><h3>剧情总览</h3><em v-if="latest">版本 {{ latest.version }}</em></header><div class="analysis-body"><p>{{ latest?.analysis.episode_summary || "完成本地识别后启动智能分析。" }}</p><div v-if="latest" class="character-chips"><span v-for="character in latest.analysis.characters" :key="character.name">{{ character.name }} · {{ character.role }}</span></div></div></article>
    </div>
    <article v-if="latest" class="panel explosion-panel"><header><h3>高能点候选</h3><button v-if="!latest.accepted" class="button button--primary" data-testid="accept-analysis" @click="accept(latest.version)">接受此版本</button><span v-else class="live-chip"><i />已锁定</span></header><div class="explosion-list"><div v-for="item in latest.analysis.explosions" :key="`${item.start_ms}-${item.title}`"><b>{{ item.score }}</b><span><strong>{{ item.title }}</strong><small>{{ item.reason }} · {{ (item.start_ms / 1000).toFixed(1) }}s</small></span></div><p v-if="!latest.analysis.explosions.length" class="section-help">暂无高能点候选</p></div></article>
    <div v-if="latest?.accepted" class="wizard-actions"><a class="button button--primary analysis-link" :href="`#/drama/${projectId}/edit`">进入成片编辑器</a></div>
  </section>
</template>
