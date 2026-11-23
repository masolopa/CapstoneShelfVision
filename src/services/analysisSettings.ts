import { apiFetch } from './http';
export type AnalysisSettings = { threshold: number; low_threshold: number; max_upload_mb: number; min_side_px: number };

async function requestSettings(method: 'GET' | 'PUT', body?: AnalysisSettings, signal?: AbortSignal): Promise<AnalysisSettings> {
  const response = await apiFetch('/api/settings', {
    method, signal: signal ?? AbortSignal.timeout(10000),
    headers: body ? { 'Content-Type': 'application/json' } : undefined,
    body: body ? JSON.stringify(body) : undefined,
  });
  if (!response.ok) throw new Error('No se pudo guardar o cargar la configuración del servidor. Intenta nuevamente.');
  const value: unknown = await response.json();
  if (!value || typeof value !== 'object') throw new Error('El servidor devolvió una configuración inválida.');
  const settings = value as AnalysisSettings;
  if (!Number.isInteger(settings.threshold) || settings.threshold <= 0 || settings.threshold >= 100 ||
      !Number.isInteger(settings.low_threshold) || settings.low_threshold <= settings.threshold || settings.low_threshold > 100 ||
      !Number.isFinite(settings.max_upload_mb) || settings.max_upload_mb <= 0 || settings.max_upload_mb > 50 ||
      !Number.isSafeInteger(settings.min_side_px) || settings.min_side_px < 50) {
    throw new Error('El servidor devolvió una configuración inválida.');
  }
  return settings;
}
export const getAnalysisSettings = (signal?: AbortSignal) => requestSettings('GET', undefined, signal);
export const saveAnalysisSettings = (settings: AnalysisSettings) => requestSettings('PUT', settings);
