/** Sesión por cookie HttpOnly; sin credenciales en localStorage. */
export async function apiFetch(input: RequestInfo | URL, init: RequestInit = {}): Promise<Response> {
  const headers = new Headers(init.headers);
  if (!['GET', 'HEAD'].includes((init.method ?? 'GET').toUpperCase())) headers.set('X-Regova-Request', '1');
  const response = await fetch(input, { ...init, headers, credentials: 'same-origin' });
  if (response.status === 401 && !String(input).endsWith('/auth/login')) window.dispatchEvent(new Event('regova:session-expired'));
  return response;
}
export async function apiJson<T>(url: string, init?: RequestInit): Promise<T> {
  const response = await apiFetch(url, init);
  if (!response.ok) {
    const body = await response.json().catch(() => null);
    throw new Error(typeof body?.detail === 'string' ? body.detail : 'No se pudo completar la operación.');
  }
  if (response.status === 204) return undefined as T;
  return response.json() as Promise<T>;
}
export function jsonBody(body: unknown, method = 'POST'): RequestInit {
  return { method, headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(body) };
}
