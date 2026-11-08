<script setup lang="ts">
import { computed, onMounted, ref } from "vue";
import { useAssetStore } from "../stores/assets";

const assets = useAssetStore();
const rootId = ref(""); const files = ref<string[]>([]);
const origin = ref(""); const licenseName = ref(""); const filter = ref("");
const message = ref("");
const visible = computed(() => filter.value ? assets.assets.filter((asset) => asset.asset_type === filter.value) : assets.assets);
onMounted(() => assets.refresh());

async function choose() {
  if (!window.pywebview?.api?.select_media_files) { message.value = "请在 Native 桌面窗口中选择素材"; return; }
  const selection = await window.pywebview.api.select_media_files();
  rootId.value = selection.rootId || ""; files.value = selection.files || [];
}
async function importSelected() {
  await assets.import({ root_id: rootId.value, relative_paths: files.value, origin: origin.value, license_name: licenseName.value, ownership: "linked" });
  message.value = `已登记 ${files.value.length - assets.importErrors.length} 个授权素材`;
  files.value = []; rootId.value = "";
}
</script>

<template>
  <section class="assets-workspace">
    <header class="wizard-heading"><div><p class="eyebrow">ASSET CENTER</p><h2>授权素材中心</h2><p>按内容指纹管理本地视频、音频、图片与字体，并保留来源和授权记录。</p></div><span class="step-count">{{ assets.assets.length }} 项</span></header>
    <div class="assets-grid">
      <article class="panel asset-import"><header><h3>登记本地素材</h3></header><div class="movie-card-body">
        <button class="media-dropzone" data-testid="asset-choose" type="button" @click="choose"><span class="dropzone-icon">＋</span><strong>选择素材文件</strong><small>视频 / 音频 / 图片 / 字体</small></button>
        <p v-if="files.length" class="asset-selection">已选择 {{ files.length }} 个文件</p>
        <label class="field">素材来源<input v-model.trim="origin" placeholder="例如：品牌自有拍摄" /></label>
        <label class="field">授权或许可证<input v-model.trim="licenseName" placeholder="例如：版权所有者授权 / CC-BY" /></label>
        <button class="button button--primary" :disabled="assets.busy || !files.length || !origin || !licenseName" @click="importSelected">{{ assets.busy ? "校验中…" : "校验并登记" }}</button>
        <p class="privacy-note">登记不会复制或删除原文件；移动原文件后会明确标记为“不可用”。</p>
      </div></article>
      <article class="panel asset-library"><header><h3>素材库</h3><select v-model="filter"><option value="">全部类型</option><option value="video">视频</option><option value="audio">音频</option><option value="image">图片</option><option value="font">字体</option></select></header>
        <div class="asset-list"><div v-for="asset in visible" :key="asset.id" :class="{ unavailable: !asset.available }"><span class="asset-kind">{{ asset.asset_type.slice(0, 1).toUpperCase() }}</span><div><b>{{ asset.filename }}</b><small>{{ asset.origin }} · {{ asset.license_name }}</small><code>{{ asset.sha256.slice(0, 12) }}</code></div><em>{{ asset.available ? "可用" : "文件已移动" }}</em></div><p v-if="!visible.length">还没有登记素材</p></div>
      </article>
    </div>
    <p v-if="message" class="workflow-message">{{ message }}</p><p v-if="assets.error" class="workflow-error">{{ assets.error }}</p><p v-for="error in assets.importErrors" :key="error.relative_path" class="workflow-error">{{ error.relative_path }}：{{ error.message }}</p>
  </section>
</template>
