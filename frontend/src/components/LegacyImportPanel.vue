<script setup lang="ts">
import { ref } from "vue";
import { useLegacyImportStore } from "../stores/legacyImport";

const store = useLegacyImportStore();
const rootId = ref(""); const relativePath = ref(""); const confirmed = ref(false);
const message = ref("");

async function choose() {
  if (!window.pywebview?.api?.select_legacy_database) { message.value = "请在 Native 桌面窗口中选择旧版 video.db"; return; }
  const selected = await window.pywebview.api.select_legacy_database();
  rootId.value = selected.rootId || ""; relativePath.value = selected.file || "";
  confirmed.value = false; message.value = "";
  if (rootId.value && relativePath.value) await store.preview(rootId.value, relativePath.value);
}

async function importProjects() {
  if (!confirmed.value) return;
  const result = await store.confirm(rootId.value, relativePath.value);
  message.value = `已导入 ${result.imported} 个项目，跳过 ${result.skipped} 个已导入项目`;
}
</script>

<template>
  <section class="settings-card legacy-import-card">
    <div class="provider-heading"><span>迁</span><div><h3>旧版项目迁移</h3><p>只读扫描旧版 video.db，凭据、Cookie 和账号数据永不导入</p></div></div>
    <button class="button button--light" type="button" data-testid="legacy-choose" :disabled="store.busy" @click="choose">选择并预览旧版数据库</button>
    <div v-if="store.report" class="legacy-preview">
      <p><b>可迁移项目：{{ store.report.projects.length }}</b> · 迁移规则 {{ store.report.migration_version }}</p>
      <ul><li v-for="project in store.report.projects" :key="`${project.legacy_table}:${project.legacy_id}`">{{ project.name }} · {{ project.project_type }} · {{ project.source_available ? "源文件可用" : "源文件缺失" }}</li></ul>
      <p v-if="store.report.excluded_tables.length" class="privacy-note">已排除敏感表：{{ store.report.excluded_tables.join("、") }}</p>
      <p v-for="warning in store.report.warnings" :key="warning" class="workflow-error">{{ warning }}</p>
      <label class="consent-row"><input v-model="confirmed" type="checkbox" /><span><b>我已核对预览并确认迁移</b><small>迁移只会写入蓝帧新数据库，不会修改旧数据库。</small></span></label>
      <div class="wizard-actions"><button class="button button--primary" type="button" :disabled="store.busy || !confirmed" @click="importProjects">{{ store.busy ? "处理中…" : "确认导入" }}</button></div>
    </div>
    <p v-if="message" class="workflow-message">{{ message }}</p><p v-if="store.error" class="workflow-error">{{ store.error }}</p>
  </section>
</template>
