// ─── API Client ────────────────────────────────────────────────
// Apunta a tu FastAPI. Cambia la URL según tu setup.
// En .env puedes poner: VITE_API_URL=http://localhost:8000

const BASE_URL = import.meta.env.VITE_API_URL || 'http://localhost:8000';

export async function api<T>(endpoint: string, options?: RequestInit): Promise<T> {
  const url = `${BASE_URL}${endpoint}`;

  const res = await fetch(url, {
    headers: { 'Content-Type': 'application/json' },
    ...options,
  });

  if (!res.ok) {
    const error = await res.json().catch(() => ({ detail: res.statusText }));
    throw new Error(error.detail || `Error ${res.status}`);
  }

  return res.json();
}
