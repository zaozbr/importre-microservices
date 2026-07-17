import { useState, useEffect, useRef, useCallback } from 'react';

// Hook generico para polling de API
export function usePoll(url, interval = 3000) {
  const [data, setData] = useState(null);
  const [error, setError] = useState(null);
  const [loading, setLoading] = useState(true);
  const timerRef = useRef();

  const fetch_ = useCallback(async () => {
    try {
      const res = await fetch(url);
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      const json = await res.json();
      setData(json);
      setError(null);
    } catch (e) {
      setError(e.message);
    } finally {
      setLoading(false);
    }
  }, [url]);

  useEffect(() => {
    fetch_();
    timerRef.current = setInterval(fetch_, interval);
    return () => clearInterval(timerRef.current);
  }, [fetch_, interval]);

  return { data, error, loading, refresh: fetch_ };
}

// Hook para aria2 RPC
export function useAria2(method, params = [], interval = 3000) {
  const [data, setData] = useState(null);
  const timerRef = useRef();

  useEffect(() => {
    const fetch_ = async () => {
      try {
        const res = await fetch('/aria2', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({
            jsonrpc: '2.0',
            method: `aria2.${method}`,
            id: 'dashboard',
            params: ['token:devin', ...params],
          }),
        });
        const json = await res.json();
        if (json.result !== undefined) setData(json.result);
      } catch {}
    };
    fetch_();
    timerRef.current = setInterval(fetch_, interval);
    return () => clearInterval(timerRef.current);
  }, [method, JSON.stringify(params), interval]);

  return data;
}

// Hook para log streaming
export function useLog(interval = 5000) {
  const [lines, setLines] = useState([]);
  const timerRef = useRef();

  useEffect(() => {
    const fetch_ = async () => {
      try {
        const res = await fetch('/api/log');
        const json = await res.json();
        if (json.lines) setLines(json.lines);
      } catch {}
    };
    fetch_();
    timerRef.current = setInterval(fetch_, interval);
    return () => clearInterval(timerRef.current);
  }, [interval]);

  return lines;
}
