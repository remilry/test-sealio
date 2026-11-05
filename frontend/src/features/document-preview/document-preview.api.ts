import { ApiError } from "@/shared/api";

/** Original files, read whole (a Word document is rendered in the page, not by the browser). */
export const documentPreviewApi = {
  file: async (fileUrl: string, signal?: AbortSignal): Promise<Blob> => {
    const response = await fetch(fileUrl, { signal });
    if (!response.ok) throw new ApiError(response.status, `Could not load ${fileUrl}`);
    return response.blob();
  },
};
