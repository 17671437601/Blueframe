/// <reference types="vite/client" />

declare global {
  interface Window {
    __BLUEFRAME_BOOTSTRAP__?: {
      apiBaseUrl: string;
      sessionToken: string;
    };
    pywebview?: {
      api: {
        get_bootstrap(): Promise<{ apiBaseUrl: string; sessionToken: string }>;
      };
    };
  }
}

export {};
