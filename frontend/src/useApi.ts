import { useEffect, useRef, useState } from "react";

type State<T> = { data?: T; error?: string; loading: boolean };

/**
 * GET /api{path} and track loading/error. Pass null to fetch nothing.
 *
 * The AbortController matters: click alert A, then quickly alert B. Without
 * aborting, A's slower response can arrive AFTER B's and overwrite the screen with
 * the wrong transaction. Aborting the old request on change prevents that race.
 *
 * Refreshing: when `refreshMs` is set the request repeats on a timer, and whenever
 * `refreshKey` changes it repeats once. A refresh keeps showing the old data until
 * the new data arrives (no "Loading…" flash); only a new `path` clears the screen.
 */
export function useApi<T>(
  path: string | null,
  { refreshMs, refreshKey }: { refreshMs?: number; refreshKey?: unknown } = {},
): State<T> {
  const [state, setState] = useState<State<T>>({ loading: path !== null });
  const [tick, setTick] = useState(0);
  const lastPath = useRef<string | null>(null);

  useEffect(() => {
    if (!refreshMs) return;
    const id = setInterval(() => setTick((t) => t + 1), refreshMs);
    return () => clearInterval(id);
  }, [refreshMs]);

  useEffect(() => {
    if (path === null) return;
    const ctrl = new AbortController();
    if (lastPath.current !== path) {
      lastPath.current = path;
      setState({ loading: true });
    }
    fetch(`/api${path}`, { signal: ctrl.signal })
      .then(async (r) => {
        if (!r.ok) throw new Error(`${r.status}: ${await r.text()}`);
        return (await r.json()) as T;
      })
      .then((data) => setState({ data, loading: false }))
      .catch((e: Error) => {
        if (e.name !== "AbortError") setState({ error: e.message, loading: false });
      });
    return () => ctrl.abort();
  }, [path, tick, refreshKey]);

  return state;
}
