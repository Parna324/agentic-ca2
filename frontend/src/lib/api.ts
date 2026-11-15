const API_BASE = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000';

async function request<T>(path: string, options?: RequestInit): Promise<T> {
  const url = `${API_BASE}/api${path}`;
  const res = await fetch(url, {
    headers: { 'Content-Type': 'application/json', ...options?.headers },
    ...options,
  });
  if (!res.ok) {
    const error = await res.text();
    throw new Error(`API Error ${res.status}: ${error}`);
  }
  return res.json();
}

export const api = {
  health: () =>
    request<{ status: string; offline_mode: boolean; model?: string; version?: string }>('/health'),

  createReview: (data: import('./types').CreateReviewRequest) =>
    request<import('./types').ReviewSummary>('/reviews', {
      method: 'POST',
      body: JSON.stringify(data),
    }),

  listReviews: (limit = 50) =>
    request<import('./types').ReviewSummary[]>(`/reviews?limit=${limit}`),

  getReview: (id: string) =>
    request<import('./types').ReviewDetail>(`/reviews/${id}`),

  getFindings: (id: string, severity?: string) =>
    request<import('./types').Finding[]>(
      `/reviews/${id}/findings${severity ? `?severity=${severity}` : ''}`
    ),

  getAgents: (id: string) =>
    request<import('./types').AgentExecution[]>(`/reviews/${id}/agents`),

  getLogs: (id: string) => request<unknown[]>(`/reviews/${id}/logs`),

  getReport: (id: string) => request<unknown>(`/reviews/${id}/report`),
};
