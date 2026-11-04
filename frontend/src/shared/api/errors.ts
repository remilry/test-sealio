/** An HTTP error from the back, with its status so screens can tell "not found" from "failed". */
export class ApiError extends Error {
  constructor(
    readonly status: number,
    message: string,
  ) {
    super(message);
    this.name = "ApiError";
  }
}

type ApiResult<T> = { data?: T; error?: unknown; response: Response };

/**
 * Turns an openapi-fetch result into its data, or throws an ApiError (for TanStack Query).
 * A success without a body (204 No Content) resolves to undefined: openapi-fetch gives no data.
 */
export async function unwrap<T>(request: Promise<ApiResult<T>>): Promise<T> {
  const { data, error, response } = await request;
  if (error !== undefined || !response.ok) {
    const detail =
      typeof error === "object" && error !== null && "detail" in error
        ? String(error.detail)
        : response.statusText;
    throw new ApiError(response.status, detail);
  }
  return data as T;
}

export function isNotFound(error: unknown): boolean {
  return error instanceof ApiError && error.status === 404;
}
