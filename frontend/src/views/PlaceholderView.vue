<script setup lang="ts">
import { useRoute } from "vue-router";
const route = useRoute();
</script>

<template>
  <section class="placeholder-panel">
    <div class="placeholder-icon">◇</div>
    <p class="eyebrow">{{ route.meta.eyebrow }}</p>
    <h2>{{ route.meta.fullTitle || route.meta.title }}</h2>
    <p>基础框架已就绪，业务模块将在后续里程碑中接入。</p>
  </section>
</template>
