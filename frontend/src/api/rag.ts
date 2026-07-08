import { apiClient } from './client'
import { useAuthStore } from '../stores/auth'

export interface RagSource {
  content_id: number
  version_id: number
  chunk_id: number
  title: string
  content_type: string
  scope_type?: 'global' | 'department'
  department_id?: number | null
  department_name?: string | null
  updated_at: string
  update_level: 'minor' | 'medium' | 'major'
  relevance_score: number
}

export interface RagStreamCallbacks {
  onSources?: (sources: RagSource[]) => void;
  onContent?: (text: string) => void;
  onError?: (error: string) => void;
  onDone?: () => void;
  onDebug?: (stage: string, data: any) => void;
}

export async function askRagStream(
  question: string,
  callbacks: RagStreamCallbacks,
  signal?: AbortSignal,
  debug = false,
): Promise<void> {
  const auth = useAuthStore();
  const token = auth.token;

  try {
    const baseURL = import.meta.env.VITE_API_BASE_URL || '/api';
    const url = debug
      ? `${baseURL}/app/rag/ask?debug=1`
      : `${baseURL}/app/rag/ask`;
    const response = await fetch(url, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        ...(token ? { Authorization: `Bearer ${token}` } : {})
      },
      body: JSON.stringify({ question }),
      signal
    });

    if (!response.ok) {
      if (response.status === 401) {
        auth.clearSession();
        window.location.href = '/login';
        return;
      }
      const errorData = await response.json().catch(() => ({}));
      callbacks.onError?.(errorData.message || '服务异常，请稍后重试');
      return;
    }

    const reader = response.body?.getReader();
    if (!reader) {
      callbacks.onError?.('当前环境不支持流式读取');
      return;
    }

    const decoder = new TextDecoder('utf-8');
    let buffer = '';

    while (true) {
      const { done, value } = await reader.read();
      if (done) break;
      
      buffer += decoder.decode(value, { stream: true });
      const lines = buffer.split('\n\n');
      buffer = lines.pop() || '';

      for (const line of lines) {
        if (line.startsWith('data: ')) {
          try {
            const data = JSON.parse(line.slice(6));
            if (data.type === 'sources') {
              callbacks.onSources?.(data.sources);
            } else if (data.type === 'content') {
              callbacks.onContent?.(data.text);
            } else if (data.type === 'error') {
              callbacks.onError?.(data.message);
            } else if (data.type === 'done') {
              callbacks.onDone?.();
            } else if (data.type === 'debug') {
              callbacks.onDebug?.(data.stage, data);
            }
          } catch (e) {
            console.error('SSE JSON parse error', e);
          }
        }
      }
    }
  } catch (error: any) {
    if (error.name === 'AbortError') return;
    callbacks.onError?.('网络异常，请重试');
  }
}
