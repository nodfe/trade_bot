import { QueryClient } from "@tanstack/react-query";

/**
 * Pre-configured QueryClient with sensible defaults for the quant platform.
 */
export function createQueryClient(): QueryClient {
  return new QueryClient({
    defaultOptions: {
      queries: {
        // Stock data updates frequently but stale-while-revalidate keeps UI fast
        staleTime: 30 * 1000, // 30s
        gcTime: 5 * 60 * 1000, // 5 min (formerly cacheTime)
        retry: 2,
        refetchOnWindowFocus: false,
      },
      mutations: {
        retry: 1,
      },
    },
  });
}

/** Default shared instance for apps that don't need custom config. */
export const queryClient = createQueryClient();

export { api, apiFetch, ApiError } from "./client";
