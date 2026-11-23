import { useEffect, useRef, useState, useSyncExternalStore } from 'react';
import { NewAnalysis, type PickedFile } from './NewAnalysis';
import { Results } from './Results';
import { History } from './History';
import type { Polygon } from './PolygonEditor';
import type { AnalysisResult, Settings } from './types';
import { analyzeImage, getAnalysis, getSettings } from './api';
import './Flow.css';

function subscribe(callback: () => void) { window.addEventListener('hashchange', callback); return () => window.removeEventListener('hashchange', callback); }
const snapshot = () => window.location.hash;
const nowLocal = () => { const date = new Date(); return new Date(date.getTime() - date.getTimezoneOffset() * 60000).toISOString().slice(0,16); };
export default function AnalysisFlow({ history = false, review = false }: { history?: boolean; review?: boolean }) {
  const hash = useSyncExternalStore(subscribe, snapshot);
  const requestedId = new URLSearchParams(hash.split('?')[1] || '').get('result');
  const invalidId = requestedId!==null && (!/^\d+$/.test(requestedId) || !Number.isSafeInteger(Number(requestedId)) || Number(requestedId)<1);
  const [picked, setPicked] = useState<PickedFile | null>(null);
  const pickedRef = useRef<PickedFile | null>(null);
  const [polygons, setPolygons] = useState<Polygon[]>([]);
  const [filas, setFilas] = useState<number | null>(null);
  const [metadata, setMetadata] = useState({ pasillo:'', captureDate:nowLocal(), reference:'', observations:'' });
  const [settings, setSettings] = useState<Settings | null>(null);
  const [result, setResult] = useState<AnalysisResult | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');
  const [retry, setRetry] = useState(0);
  useEffect(() => {
    let active = true;
    if(history || requestedId) return;
    getSettings().then(value => { if (active) setSettings(value); }).catch(() => { if(active) setError('No se pudo conectar al backend. Inicia backend/EJECUTAR.bat y reintenta.'); });
    return () => {active = false;};
  }, [retry,history,requestedId]);
  useEffect(() => {
    if (!requestedId) return;
    if(!/^\d+$/.test(requestedId) || Number(requestedId)<1)return;
    let active = true;
    getAnalysis(Number(requestedId)).then(value => { if(active) {setResult(value);setError('');} }).catch(e => {if(active) setError(e instanceof Error ? e.message : 'No se pudo abrir el análisis.');});
    return () => {active=false;};
  }, [requestedId,retry]);
  useEffect(() => () => { if(pickedRef.current) URL.revokeObjectURL(pickedRef.current.url); }, []);
  function onPick(value: PickedFile | null) { pickedRef.current = value; setPicked(value); setResult(null); setError(''); setFilas(null); }
  async function analyze() {
    if (!picked || busy || !metadata.captureDate) return;
    if (!metadata.pasillo.trim()) { setError('Indica el pasillo de la fotografía.'); return; }
    setBusy(true);setError('');
    try {
      const value = await analyzeImage(picked.file, {method:'yolo',filas,
        roi:polygons.find(p => p.kind === 'roi')?.points,
        exclusions:polygons.filter(p => p.kind === 'exclusion').map(p => p.points),
        structural:polygons.filter(p => p.kind === 'structural').map(p => p.points), ...metadata });
      value.filename = picked.file.name;
      setResult(value);
      window.location.hash = `/analysis?result=${value.id}`;
    } catch(e) {setError(e instanceof Error ? e.message : 'No se pudo analizar la imagen.');}
    finally {setBusy(false);}
  }
  function back() { setResult(null);setError('');window.location.hash = review ? '/review' : history ? '/history' : '/analysis'; }
  function resetCapture() {
    if (pickedRef.current) URL.revokeObjectURL(pickedRef.current.url);
    pickedRef.current=null;
    setPicked(null);setPolygons([]);setFilas(null);setResult(null);setError('');
    setMetadata({pasillo:'',captureDate:nowLocal(),reference:'',observations:''});
  }
  function startNew() {resetCapture();window.location.hash='/analysis';}
  function finish() {resetCapture();window.location.hash='/history';}
  const visibleResult = requestedId && result && result.id === Number(requestedId) ? result : null;
  return <div className="regova-flow">
    {error && <div className="panel error-panel" role="alert">{error}<button className="btn ghost" onClick={() => {setError('');setRetry(value => value+1);}}>Reintentar conexión</button></div>}
    {invalidId ? <p className="panel error-panel" role="alert">El identificador del reporte no es válido. <a href="#/history">Ver reportes</a></p> : requestedId ? visibleResult ? <Results review={review} key={visibleResult.id} result={visibleResult} originalUrl={null} onBack={back} onNew={startNew} onFinish={finish} onUpdated={setResult} /> : !error && <p role="status">Cargando resultado…</p>
      : history ? <History mode="history" onOpen={id => {setResult(null);window.location.hash=`${review ? "/review" : "/history"}?result=${id}`;}} />
      : settings ? <NewAnalysis picked={picked} onPick={onPick} polys={polygons} onPolys={setPolygons} busy={busy} onAnalyze={analyze} onError={setError} method="yolo" filas={filas} onFilas={setFilas} metadata={metadata} onMetadata={setMetadata} limits={settings} /> : !error && <p role="status">Cargando requisitos de imágenes…</p>}
  </div>;
}
