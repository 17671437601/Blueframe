<script setup lang="ts">
import { computed, onMounted, onUnmounted, ref, watch } from "vue";

import ProjectTabs from "../components/ProjectTabs.vue";
import { useHighlightStore } from "../stores/highlights";

const props = defineProps<{ projectId: string }>();

const store = useHighlightStore();
const targetCount = ref(20);
const minSeconds = ref(10);
const maxSeconds = ref(45);
const burnSubtitles = ref(true);
const selectedBatchId = ref("");
const message = ref("");
let timer: number | undefined;

const ACTIVE_STATUSES = ["queued", "running", "paused", "pausing"];

const selectedBatch = computed(
  () => store.batches.find((batch) => batch.id === selectedBatchId.value) || store.batches[0] || null,
);
const latestAnalysis = computed(() => store.latestAnalysis);
const hasActiveBatch = computed(() =>
  store.batches.some((batch) => ACTIVE_STATUSES.includes(batch.status)),
);
const clipStats = computed(() => {
  const clips = selectedBatch.value?.clips ?? [];
  return {
    total: clips.length,
    completed: clips.filter((clip) => clip.status === "completed").length,
    failed: clips.filter((clip) => clip.status === "failed").length,
  };
});
const canSubmit = computed(
  () =>
    !store.busy &&
    !!latestAnalysis.value &&
    targetCount.value >= 1 &&
    targetCount.value <= 60 &&
    minSeconds.value >= 3 &&
    maxSeconds.value <= 180 &&
    maxSeconds.value > minSeconds.value,
);

async function refresh() {
  await store.refresh(props.projectId);
  if (!selectedBatchId.value && store.batches[0]) selectedBatchId.value = store.batches[0].id;
}

onMounted(async () => {
  await refresh();
  timer = window.setInterval(() => {
    if (!store.busy && hasActiveBatch.value) void refresh().catch(() => undefined);
  }, 4000);
});

onUnmounted(() => {
  if (timer !== undefined) window.clearInterval(timer);
});

watch(
  () => selectedBatch.value?.id,
  (value) => {
    if (value) selectedBatchId.value = value;
  },
);

async function submit() {
  message.value = "";
  try {
    const result = await store.create(props.projectId, {
      ...(latestAnalysis.value ? { analysis_version_id: latestAnalysis.value.id } : {}),
      target_count: targetCount.value,
      min_duration_ms: minSeconds.value * 1000,
      max_duration_ms: maxSeconds.value * 1000,
      burn_subtitles: burnSubtitles.value,
      idempotency_key: `highlight:${props.projectId}:${crypto.randomUUID()}`,
    });
    selectedBatchId.value = result.batch.id;
    message.value = `已提交 ${result.batch.clips.length} 个高光片段，任务进入队列`;
  } catch (error) {
    message.value = error instanceof Error ? error.message : "提交高光批次失败";
  }
}

async function retryFailed() {
  if (!selectedBatch.value) return;
  message.value = "";
  try {
    await store.retry(props.projectId, selectedBatch.value.id);
    message.value = "失败片段已重新进入队列";
  } catch (error) {
    message.value = error instanceof Error ? error.message : "重试失败";
  }
}

async function openOutput() {
  if (!window.pywebview?.api?.open_project_output) {
    message.value = "请在 Native 桌面窗口中打开交付目录";
    return;
  }
  await window.pywebview.api.open_project_output(props.projectId);
}

function clock(ms: number): string {
  const total = Math.max(0, Math.round(ms / 100) / 10);
  const minutes = Math.floor(total / 60);
  const seconds = (total - minutes * 60).toFixed(1).padStart(4, "0");
  return `${minutes}:${seconds}`;
}

function clipStatusLabel(status: string): string {
  return (
    {
      queued: "排队中",
      running: "渲染中",
      completed: "已完成",
      failed: "失败",
      paused: "已暂停",
      cancelled: "已取消",
    }[status] ?? status
  );
}

function batchStatusLabel(status: string): string {
  return (
    {
      queued: "排队中",
      running: "渲染中",
      completed: "已完成",
      partial: "部分完成",
      failed: "失败",
      paused: "已暂停",
      cancelled: "已取消",
    }[status] ?? status
  );
}
</script>

