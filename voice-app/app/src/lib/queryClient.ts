import { notifyManager, QueryClient } from '@tanstack/react-query';

export { QueryClientProvider } from '@tanstack/react-query';

/**
 * Shared QueryClient instance used across the app.
 *
 * Extracted into its own side-effect-free module so it can be imported from
 * both the React bootstrap (main.tsx) and non-React code (stores, utilities)
 * without pulling in ReactDOM or other bootstrap side effects.
 */
export const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      staleTime: 1000 * 60 * 5, // 5 minutes
      gcTime: 1000 * 60 * 10, // 10 minutes (formerly cacheTime)
      retry: 1,
      refetchOnWindowFocus: false,
    },
  },
});

/** Drop all previous-server data, including server-specific initialData. */
export function resetServerQueries(): void {
  notifyManager.batch(() => {
    for (const query of queryClient.getQueryCache().getAll()) {
      // reset cancels the previous request; clearing its initialData must
      // happen before refetch so cancellation cannot restore an old seed.
      query.reset();
      query.setState({ data: undefined, dataUpdatedAt: 0, status: 'pending' });
    }
  });
  void queryClient.refetchQueries({ type: 'active' });
}
