const PROJECT_TYPES: Record<string, string> = {
  drama: "短剧",
  movie: "影视解说",
  variants: "视频变体",
  live: "直播切片",
};

const PROJECT_STATUSES: Record<string, string> = {
  draft: "草稿",
  ready: "就绪",
  processing: "处理中",
  completed: "已完成",
  failed: "失败",
  archived: "已归档",
};

const JOB_TYPES: Record<string, string> = {
  transcribe_project: "本地识别",
  analyze_project: "剧情分析",
  render_edit_plan: "成片渲染",
  generate_commentary: "解说生成",
  synthesize_commentary: "配音字幕",
  render_variant_batch: "变体渲染",
  render_highlights: "高光切片",
  process_live_segment: "直播分段处理",
};

const JOB_STATUSES: Record<string, string> = {
  queued: "排队中",
  running: "运行中",
  pausing: "暂停中",
  paused: "已暂停",
  cancelling: "取消中",
  cancelled: "已取消",
  completed: "已完成",
  failed: "失败",
  interrupted: "已中断",
};

const JOB_STAGES: Record<string, string> = {
  extract_audio: "提取音频",
  recognize: "语音识别",
  asr_no_audio: "无音轨",
  asr_completed: "识别完成",
  transcribe_project: "本地识别",
  analyze_story: "剧情分析",
  generate_commentary: "解说生成",
  synthesize_commentary: "配音合成",
  align_commentary: "字幕对齐",
  render_media: "渲染成片",
  publish_media: "写入交付",
  render_variants: "批量变体",
  render_highlights: "高光切片渲染",
  process_live_segment: "直播分段处理",
};

function lookup(labels: Record<string, string>, value: string | null | undefined, fallback: string): string {
  if (!value) return fallback;
  return labels[value] ?? value;
}

export function projectTypeLabel(value: string): string {
  return lookup(PROJECT_TYPES, value, "项目");
}

export function projectStatusLabel(value: string): string {
  return lookup(PROJECT_STATUSES, value, value);
}

export function jobTypeLabel(value: string): string {
  return lookup(JOB_TYPES, value, value);
}

export function jobStatusLabel(value: string): string {
  return lookup(JOB_STATUSES, value, value);
}

export function stageLabel(value: string | null | undefined): string {
  return lookup(JOB_STAGES, value, "");
}

export function formatDateTime(value: string | null | undefined): string {
  if (!value) return "—";
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return "—";
  const now = new Date();
  const sameYear = date.getFullYear() === now.getFullYear();
  const parts = new Intl.DateTimeFormat("zh-CN", {
    ...(sameYear ? {} : { year: "numeric" }),
    month: "2-digit",
    day: "2-digit",
    hour: "2-digit",
    minute: "2-digit",
    hour12: false,
  }).format(date);
  return parts.replace(/\//g, "-");
}

export function isWithinDays(value: string | null | undefined, days: number): boolean {
  if (!value) return false;
  const timestamp = new Date(value).getTime();
  if (Number.isNaN(timestamp)) return false;
  return Date.now() - timestamp <= days * 24 * 60 * 60 * 1000;
}
