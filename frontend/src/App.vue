<script setup lang="ts">
import AppShell from "./layout/AppShell.vue";
import { useSystemStore } from "./stores/system";

const system = useSystemStore();
</script>

<template>
  <AppShell
    :connection="system.connection"
    :account-mode="system.accountMode"
    :grace-remaining-seconds="system.graceRemainingSeconds"
    :running-task-count="system.runningTaskCount"
    :refreshing="system.refreshing"
    @retry="system.refresh()"
  />
</template>
