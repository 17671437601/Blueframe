<script setup lang="ts">
import { onMounted } from "vue";
import { useDiagnosticsStore } from "../stores/diagnostics";
const diagnostics = useDiagnosticsStore();
onMounted(() => diagnostics.load());
</script>

<template>
  <section class="settings-card">
    <div class="provider-heading"><span>诊</span><div><h3>隐私诊断</h3><p>导出阶段指标、任务状态和系统版本，供故障排查使用</p></div></div>
    <div class="diagnostic-metrics"><span><b>{{ diagnostics.summary.job_count }}</b>任务</span><span><b>{{ diagnostics.summary.failed_jobs }}</b>失败</span><span><b>{{ diagnostics.summary.metric_count }}</b>指标</span></div>
    <p class="privacy-note">诊断包默认不包含视频、音频、字幕、任务参数、绝对路径、账号资料、Cookie、Token 或 API Key。</p>
    <div class="wizard-actions"><button class="button button--primary" type="button" :disabled="diagnostics.busy" @click="diagnostics.export">{{ diagnostics.busy ? "导出中…" : "导出安全诊断包" }}</button></div>
    <p v-if="diagnostics.filename" class="workflow-message">已保存到本地诊断目录：{{ diagnostics.filename }}</p><p v-if="diagnostics.error" class="workflow-error">{{ diagnostics.error }}</p>
  </section>
</template>
