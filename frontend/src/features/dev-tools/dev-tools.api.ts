import { api, unwrap } from "@/shared/api";

export const devToolsApi = {
  /** Back to the start of the demo (`POST /dev/reset`, only when the API runs with dev tools on). */
  resetDemo: () => unwrap(api.POST("/dev/reset")),
};
