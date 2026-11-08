<script setup lang="ts">
import { computed, ref } from "vue";

import { useProjectStore } from "../stores/projects";

const projects = useProjectStore();
const step = ref(0);
const name = ref("");
const rootId = ref("");
const files = ref<string[]>([]);
const targetSeconds = ref(480);
const explosionThreshold = ref(72);
const highlightCount = ref(10);
const remixCount = ref(10);
const commentaryCount = ref(0);
const message = ref("");

const steps = ["导入素材", "智能分析", "生产配置", "确认启动"];
const canContinue = computed(() => step.value > 0 || (name.value.trim() && files.value.length > 0));

async function chooseMedia() {
  if (!window.pywebview?.api?.select_media_files) {
    message.value = "请在 Native 桌面窗口中选择素材";
    return;
  }
  const selection = await window.pywebview.api.select_media_files();
  if (selection.rootId) {
    rootId.value = selection.rootId;
    files.value = selection.files;
    if (!name.value && files.value[0]) name.value = files.value[0].replace(/\.[^.]+$/, "");
  }
}

async function startProject() {
  const project = await projects.createFromSelection({
    name: name.value.trim(),
    projectType: "drama",
    rootId: rootId.value,
    files: files.value,
    config: {
      target_seconds: targetSeconds.value,
      explosion_threshold: explosionThreshold.value,
      highlight_count: highlightCount.value,
      remix_count: remixCount.value,
      commentary_count: commentaryCount.value,
    },
  });
  message.value = `项目已创建：${project.name}，正在进行本地识别`;
}
</script>

<template>
  <section class="drama-workspace">
    <header class="wizard-heading">
      <div><p class="eyebrow">DRAMA PRODUCTION</p><h2>创建短剧项目</h2><p>导入多集素材，配置分析与成片目标，然后启动本地处理。</p></div>
      <span class="step-count">{{ step + 1 }} / 4</span>
    </header>
    <ol class="wizard-steps" aria-label="创建步骤">
      <li v-for="(label, index) in steps" :key="label" :class="{ active: index === step, done: index < step }">
        <span>{{ index < step ? "✓" : index + 1 }}</span><b>{{ label }}</b>
      </li>
    </ol>

    <div class="wizard-panel">
      <div v-if="step === 0" class="wizard-section">
        <div class="field"><label for="project-name">项目名称</label><input id="project-name" v-model="name" name="project-name" placeholder="例如：都市悬疑 第一季" /></div>
        <button class="media-dropzone" data-testid="choose-media" type="button" @click="chooseMedia">
          <span class="dropzone-icon">＋</span><strong>选择单集或多集视频</strong><small>支持 MP4、MOV、MKV、AVI；文件不会上传云端</small>
        </button>
        <ul v-if="files.length" class="selected-files"><li v-for="(file, index) in files" :key="file"><span>{{ index + 1 }}</span><b>{{ file }}</b><em>等待探测</em></li></ul>
      </div>

      <div v-else-if="step === 1" class="wizard-section">
        <h3>智能分析设置</h3><p class="section-help">本地 ASR 完成后，仅转写文本会发送给已配置的 AI 服务。</p>
        <div class="settings-grid">
          <label>爆点评分门槛<input v-model.number="explosionThreshold" type="number" min="0" max="100" /></label>
          <label>目标成片时长（秒）<input v-model.number="targetSeconds" type="number" min="7" max="720" /></label>
        </div>
        <details><summary>高级 AI 与 EDL 设置</summary><p>关键帧视觉理解默认关闭；时间线最小片段和相似度将在分析后校验。</p></details>
      </div>

      <div v-else-if="step === 2" class="wizard-section">
        <h3>生产配置</h3><p class="section-help">分别设置高光、剧情重组和解说方案数量。</p>
        <div class="production-cards">
          <label><span>高光成片</span><input v-model.number="highlightCount" type="number" min="0" max="50" /></label>
          <label><span>剧情重组</span><input v-model.number="remixCount" type="number" min="0" max="50" /></label>
          <label><span>解说成片</span><input v-model.number="commentaryCount" type="number" min="0" max="20" /></label>
        </div>
      </div>

      <div v-else class="wizard-section review-section">
        <h3>确认并启动</h3>
        <dl><div><dt>项目</dt><dd>{{ name }}</dd></div><div><dt>素材</dt><dd>{{ files.length }} 集</dd></div><div><dt>目标时长</dt><dd>{{ targetSeconds }} 秒</dd></div><div><dt>方案</dt><dd>高光 {{ highlightCount }} / 重组 {{ remixCount }} / 解说 {{ commentaryCount }}</dd></div></dl>
        <p class="privacy-note">素材、音频和本地识别缓存保留在电脑中。远程 AI 尚未配置时，任务会停在“等待服务配置”。</p>
      </div>
    </div>

    <footer class="wizard-actions">
      <button v-if="step > 0" class="button button--light" type="button" @click="step -= 1">上一步</button>
      <button v-if="step < 3" class="button button--primary" data-testid="next-step" type="button" :disabled="!canContinue" @click="step += 1">下一步</button>
      <button v-else class="button button--primary" data-testid="start-project" type="button" :disabled="projects.busy" @click="startProject">{{ projects.busy ? "正在创建…" : "确认并启动" }}</button>
    </footer>
    <p v-if="message" class="workflow-message" role="status">{{ message }}</p>
    <p v-if="projects.error" class="workflow-error" role="alert">{{ projects.error }}</p>
  </section>
</template>
