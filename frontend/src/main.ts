import { createApp } from "vue";

import App from "./App.vue";
import { createApiClient } from "./api/client";
import { router } from "./router";
import { configureSystemStore } from "./stores/system";
import { configureProjectStore } from "./stores/projects";
import "./styles/tokens.css";
import "./styles/base.css";

async function resolveBootstrap() {
  if (window.__BLUEFRAME_BOOTSTRAP__) return window.__BLUEFRAME_BOOTSTRAP__;
  if (window.location.protocol === "file:" && !window.pywebview?.api) {
    await new Promise<void>((resolve) =>
      window.addEventListener("pywebviewready", () => resolve(), { once: true }),
    );
  }
  if (window.pywebview?.api) return window.pywebview.api.get_bootstrap();
  return { apiBaseUrl: window.location.origin, sessionToken: "development-session-token" };
}

const bootstrap = await resolveBootstrap();
const system = configureSystemStore(createApiClient(bootstrap.apiBaseUrl, bootstrap.sessionToken));
configureProjectStore(createApiClient(bootstrap.apiBaseUrl, bootstrap.sessionToken));

createApp(App).use(router).mount("#app");
void system.refresh();
