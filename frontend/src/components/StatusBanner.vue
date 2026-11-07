<script setup lang="ts">
const props = defineProps<{
  kind: "none" | "offline" | "grace" | "readonly" | "degraded";
  graceRemainingSeconds: number | null;
  refreshing?: boolean;
}>();

defineEmits<{ retry: [] }>();

function graceText(): string {
  const seconds = props.graceRemainingSeconds ?? 0;
  const hours = Math.floor(seconds / 3600);
  const minutes = Math.floor((seconds % 3600) / 60);
  return `${hours} 小时 ${minutes} 分钟`;
}
</script>

<template>
  <aside v-if="kind !== 'none'" class="status-banner" :class="`status-banner--${kind}`" role="status">
    <div>
      <strong v-if="kind === 'offline'">本地服务暂时离线</strong>
      <strong v-else-if="kind === 'readonly'">当前为只读模式</strong>
      <strong v-else-if="kind === 'grace'">账号处于离线宽限期</strong>
      <strong v-else>部分服务暂不可用</strong>
      <span v-if="kind === 'offline'">工作区仍可浏览，恢复连接后即可继续处理。</span>
      <span v-else-if="kind === 'readonly'">可以查看项目和导出，新的处理任务已暂停。</span>
      <span v-else-if="kind === 'grace'">剩余 {{ graceText() }}，请在联网后刷新授权。</span>
      <span v-else>已保留最近一次安全状态，你可以稍后重试。</span>
    </div>
    <button v-if="kind === 'offline' || kind === 'degraded'" data-testid="retry" type="button" :disabled="refreshing" @click="$emit('retry')">
      {{ refreshing ? "连接中…" : "重试连接" }}
    </button>
  </aside>
</template>
