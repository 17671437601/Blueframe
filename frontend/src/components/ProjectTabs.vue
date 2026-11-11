<script setup lang="ts">
defineProps<{
  projectId: string;
  active: "analysis" | "highlights" | "story" | "timeline";
}>();
</script>

<template>
  <nav class="project-tabs" aria-label="项目视图">
    <a :href="`#/drama/${projectId}`" :aria-current="active === 'analysis' ? 'page' : undefined">剧情分析</a>
    <a :href="`#/drama/${projectId}/highlights`" :aria-current="active === 'highlights' ? 'page' : undefined">高光切片</a>
    <a :href="`#/drama/${projectId}/story`" :aria-current="active === 'story' ? 'page' : undefined">主线成片</a>
    <a :href="`#/drama/${projectId}/edit`" :aria-current="active === 'timeline' ? 'page' : undefined">成片编辑</a>
  </nav>
</template>
