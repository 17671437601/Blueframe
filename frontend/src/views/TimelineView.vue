<script setup lang="ts">
import { computed, onMounted, ref } from "vue";

import type { EditPlan, EditSegment } from "../api/client";
import { useTimelineStore } from "../stores/timeline";

const props = withDefaults(defineProps<{
  projectId: string; plan?: EditPlan | null;
  save?: (projectId: string, draft: { title: string; kind: EditPlan["kind"]; target_duration_ms: number; segments: EditSegment[] }) => Promise<unknown>;
  render?: (projectId: string, planId: string) => Promise<unknown>;
  refresh?: (projectId: string) => Promise<unknown>;
  openOutput?: (projectId: string) => Promise<unknown>;
}>(), { plan: null, save: undefined, render: undefined, refresh: undefined, openOutput: undefined });

const store = props.save ? null : useTimelineStore();
const clone = <T>(value: T): T => JSON.parse(JSON.stringify(value)) as T;
const localPlan = ref<EditPlan | null>(props.plan ? clone(props.plan) : null);
const history = ref<EditSegment[][]>([]);
const dragging = ref<number | null>(null);
const activePlan = computed(() => localPlan.value ?? store?.plans[0] ?? null);
const segments = computed(() => activePlan.value?.segments ?? []);
const duration = computed(() => segments.value.reduce((total, item) => total + item.source_end_ms - item.source_start_ms, 0));
const renderJob = computed(() => store?.jobs.find((job) => job.payload?.plan_id === activePlan.value?.id));

onMounted(async () => {
  if (props.refresh) await props.refresh(props.projectId); else await store!.refresh(props.projectId);
  if (!localPlan.value && store?.plans[0]) localPlan.value = clone(store.plans[0]);
});
function snapshot() { history.value.push(clone(segments.value)); }
function move(index: number, direction: number) { const target = index + direction; if (target < 0 || target >= segments.value.length) return; snapshot(); const list = segments.value; [list[index], list[target]] = [list[target], list[index]]; }
function undo() { const previous = history.value.pop(); if (previous && activePlan.value) activePlan.value.segments = previous; }
function drop(index: number) { if (dragging.value === null || dragging.value === index) return; snapshot(); const [item] = segments.value.splice(dragging.value, 1); segments.value.splice(index, 0, item); dragging.value = null; }
async function save() { const plan = activePlan.value; if (!plan) return; await (props.save ? props.save(props.projectId, plan) : store!.save(props.projectId, plan)); }
async function render() { const plan = activePlan.value; if (!plan?.id) return; await (props.render ? props.render(props.projectId, plan.id) : store!.render(props.projectId, plan.id)); }
async function openOutput() { await (props.openOutput ? props.openOutput(props.projectId) : store!.openOutput(props.projectId)); }
</script>

<template>
  <section class="timeline-workspace">
    <header class="wizard-heading"><div><p class="eyebrow">EDIT DECISION LIST</p><h2>高光与重组编辑器</h2><p>拖动排序、调整入出点，然后渲染可交付成片。</p></div><span class="step-count">{{ (duration / 1000).toFixed(1) }} 秒</span></header>
    <div v-if="activePlan" class="timeline-layout">
      <article class="panel preview-panel"><header><h3>预览</h3><span>{{ activePlan.title }} · v{{ activePlan.version }}</span></header><div class="preview-stage"><span>▶</span><p>选择片段后生成本地预览</p></div><div class="render-status"><b>{{ renderJob?.status || "尚未渲染" }}</b><small v-if="renderJob">{{ Math.round(renderJob.progress) }}%</small></div></article>
      <article class="panel timeline-panel"><header><h3>时间线片段</h3><button data-testid="undo" :disabled="!history.length" @click="undo">撤销</button></header><div class="timeline-list"><div v-for="(segment, index) in segments" :key="`${segment.source_id}-${index}`" data-segment draggable="true" @dragstart="dragging = index" @dragover.prevent @drop="drop(index)"><span class="drag-handle">⋮⋮</span><b>{{ segment.source_id }}</b><label>入点<input v-model.number="segment.source_start_ms" type="number" min="0" @focus="snapshot" /></label><label>出点<input v-model.number="segment.source_end_ms" type="number" :max="segment.source_duration_ms" @focus="snapshot" /></label><small>{{ ((segment.source_end_ms - segment.source_start_ms) / 1000).toFixed(1) }}s</small><button :data-testid="`move-down-${index}`" @click="move(index, 1)">↓</button></div></div></article>
    </div>
    <div v-else class="placeholder-panel"><span class="placeholder-icon">✂</span><h2>还没有剪辑方案</h2><p>先在剧情分析中接受一个候选方案。</p></div>
    <footer v-if="activePlan" class="wizard-actions"><button class="button button--light" data-testid="open-output" @click="openOutput">打开交付目录</button><button class="button button--light" data-testid="save-plan" @click="save">保存新版本</button><button class="button button--primary" data-testid="render-plan" @click="render">渲染成片</button></footer>
  </section>
</template>
