import { useCallback, useEffect, useState } from 'react';

const loading = key => ({ key, status: 'loading', text: '' });

export function artifactVersion(files, name) {
  const file = Array.isArray(files) ? files.find(item => item?.name === name) : null;
  const value = file?.version ?? file?.at;
  return typeof value === 'string' || typeof value === 'number' ? String(value) : '';
}

export function artifactUrl(id, file, version = '') {
  const url = `/files/${encodeURIComponent(String(id))}/${encodeURIComponent(String(file))}`;
  return version ? `${url}?v=${encodeURIComponent(String(version))}` : url;
}

export async function runArtifactRequest(fetcher, url, signal, publish) {
  try {
    const response = await fetcher(url, { signal, cache: 'no-store' });
    if (signal.aborted) return;
    if (!response.ok) throw new Error('artifact response failed');
    const text = await response.text();
    if (signal.aborted) return;
    publish(text.trim() ? { status: 'ready', text } : { status: 'empty', text: '' });
  } catch {
    if (!signal.aborted) publish({ status: 'error', text: '' });
  }
}

export function useArtifactText(id, file, version = '') {
  const [attempt, setAttempt] = useState(0);
  const key = `${id}\u0000${file}\u0000${version}\u0000${attempt}`;
  const [content, setContent] = useState(() => loading(key));

  useEffect(() => {
    const controller = new AbortController();
    setContent(loading(key));
    void runArtifactRequest(fetch, artifactUrl(id, file, version), controller.signal,
      value => setContent({ key, ...value }));
    return () => controller.abort();
  }, [id, file, version, attempt, key]);

  const retry = useCallback(() => setAttempt(current => current + 1), []);
  return { ...(content.key === key ? content : loading(key)), retry };
}
