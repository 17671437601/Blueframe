import { createApp } from "vue";

import App from "./App.vue";
import { createApiClient } from "./api/client";
import { router } from "./router";
import { configureSystemStore } from "./stores/system";
import "./styles/tokens.css";
import "./styles/base.css";

const bootstrap = window.__BLUEFRAME_BOOTSTRAP__ ?? {
  apiBaseUrl: window.location.origin,
  sessionToken: "development-session-token",
};
const system = configureSystemStore(createApiClient(bootstrap.apiBaseUrl, bootstrap.sessionToken));

createApp(App).use(router).mount("#app");
void system.refresh();
