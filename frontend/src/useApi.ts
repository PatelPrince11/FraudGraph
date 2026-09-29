import { useEffect, useState } from "react";

type State<T> = { data?: T; error?: string; loading: boolean };

/**
 * GET /api{path} and track loading/error. Pass null to fetch nothing.
 *
 * The AbortController matters: click alert A, then quickly alert B. Without
 * aborting, A's slower response can arrive AFTER B's and overwrite the screen with
 * the wrong transaction. Aborting the old request on change prevents that race.
 */
export function useApi<T>(path: string | null): State<T> {
  const [state, setState] = useState<State<T>>({ loading: path !== null });

  useEffect(() => {
    if (path === null) return;
    const ctrl = new AbortController();
    setState({ loading: true });
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
  }, [path]);

  return state;
}
