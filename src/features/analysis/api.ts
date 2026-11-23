import { apiFetch } from '../../services/http';
import type { AnalysisMethod, AnalysisResult, Health, HistoryItem, Metrics, Settings, TrainingStatus } from "./types";

async function parse<T>(res: Response): Promise<T> {
  const body = await res.json().catch(() => null);
  if (!res.ok) {
    const detail = body && typeof body.detail === "string" ? body.detail : res.status===422 ? "Revisa los datos ingresados: hay valores inválidos." : "No se pudo completar la solicitud en el servidor.";
    throw new Error(detail);
  }
  if(body === null) throw new Error("El servidor devolvió una respuesta inválida. Comprueba la conexión e intenta nuevamente.");
  return body as T;
}

export interface AnalyzeOptions {
  pasillo: string; captureDate?: string; reference?: string; observations?: string;
  roi?: number[][];
  exclusions?: number[][][];
  structural?: number[][][];
  method?: AnalysisMethod;
  filas?: number | null;
}

export async function analyzeImage(file: File, opts: AnalyzeOptions): Promise<AnalysisResult> {
  const fd = new FormData();
  fd.append("file", file);
  fd.append("pasillo", opts.pasillo);
  fd.append("capture_date", opts.captureDate ?? "");
  fd.append("reference", opts.reference ?? "");
  fd.append("observations", opts.observations ?? "");
  fd.append("method", opts.method ?? "heuristic");
  if (opts.filas) fd.append("filas", String(opts.filas));
  if (opts.roi) fd.append("roi", JSON.stringify(opts.roi));
  if (opts.exclusions?.length) fd.append("exclusions", JSON.stringify(opts.exclusions));
  if (opts.structural?.length) fd.append("structural", JSON.stringify(opts.structural));
  const r = await apiFetch("/api/analyze", { method: "POST", body: fd, signal: AbortSignal.timeout(150000) });
  return parse<AnalysisResult>(r);
}

export const getAnalysis = async (id: number) => parse<AnalysisResult>(await apiFetch(`/api/analyze/${id}`,{signal:AbortSignal.timeout(15000)}));
export const getHistory = async (limit = 200) => parse<HistoryItem[]>(await apiFetch(`/api/history?limit=${limit}`,{signal:AbortSignal.timeout(15000)}));
export const getMetrics = async () => parse<Metrics>(await apiFetch("/api/metrics"));
export const getSettings = async () => parse<Settings>(await apiFetch("/api/settings",{signal:AbortSignal.timeout(15000)}));
export const getHealth = async () => parse<Health>(await apiFetch("/api/health"));
export const reportUrl = (id: number) => `/api/analyze/${id}/report.pdf`;

export async function saveSettings(body: Partial<Settings>): Promise<Settings> {
  return parse<Settings>(
    await apiFetch("/api/settings", {
      method: "PUT",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body),
    })
  );
}

export const getTraining = async () => parse<TrainingStatus>(await apiFetch("/api/training/status"));

export async function downloadGroupedReports(ids:number[]):Promise<void> {
  const response=await apiFetch('/api/reports/grouped.pdf',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({ids})});
  if(!response.ok){const body=await response.json().catch(()=>({}));throw new Error(typeof body.detail==='string'?body.detail:'No se pudo generar el PDF agrupado. Intenta nuevamente.');}
  const blob=await response.blob();
  const url=URL.createObjectURL(blob);
  const link=document.createElement('a');link.href=url;link.download=`regova_reportes_${ids.length}.pdf`;document.body.appendChild(link);link.click();link.remove();
  window.setTimeout(()=>URL.revokeObjectURL(url),60000);
}

export const updateAnalysisMetadata = async (id:number, metadata:{pasillo:string;reference:string;observations:string}) => parse<AnalysisResult>(await apiFetch(`/api/analyze/${id}`,{method:'PATCH',headers:{'Content-Type':'application/json'},body:JSON.stringify(metadata)}));
export async function deleteAnalysis(id:number):Promise<void>{
  const response=await apiFetch(`/api/analyze/${id}`,{method:'DELETE'});
  if(!response.ok)await parse(response);
}

export type ReviewDecision = 'confirmado' | 'corregido' | 'descartado';
export interface ReviewInput { decision: ReviewDecision; correccion: Record<string, unknown>; comentario: string | null }
export interface SavedReview extends ReviewInput { id: number; creado_en: string; revisor_codigo: string; revisor_nombre: string }
export const getReviews = async (id:number) => parse<SavedReview[]>(await apiFetch(`/api/analyze/${id}/reviews`,{signal:AbortSignal.timeout(15000)}));
export const createReview = async (id:number, body:ReviewInput) => parse<{id:number}>(await apiFetch(`/api/analyze/${id}/reviews`, {method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(body)}));
