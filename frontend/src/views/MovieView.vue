<script setup lang="ts">
import { computed, onMounted, ref } from "vue";
import { useRoute, useRouter } from "vue-router";

import { useMovieStore } from "../stores/movie";
import { useProjectStore } from "../stores/projects";

const route = useRoute();
const router = useRouter();
const movie = useMovieStore();
const projects = useProjectStore();
const projectId = computed(() => String(route.params.projectId || ""));
const name = ref("");
const rootId = ref("");
const files = ref<string[]>([]);
const voice = ref("zh_female_vv_uranus_bigtts");
const consent = ref(false);
const title = ref("");
const sentenceTexts = ref<string[]>([]);
const message = ref("");

const currentScript = computed(() => movie.scripts[0] || null);
const currentPlan = computed(() => movie.plans[0] || null);

function loadDraft() {
  if (!currentScript.value) return;
  title.value = currentScript.value.title;
  voice.value = currentScript.value.voice;
  sentenceTexts.value = currentScript.value.sentences.map((sentence) => sentence.text);
}

async function refresh() {
  if (!projectId.value) return;
  await movie.refresh(projectId.value); loadDraft();
}

onMounted(refresh);

async function chooseMedia() {
  if (!window.pywebview?.api?.select_media_files) { message.value = "请在 Native 桌面窗口中选择影片"; return; }
  const selection = await window.pywebview.api.select_media_files();
  rootId.value = selection.rootId || ""; files.value = selection.files || [];
  if (!name.value && files.value[0]) name.value = files.value[0].replace(/\.[^.]+$/, "");
}

async function createProject() {
  const project = await projects.createFromSelection({
    name: name.value.trim(), projectType: "movie", rootId: rootId.value, files: files.value,
    config: { output_width: 1080, output_height: 1920, output_fps: 30 },
  });
  await router.push(`/movie/${project.id}`);
  await refresh();
}

async function generate() {
  if (!consent.value) { message.value = "请先确认仅发送字幕文本给远程 AI"; return; }
  await movie.generate(projectId.value, voice.value);
  message.value = "解说脚本任务已进入队列，完成后点击刷新";
}

async function saveScript() {
  if (!currentScript.value) return;
  const saved = await movie.save(projectId.value, currentScript.value, title.value, voice.value, sentenceTexts.value);
  title.value = saved.title; sentenceTexts.value = saved.sentences.map((sentence) => sentence.text);
  message.value = `已保存人工修订版本 v${saved.version}`;
}

async function synthesize() {
  if (!currentScript.value) return;
  await movie.synthesize(projectId.value, currentScript.value.id);
  message.value = "配音与字幕任务已进入队列";
}

async function ensurePlan() {
  await movie.createFullLengthPlan(projectId.value); message.value = "已创建全片解说剪辑方案";
}

async function render() {
  if (!currentScript.value || !currentPlan.value) return;
  await movie.render(projectId.value, currentPlan.value.id, currentScript.value.id);
  message.value = "成片渲染已进入队列，可在任务状态中查看进度";
}
</script>

<template>
  <section v-if="!projectId" class="movie-workspace movie-import">
    <header class="wizard-heading"><div><p class="eyebrow">MOVIE COMMENTARY</p><h2>创建影视解说项目</h2><p>本地识别原片，远程 AI 只处理字幕文本，配音与成片在本机生成。</p></div><span class="step-count">Native</span></header>
    <div class="wizard-panel">
      <label class="field">项目名称<input v-model="name" name="movie-name" placeholder="例如：悬疑电影解说" /></label>
      <button class="media-dropzone" data-testid="movie-choose-media" type="button" @click="chooseMedia"><span class="dropzone-icon">＋</span><strong>选择一部或多段影片</strong><small>支持 MP4、MOV、MKV、AVI；原片不会上传</small></button>
      <ul v-if="files.length" class="selected-files"><li v-for="file in files" :key="file"><span>影</span><b>{{ file }}</b><em>本地处理</em></li></ul>
      <div class="wizard-actions"><button class="button button--primary" :disabled="!name.trim() || !files.length || projects.busy" @click="createProject">{{ projects.busy ? "创建中…" : "创建并开始识别" }}</button></div>
    </div>
    <p v-if="message" class="workflow-message">{{ message }}</p><p v-if="projects.error" class="workflow-error">{{ projects.error }}</p>
  </section>

  <section v-else class="movie-workspace">
    <header class="wizard-heading"><div><p class="eyebrow">MOVIE COMMENTARY</p><h2>{{ movie.project?.name || "影视解说工作台" }}</h2><p>从字幕事实生成解说，人工确认后再配音和渲染。</p></div><button class="button button--light" data-testid="movie-refresh" @click="refresh">刷新状态</button></header>
    <div class="movie-pipeline" aria-label="影视解说流程"><span class="active">1 本地识别</span><span>2 解说脚本</span><span>3 配音字幕</span><span>4 成片渲染</span></div>
    <div class="movie-grid">
      <article class="panel movie-control">
        <header><h3>生成设置</h3><small>{{ movie.project?.sources?.length || 0 }} 个素材</small></header>
        <div class="movie-card-body">
          <label class="field">火山音色<input v-model="voice" name="movie-voice" /></label>
          <label class="consent-row"><input v-model="consent" type="checkbox" /><span><b>允许发送字幕文本</b><small>不发送原片、音频或本地路径</small></span></label>
          <button class="button button--primary" data-testid="generate-commentary" :disabled="movie.busy" @click="generate">生成事实可追溯解说</button>
          <button class="button button--light" :disabled="movie.busy" @click="ensurePlan">创建全片剪辑方案</button>
        </div>
      </article>

      <article class="panel script-editor">
        <header><div><h3>解说脚本</h3><small v-if="currentScript">版本 v{{ currentScript.version }} · {{ currentScript.provider }}</small></div><button type="button" @click="sentenceTexts.push('')">＋ 添加一句</button></header>
        <div v-if="currentScript" class="movie-card-body">
          <div class="settings-grid"><label>标题<input v-model="title" /></label><label>音色<input v-model="voice" /></label></div>
          <ol class="script-lines"><li v-for="(_text, index) in sentenceTexts" :key="index"><b>{{ index + 1 }}</b><textarea v-model="sentenceTexts[index]" rows="2" /><button aria-label="删除句子" @click="sentenceTexts.splice(index, 1)">×</button></li></ol>
          <div class="wizard-actions"><button class="button button--light" :disabled="movie.busy" @click="saveScript">保存新版本</button><button class="button button--primary" :disabled="movie.busy || !sentenceTexts.length" @click="synthesize">生成配音与字幕</button></div>
        </div>
        <div v-else class="empty-script"><p>识别完成后生成解说稿；无对白影片也可点击“添加一句”人工编写。</p></div>
      </article>
    </div>

    <article class="panel movie-delivery"><header><h3>交付与任务</h3><button class="button button--primary" :disabled="movie.busy || !currentScript || !currentPlan" data-testid="render-commentary" @click="render">渲染解说成片</button></header><div class="job-strip"><span v-if="!movie.jobs.length">暂无任务</span><span v-for="job in movie.jobs" :key="job.id"><b>{{ job.job_type }}</b> {{ job.status }} · {{ Math.round(job.progress) }}%</span></div></article>
    <p v-if="message" class="workflow-message">{{ message }}</p><p v-if="movie.error" class="workflow-error">{{ movie.error }}</p>
  </section>
</template>
