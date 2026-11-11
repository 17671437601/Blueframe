<script setup lang="ts">
import { computed, onMounted, onUnmounted, ref, watch } from "vue";

import ProjectTabs from "../components/ProjectTabs.vue";
import { useStoryStore } from "../stores/story";

const props = defineProps<{ projectId: string }>();

const store = useStoryStore();
const targetCount = ref(10);
const minMinutes = ref(3);
const maxMinutes = ref(8);
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
const itemStats = computed(() => {
  const items = selectedBatch.value?.items ?? [];
  return {
    total: items.length,
    completed: items.filter((item) => item.status === "completed").length,
    failed: items.filter((item) => item.status === "failed").length,
  };
});
const canSubmit = computed(
  () =>
    !store.busy &&
    !!latestAnalysis.value &&
    targetCount.value >= 1 &&
    targetCount.value <= 50 &&
    minMinutes.value >= 1 &&
    maxMinutes.value <= 60 &&
    maxMinutes.value > minMinutes.value,
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
      min_duration_ms: minMinutes.value * 60_000,
      max_duration_ms: maxMinutes.value * 60_000,
      burn_subtitles: burnSubtitles.value,
      idempotency_key: `story:${props.projectId}:${crypto.randomUUID()}`,
    });
    selectedBatchId.value = result.batch.id;
    message.value = `已提交 ${result.batch.items.length} 条主线成片，任务进入队列`;
  } catch (error) {
    message.value = error instanceof Error ? error.message : "提交主线成片批次失败";
  }
}

async function retryFailed() {
  if (!selectedBatch.value) return;
  message.value = "";
  try {
    await store.retry(props.projectId, selectedBatch.value.id);
    message.value = "失败成片已重新进入队列";
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

function duration(ms: number): string {
  if (!ms) return "—";
  const minutes = Math.floor(ms / 60_000);
  const seconds = Math.round((ms % 60_000) / 1000);
  return seconds ? `${minutes} 分 ${seconds} 秒` : `${minutes} 分钟`;
}

function itemStatusLabel(status: string): string {
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
  <section class="story-workspace">
    <ProjectTabs :project-id="projectId" active="story" />
    <header class="wizard-heading">
      <div>
        <p class="eyebrow">MAIN STORY</p>
        <h2>整剧主线成片</h2>
        <p>按剧集顺序抽取主要剧情拼成多条成片，时长在区间内差异化，每条独立交付。</p>
      </div>
      <button class="button button--light" type="button" :disabled="store.busy" @click="refresh">
        {{ store.busy ? "刷新中…" : "刷新状态" }}
      </button>
    </header>

    <div class="story-grid">
      <article class="panel story-config">
        <header><h3>批次配置</h3><em v-if="latestAnalysis">分析版本 {{ latestAnalysis.version }}</em></header>
        <div class="movie-card-body">
          <div class="settings-grid">
            <label>成片数量<input v-model.number="targetCount" type="number" min="1" max="50" /></label>
            <label>最短时长（分钟）<input v-model.number="minMinutes" type="number" min="1" max="60" /></label>
            <label>最长时长（分钟）<input v-model.number="maxMinutes" type="number" min="1" max="60" /></label>
          </div>
          <label class="consent-row">
            <input v-model="burnSubtitles" type="checkbox" />
            <span><b>烧录硬字幕</b><small>多段拼接后按全局时间轴重新生成字幕，段落边界自动对齐台词。</small></span>
          </label>
          <p v-if="!latestAnalysis" class="workflow-warning">
            尚未完成剧情分析，请先在“剧情分析”标签页完成并接受一个版本。
          </p>
          <p v-else-if="!latestAnalysis.accepted" class="privacy-note">
            当前使用的是未锁定版本；建议先在剧情分析页接受版本，避免结果被后续分析覆盖。
          </p>
          <p class="privacy-note">
            规划时按剧集时长与爆点密度分配配额，顺序选段并自动去重重叠，N 条成片之间控制重合度。
          </p>
          <button
            class="button button--primary"
            type="button"
            data-testid="start-story"
            :disabled="!canSubmit"
            @click="submit"
          >
            {{ store.busy ? "提交中…" : `生成 ${targetCount} 条主线成片` }}
          </button>
        </div>
      </article>

      <article class="panel story-results">
        <header>
          <h3>成片结果</h3>
          <select v-if="store.batches.length" v-model="selectedBatchId">
            <option v-for="batch in store.batches" :key="batch.id" :value="batch.id">
              {{ batch.id.slice(0, 8) }} · {{ batchStatusLabel(batch.status) }}
            </option>
          </select>
        </header>

        <div v-if="selectedBatch" class="story-body">
          <div class="story-batch-summary">
            <span class="live-chip"><i />{{ batchStatusLabel(selectedBatch.status) }}</span>
            <small>完成 {{ itemStats.completed }} / {{ itemStats.total }} · 失败 {{ itemStats.failed }}</small>
            <small>成片时长 {{ selectedBatch.min_duration_ms / 60_000 }}–{{ selectedBatch.max_duration_ms / 60_000 }} 分钟</small>
          </div>

          <div class="story-items">
            <div
              v-for="item in selectedBatch.items"
              :key="item.id"
              class="story-item"
              :class="`status-${item.status}`"
            >
              <div class="story-item__index">
                <span>#{{ item.item_index + 1 }}</span>
                <b>{{ item.item_index + 1 }}</b>
              </div>
              <div class="story-item__main">
                <strong>{{ item.title }}</strong>
                <em>目标 {{ duration(item.target_duration_ms) }} · 实际 {{ duration(item.duration_ms) }}</em>
                <span v-if="item.output_filename" class="story-item__file">{{ item.output_filename }}</span>
              </div>
              <div class="story-item__state">
                <span class="task-status" :class="`task-status--${item.status}`">{{ itemStatusLabel(item.status) }}</span>
                <small v-if="item.error_summary" class="story-item__error">{{ item.error_summary }}</small>
              </div>
            </div>
          </div>

          <footer class="variant-actions">
            <button
              class="button button--light"
              type="button"
              :disabled="!itemStats.failed || store.busy"
              @click="retryFailed"
            >仅重试失败成片</button>
            <button class="button button--primary" type="button" @click="openOutput">打开交付目录</button>
          </footer>
        </div>

        <div v-else class="empty-script">
          <p>配置批次后提交，整剧主线成片会逐条出现在这里，单项失败不影响其他成片。</p>
        </div>
      </article>
    </div>

    <p v-if="message" class="workflow-message" role="status">{{ message }}</p>
    <p v-if="store.error" class="workflow-error" role="alert">{{ store.error }}</p>
  </section>
</template>
