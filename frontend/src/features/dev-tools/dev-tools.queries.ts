import { useMutation, useQueryClient } from "@tanstack/react-query";
import { devToolsApi } from "./dev-tools.api";

/** Resets the demo; every cached server data is dropped (the caller reloads the page). */
export function useResetDemo() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: devToolsApi.resetDemo,
    onSuccess: () => queryClient.clear(),
  });
}
