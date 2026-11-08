import { createApp } from "vue";

import App from "./App.vue";
import { createApiClient } from "./api/client";
import { router } from "./router";
import { configureSystemStore } from "./stores/system";
import { configureProjectStore } from "./stores/projects";
import { configureProviderSettingsStore } from "./stores/providerSettings";
import { configureAnalysisStore } from "./stores/analysis";
import { configureTimelineStore } from "./stores/timeline";
import { configureTtsSettingsStore } from "./stores/ttsSettings";
import { configureMovieStore } from "./stores/movie";
import { configureAssetStore } from "./stores/assets";
import { configureVariantStore } from "./stores/variants";
import { configureLiveStore } from "./stores/live";
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
configureProviderSettingsStore(createApiClient(bootstrap.apiBaseUrl, bootstrap.sessionToken));
configureAnalysisStore(createApiClient(bootstrap.apiBaseUrl, bootstrap.sessionToken));
configureTimelineStore(createApiClient(bootstrap.apiBaseUrl, bootstrap.sessionToken));
configureTtsSettingsStore(createApiClient(bootstrap.apiBaseUrl, bootstrap.sessionToken));
configureMovieStore(createApiClient(bootstrap.apiBaseUrl, bootstrap.sessionToken));
configureAssetStore(createApiClient(bootstrap.apiBaseUrl, bootstrap.sessionToken));
configureVariantStore(createApiClient(bootstrap.apiBaseUrl, bootstrap.sessionToken));
configureLiveStore(createApiClient(bootstrap.apiBaseUrl, bootstrap.sessionToken));

createApp(App).use(router).mount("#app");
void system.refresh();
