<script setup lang="ts">
import { computed, onMounted, ref } from "vue";
import { useRoute, useRouter } from "vue-router";
import { useProjectStore } from "../stores/projects";
import { useVariantStore } from "../stores/variants";

const route = useRoute(), router = useRouter();
const projects = useProjectStore(), variants = useVariantStore();
const projectId = computed(() => String(route.params.projectId || ""));
const name = ref(""); const rootId = ref(""); const files = ref<string[]>([]);
const count = ref(5); const seed = ref(2026); const width = ref(1080); const height = ref(1920); const overlay = ref("");
const selectedBatchId = ref(""); const message = ref("");
const selectedBatch = computed(() => variants.batches.find((batch) => batch.id === selectedBatchId.value) || variants.batches[0] || null);

async function refresh() { if (!projectId.value) return; await variants.refresh(projectId.value); if (!selectedBatchId.value && variants.batches[0]) selectedBatchId.value = variants.batches[0].id; }
onMounted(refresh);
async function choose() {
  if (!window.pywebview?.api?.select_media_files) { message.value = "请在 Native 桌面窗口中选择主成片"; return; }
  const selection = await window.pywebview.api.select_media_files(); rootId.value = selection.rootId || ""; files.value = selection.files || [];
  if (!name.value && files.value[0]) name.value = `${files.value[0].replace(/\.[^.]+$/, "")}-变体`;
}
async function createProject() {
  const project = await projects.createFromSelection({ name: name.value, projectType: "variants", rootId: rootId.value, files: files.value, config: {} });
  await router.push(`/variants/${project.id}`); await refresh();
}
async function startBatch() {
  const source = variants.project?.sources?.[0]; if (!source) { message.value = "主成片尚未就绪，请刷新"; return; }
  const result = await variants.create(projectId.value, {
    source_id: source.id, count: count.value, seed: seed.value, width: width.value, height: height.value,
    ...(overlay.value ? { overlay_asset_id: overlay.value } : {}), idempotency_key: `variant:${crypto.randomUUID()}`,
  });
  selectedBatchId.value = result.batch.id; message.value = "批量变体任务已进入队列";
}
async function retry() { if (!selectedBatch.value) return; await variants.retry(projectId.value, selectedBatch.value.id); message.value = "失败项已重新进入队列"; }
async function openOutput() {
  if (!window.pywebview?.api?.open_project_output) { message.value = "请在 Native 桌面窗口中打开交付目录"; return; }
  await window.pywebview.api.open_project_output(projectId.value);
}
</script>

<template>
  <section v-if="!projectId" class="variants-workspace variant-import">
    <header class="wizard-heading"><div><p class="eyebrow">VIDEO VARIANTS</p><h2>创建视频变体项目</h2><p>从已完成的主成片生成可解释、可复现的画幅与素材包装版本。</p></div><span class="step-count">合规包装</span></header>
    <div class="wizard-panel"><label class="field">项目名称<input v-model="name" /></label><button class="media-dropzone" data-testid="variant-choose" @click="choose"><span class="dropzone-icon">＋</span><strong>选择主成片</strong><small>不会改变源文件，也不承诺绕过审核或版权规则</small></button><ul v-if="files.length" class="selected-files"><li v-for="file in files" :key="file"><span>源</span><b>{{ file }}</b><em>等待创建</em></li></ul><div class="wizard-actions"><button class="button button--primary" :disabled="projects.busy || !files.length || !name" @click="createProject">创建变体项目</button></div></div>
    <p v-if="message" class="workflow-message">{{ message }}</p>
  </section>

  <section v-else class="variants-workspace">
    <header class="wizard-heading"><div><p class="eyebrow">VIDEO VARIANTS</p><h2>{{ variants.project?.name || "视频变体" }}</h2><p>相同种子与配方会得到相同的结构化参数；每个输出独立重试。</p></div><button class="button button--light" @click="refresh">刷新状态</button></header>
    <div class="variants-grid">
      <article class="panel variant-config"><header><h3>批量配置</h3></header><div class="movie-card-body">
        <div class="settings-grid"><label>输出数量<input v-model.number="count" type="number" min="1" max="50" /></label><label>确定性种子<input v-model.number="seed" type="number" min="0" /></label><label>宽度<input v-model.number="width" type="number" min="320" step="2" /></label><label>高度<input v-model.number="height" type="number" min="320" step="2" /></label></div>
        <label class="field">授权角标素材<select v-model="overlay"><option value="">不叠加</option><option v-for="asset in variants.overlays" :key="asset.id" :value="asset.id">{{ asset.filename }} · {{ asset.license_name }}</option></select></label>
        <p class="privacy-note">变体仅包含画幅、色彩、速度、音量、码率及已授权角标包装；参数始终可查看。</p>
        <button class="button button--primary" data-testid="start-variants" :disabled="variants.busy" @click="startBatch">生成 {{ count }} 个变体</button>
      </div></article>
      <article class="panel variant-results"><header><h3>输出比较</h3><select v-model="selectedBatchId"><option v-for="batch in variants.batches" :key="batch.id" :value="batch.id">{{ batch.id.slice(0, 8) }} · {{ batch.status }}</option></select></header>
        <div v-if="selectedBatch" class="variant-items"><div v-for="item in selectedBatch.items" :key="item.id" :class="`status-${item.status}`"><div class="variant-preview"><span>{{ item.recipe.width }} × {{ item.recipe.height }}</span><b>V{{ item.item_index + 1 }}</b></div><div><strong>{{ item.output_filename || `变体 ${item.item_index + 1}` }}</strong><small>速度 {{ item.recipe.speed }}× · 饱和 {{ item.recipe.saturation }} · 音量 {{ item.recipe.audio_gain_db }}dB · {{ item.recipe.video_bitrate }}</small><em>{{ item.error_summary || item.status }}</em></div></div></div><div v-else class="empty-script"><p>配置后开始生成，结果会逐项出现在这里。</p></div>
        <footer class="variant-actions"><button class="button button--light" :disabled="!selectedBatch || !selectedBatch.items.some((item) => item.status === 'failed')" @click="retry">仅重试失败项</button><button class="button button--primary" @click="openOutput">打开交付目录</button></footer>
      </article>
    </div>
    <p v-if="message" class="workflow-message">{{ message }}</p><p v-if="variants.error" class="workflow-error">{{ variants.error }}</p>
  </section>
</template>
