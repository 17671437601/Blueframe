/// <reference types="vite/client" />

declare global {
  interface Window {
    __BLUEFRAME_BOOTSTRAP__?: {
      apiBaseUrl: string;
      sessionToken: string;
    };
  }
}

export {};
