/**
 * NexAlfa REST API Client
 */
const API_URL = process.env.NEXT_PUBLIC_GATEWAY_URL || 'http://localhost:18789';

async function fetchAPI<T>(path: string, options?: RequestInit): Promise<T> {
  const res = await fetch(`${API_URL}${path}`, {
    headers: { 'Content-Type': 'application/json' }, ...options,
  });
  if (!res.ok) throw new Error(`API Error: ${res.status} ${res.statusText}`);
  return res.json();
}

export interface ModelInfo {
  current_model: string;
  thinking_level: string;
  temperature: number;
  max_tokens: number;
  streaming: boolean;
  fallback_models: string[];
  providers: Array<{
    name: string;
    display: string;
    models: string[];
  }>;
}

export const api = {
  getStatus: () => fetchAPI<any>('/api/status'),
  getSessions: () => fetchAPI<any[]>('/api/sessions'),
  getSessionMessages: (id: string, limit = 50) => fetchAPI<any[]>(`/api/sessions/${id}/messages?limit=${limit}`),
  sendMessage: (content: string, channel = 'api', channelId = 'web') =>
    fetchAPI<{ response: string }>('/api/message', {
      method: 'POST', body: JSON.stringify({ content, channel, channel_id: channelId }),
    }),
  getSkills: () => fetchAPI<any[]>('/api/skills'),
  getMemories: () => fetchAPI<any>('/api/memories'),
  getChannels: () => fetchAPI<any[]>('/api/channels'),
  getConfig: () => fetchAPI<any>('/api/config'),

  // Model & settings control
  getModel: () => fetchAPI<ModelInfo>('/api/model'),
  setModel: (model: string) =>
    fetchAPI<any>('/api/model', { method: 'POST', body: JSON.stringify({ model }) }),
  setThinking: (level: string) =>
    fetchAPI<any>('/api/thinking', { method: 'POST', body: JSON.stringify({ level }) }),
  setTemperature: (temperature: number) =>
    fetchAPI<any>('/api/temperature', { method: 'POST', body: JSON.stringify({ temperature }) }),
  setDevMode: (opts: { show_thinking?: boolean; enabled?: boolean }) =>
    fetchAPI<any>('/api/dev-mode', { method: 'POST', body: JSON.stringify(opts) }),
};
