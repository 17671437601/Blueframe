<script setup lang="ts">
import { computed, onMounted, ref } from "vue";
import { useRoute, useRouter } from "vue-router";
import { useLiveStore } from "../stores/live";

const route = useRoute(), router = useRouter(), live = useLiveStore();
const projectId = computed(() => String(route.params.projectId || ""));
const name = ref("直播自动切片"); const rootId = ref("");
const displayName = ref(""); const playbackUrl = ref(""); const confirmed = ref(false); const message = ref("");
const active = computed(() => live.sessions.find((session) => session.intent_active) || null);

async function refresh() { if (projectId.value) await live.refresh(projectId.value); }
onMounted(refresh);
async function chooseDirectory() {
  if (!window.pywebview?.api?.select_project_directory) { message.value = "请在 Native 桌面窗口中选择交付目录"; return; }
  const selected = await window.pywebview.api.select_project_directory(); rootId.value = selected.rootId || "";
  if (rootId.value) message.value = "交付目录已授权";
}
async function createProject() { const project = await live.createProject(name.value, rootId.value); await router.push(`/live/${project.id}`); await refresh(); }
async function start() {
  if (!confirmed.value) { message.value = "请先确认录制和处理授权"; return; }
  await live.start(projectId.value, displayName.value, playbackUrl.value, confirmed.value);
  playbackUrl.value = ""; message.value = "录制已启动；播放地址已移入 Windows 凭据管理器";
}
async function stop() { if (!active.value) return; await live.stop(projectId.value, active.value.id); message.value = "录制已安全停止，已完成分段仍会继续处理"; }
async function reconnect() { if (!active.value) return; await live.reconnect(projectId.value, active.value.id); message.value = "已请求重新连接直播源"; }
async function openOutput() { if (window.pywebview?.api?.open_project_output) await window.pywebview.api.open_project_output(projectId.value); else message.value = "请在 Native 桌面窗口中打开交付目录"; }
</script>

<template>
  <section v-if="!projectId" class="live-workspace live-create">
    <header class="wizard-heading"><div><p class="eyebrow">LIVE AUTO CLIP</p><h2>创建直播切片项目</h2><p>录制你已获授权的直播源，本地分段并自动生成可审阅切片。</p></div><span class="step-count">最多 2 路</span></header>
    <div class="wizard-panel"><label class="field">项目名称<input v-model.trim="name" /></label><button class="media-dropzone" data-testid="live-directory" @click="chooseDirectory"><span class="dropzone-icon">⌂</span><strong>选择本地交付目录</strong><small>原始分段、字幕和切片均保存在该目录</small></button><div class="wizard-actions"><button class="button button--primary" :disabled="!rootId || !name || live.busy" @click="createProject">创建直播项目</button></div></div><p v-if="message" class="workflow-message">{{ message }}</p>
  </section>

  <section v-else class="live-workspace">
    <header class="wizard-heading"><div><p class="eyebrow">LIVE AUTO CLIP</p><h2>{{ live.project?.name || "直播自动切片" }}</h2><p>稳定分段会自动进入本地 ASR、智能分析和切片渲染。</p></div><button class="button button--light" @click="refresh">刷新状态</button></header>
    <div class="live-grid">
      <article class="panel live-source"><header><h3>授权直播源</h3><span :class="['live-state', active?.status]">{{ active?.status || "未启动" }}</span></header><div class="movie-card-body">
        <template v-if="!active"><label class="field">显示名称<input v-model.trim="displayName" placeholder="主播或栏目名称" /></label><label class="field">授权播放地址<input v-model="playbackUrl" name="playback-url" type="password" autocomplete="off" placeholder="https://… / rtmp://… / srt://…" /></label><label class="consent-row"><input v-model="confirmed" type="checkbox" /><span><b>我确认已获得录制和处理授权</b><small>本工具不解析抖音页面、不抓取 Cookie、不绕过登录、付费或 DRM</small></span></label><button class="button button--primary" data-testid="start-recording" :disabled="live.busy || !displayName || !playbackUrl" @click="start">开始录制与自动切片</button></template>
        <template v-else><div class="recording-pulse"><i></i><div><b>{{ active.display_name }}</b><small>重连 {{ active.reconnect_count }} 次 · {{ active.segments.length }} 个分段</small></div></div><p v-if="active.error_summary" class="workflow-error">{{ active.error_summary }}</p><div class="live-actions"><button class="button button--light" @click="reconnect">手动重连</button><button class="button live-stop" @click="stop">安全停止</button></div></template>
        <p class="privacy-note">播放地址只保存在 Windows 凭据管理器，不写入项目数据库、日志或前端缓存。</p>
      </div></article>
      <article class="panel live-segments"><header><h3>分段与自动切片</h3><button @click="openOutput">打开交付目录</button></header><div class="segment-list"><template v-for="session in live.sessions" :key="session.id"><div v-for="segment in session.segments" :key="segment.id"><span>{{ String(segment.sequence + 1).padStart(3, '0') }}</span><div><b>{{ segment.filename }}</b><small>{{ Math.round(segment.duration_ms / 1000) }} 秒 · {{ (segment.size_bytes / 1024 / 1024).toFixed(1) }} MB</small></div><em :class="segment.status">{{ segment.status }}</em></div></template><p v-if="!live.sessions.some((session) => session.segments.length)">录制稳定后，分段会出现在这里。</p></div><div class="job-strip"><span v-for="job in live.jobs" :key="job.id"><b>{{ job.job_type }}</b> {{ job.status }} · {{ Math.round(job.progress) }}%</span></div></article>
    </div><p v-if="message" class="workflow-message">{{ message }}</p><p v-if="live.error" class="workflow-error">{{ live.error }}</p>
  </section>
</template>
