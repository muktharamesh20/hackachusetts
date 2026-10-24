import { useFocusEffect } from "expo-router";
import { DependencyList, useCallback, useRef, useState } from "react";

/** Load data whenever the screen gains focus; exposes pull-to-refresh state. */
export function useLoad<T>(load: () => Promise<T>, deps: DependencyList = []) {
  const [data, setData] = useState<T | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [refreshing, setRefreshing] = useState(false);
  const loadRef = useRef(load);
  loadRef.current = load;

  const run = useCallback(async () => {
    try {
      setData(await loadRef.current());
      setError(null);
    } catch (e: any) {
      setError(e?.message ?? "Something went wrong");
    }
  }, []);

  useFocusEffect(
    useCallback(() => {
      run();
      // eslint-disable-next-line react-hooks/exhaustive-deps
    }, [run, ...deps]),
  );

  const refresh = useCallback(async () => {
    setRefreshing(true);
    await run();
    setRefreshing(false);
  }, [run]);

  return { data, error, loading: data === null && error === null, refreshing, refresh, reload: run };
}
