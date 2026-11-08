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
        select_media_files(): Promise<{ rootId: string | null; files: string[] }>;
      };
    };
  }
}

export {};
