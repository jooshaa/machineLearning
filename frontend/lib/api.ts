import {
  AiAnalysis,
  AnalyticsSnapshot,
  BacktestResult,
  CreateTradePayload,
  Strategy,
  Trade,
} from './types';

const API_URL = process.env.NEXT_PUBLIC_API_URL ?? 'http://localhost:3001';

async function fetchJson<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(`${API_URL}${path}`, {
    ...init,
    headers: {
      'Content-Type': 'application/json',
      ...(init?.headers ?? {}),
    },
    cache: 'no-store',
  });

  if (!response.ok) {
    throw new Error(`Request failed: ${path}`);
  }

  return response.json();
}

export function getTrades() {
  return fetchJson<Trade[]>('/trades');
}

export function getAnalytics() {
  return fetchJson<AnalyticsSnapshot>('/analytics');
}

export function getStrategies() {
  return fetchJson<Strategy[]>('/strategies');
}

export async function getAiAnalysis() {
  try {
    return await fetchJson<AiAnalysis>('/ai-analysis');
  } catch {
    return null;
  }
}

export function createTrade(payload: CreateTradePayload) {
  return fetchJson<Trade>('/trades', {
    method: 'POST',
    body: JSON.stringify(payload),
  });
}

export async function uploadTradeScreenshots(files: File[]) {
  const formData = new FormData();
  files.forEach((file) => formData.append('files', file));

  const response = await fetch(`${API_URL}/trades/upload-screenshots`, {
    method: 'POST',
    body: formData,
  });

  if (!response.ok) {
    throw new Error('Screenshot upload failed');
  }

  return response.json() as Promise<{ urls: string[] }>;
}

export function importTradesCsv(csvContent: string) {
  return fetchJson<{ imported: number; sample: Trade[] }>('/trades/import-csv', {
    method: 'POST',
    body: JSON.stringify({ csvContent }),
  });
}

export function analyzeTradeScreenshots(id: string) {
  return fetchJson<{
    status: 'none' | 'pending' | 'completed' | 'failed';
    summary: string | null;
    detectedSetup: string | null;
    qualityScore: number | null;
    tags: string[];
  }>(`/trades/${id}/analyze-screenshots`, {
    method: 'POST',
  });
}

export function deleteTrade(id: string) {
  return fetchJson<{ success: boolean }>(`/trades/${id}`, {
    method: 'DELETE',
  });
}

export function runBacktest(payload: Record<string, unknown>) {
  return fetchJson<BacktestResult>('/backtests', {
    method: 'POST',
    body: JSON.stringify(payload),
  });
}

export function createStrategy(payload: Record<string, unknown>) {
  return fetchJson<Strategy>('/strategies', {
    method: 'POST',
    body: JSON.stringify(payload),
  });
}

export function fetchCandles(payload: {
  symbol: string;
  interval: string;
  period?: string;
  start?: string;
  end?: string;
}) {
  return fetchJson<{ candles: Array<Record<string, unknown>>; count: number }>(
    '/backtests/fetch-candles',
    {
      method: 'POST',
      body: JSON.stringify(payload),
    },
  );
}

export function fetchLocalCandles(date: string, timeframe: string = '5m') {
  return fetch(`http://localhost:8000/candles/${date}?timeframe=${timeframe}`)
    .then(res => {
      if (!res.ok) throw new Error(`Failed to fetch candles: ${res.statusText}`);
      return res.json();
    })
    .then(data => ({ candles: data }));
}

export function runAdvancedBacktest(payload: Record<string, unknown>) {
  return fetchJson<Record<string, unknown>>('/backtests/advanced', {
    method: 'POST',
    body: JSON.stringify(payload),
  });
}

export function runFabioBacktest(payload: Record<string, unknown>) {
  return fetchJson<Record<string, unknown>>('/backtests/fabio', {
    method: 'POST',
    body: JSON.stringify(payload),
  });
}

export function runVolumeDeltaBacktest() {
  return fetchJson<any>('/backtests/volume-delta', {
    method: 'POST',
  });
}

export function saveFabioResult(payload: Record<string, unknown>) {
  return fetchJson<Record<string, unknown>>('/backtests/fabio/save', {
    method: 'POST',
    body: JSON.stringify(payload),
  });
}

export function getFabioHistory() {
  return fetchJson<Record<string, unknown>[]>('/backtests/fabio/history', {
    method: 'POST',
  });
}

export function getFabioMemory() {
  return fetchJson<any>('/backtests/fabio/memory', {
    method: 'GET',
  });
}

export function trainFabioAi(payload: Record<string, unknown>) {
  return fetchJson<any>('/backtests/fabio/train', {
    method: 'POST',
    body: JSON.stringify(payload),
  });
}
export function startFabioL3(payload: Record<string, unknown>) {
  return fetchJson<any>('/backtests/fabio/l3/start', {
    method: 'POST',
    body: JSON.stringify(payload),
  });
}

export function getFabioL3Status(id: string) {
  return fetchJson<any>(`/backtests/fabio/l3/status/${id}`, {
    method: 'GET',
  });
}

export function getFabioL3Result(id: string) {
  return fetchJson<any>(`/backtests/fabio/l3/result/${id}`, {
    method: 'GET',
  });
}

export function cancelFabioL3(id: string) {
  return fetchJson<any>(`/backtests/fabio/l3/cancel/${id}`, {
    method: 'POST',
  });
}

export function getFabioL3Analysis() {
  return fetchJson<any>('/backtests/fabio/l3/analysis', {
    method: 'GET',
  });
}