<template>
  <section class="highlights-workspace">
    <ProjectTabs :project-id="projectId" active="highlights" />
    <header class="wizard-heading">
      <div>
        <p class="eyebrow">HIGHLIGHT CUTS</p>
        <h2>整剧高光切片</h2>
        <p>提交整部剧集，按剧情高能点一次产出多个独立片段，每段带 AI 标题与硬字幕。</p>
      </div>
      <button class="button button--light" type="button" :disabled="store.busy" @click="refresh">
        {{ store.busy ? "刷新中…" : "刷新状态" }}
      </button>
    </header>

    <div class="highlights-grid">
      <article class="panel highlight-config">
        <header><h3>批次配置</h3><em v-if="latestAnalysis">分析版本 {{ latestAnalysis.version }}</em></header>
        <div class="movie-card-body">
          <div class="settings-grid">
            <label>片段数量<input v-model.number="targetCount" type="number" min="1" max="60" /></label>
            <label>最短时长（秒）<input v-model.number="minSeconds" type="number" min="3" max="180" /></label>
            <label>最长时长（秒）<input v-model.number="maxSeconds" type="number" min="5" max="180" /></label>
          </div>
          <label class="consent-row">
            <input v-model="burnSubtitles" type="checkbox" />
            <span><b>烧录硬字幕</b><small>按识别时间轴裁剪字幕，片段边界自动对齐到台词。</small></span>
          </label>
          <p v-if="!latestAnalysis" class="workflow-warning">
            尚未完成剧情分析，请先在“剧情分析”标签页完成并接受一个版本。
          </p>
          <p v-else-if="!latestAnalysis.accepted" class="privacy-note">
            当前使用的是未锁定版本；建议先在剧情分析页接受版本，避免结果被后续分析覆盖。
          </p>
          <p class="privacy-note">
            规划时按高能点评分排序，自动去重重叠片段，并跳过短于 3 秒的碎片。
          </p>
          <button
            class="button button--primary"
            type="button"
            data-testid="start-highlights"
            :disabled="!canSubmit"
            @click="submit"
          >
            {{ store.busy ? "提交中…" : `生成 ${targetCount} 个高光片段` }}
          </button>
        </div>
      </article>

      <article class="panel highlight-results">
        <header>
          <h3>片段结果</h3>
          <select v-if="store.batches.length" v-model="selectedBatchId">
            <option v-for="batch in store.batches" :key="batch.id" :value="batch.id">
              {{ batch.id.slice(0, 8) }} · {{ batchStatusLabel(batch.status) }}
            </option>
          </select>
        </header>

        <div v-if="selectedBatch" class="highlight-body">
          <div class="highlight-summary">
            <span class="live-chip"><i />{{ batchStatusLabel(selectedBatch.status) }}</span>
            <small>完成 {{ clipStats.completed }} / {{ clipStats.total }} · 失败 {{ clipStats.failed }}</small>
            <small>片段 {{ selectedBatch.min_duration_ms / 1000 }}–{{ selectedBatch.max_duration_ms / 1000 }} 秒</small>
          </div>

          <div class="highlight-clips">
            <div
              v-for="clip in selectedBatch.clips"
              :key="clip.id"
              class="highlight-clip"
              :class="`status-${clip.status}`"
            >
              <div class="highlight-clip__index">
                <span>#{{ clip.item_index + 1 }}</span>
                <b>{{ clip.score }}</b>
              </div>
              <div class="highlight-clip__main">
                <strong>{{ clip.title }}</strong>
                <small>{{ clip.reason }}</small>
                <em>{{ clock(clip.start_ms) }} – {{ clock(clip.end_ms) }} · {{ (clip.duration_ms / 1000).toFixed(1) }}s</em>
                <span v-if="clip.output_filename" class="highlight-clip__file">{{ clip.output_filename }}</span>
              </div>
              <div class="highlight-clip__state">
                <span class="task-status" :class="`task-status--${clip.status}`">{{ clipStatusLabel(clip.status) }}</span>
                <small v-if="clip.error_summary" class="highlight-clip__error">{{ clip.error_summary }}</small>
              </div>
            </div>
          </div>

          <footer class="variant-actions">
            <button
              class="button button--light"
              type="button"
              :disabled="!clipStats.failed || store.busy"
              @click="retryFailed"
            >仅重试失败片段</button>
            <button class="button button--primary" type="button" @click="openOutput">打开交付目录</button>
          </footer>
        </div>

        <div v-else class="empty-script">
          <p>配置批次后提交，整剧高光片段会逐项出现在这里，单项失败不影响其他片段。</p>
        </div>
      </article>
    </div>

    <p v-if="message" class="workflow-message" role="status">{{ message }}</p>
    <p v-if="store.error" class="workflow-error" role="alert">{{ store.error }}</p>
  </section>
</template>
