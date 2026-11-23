import ImageUploadIcon from '../../assets/icons/ImageUploadIcon';
import '../../pages/Analysis/Analysis.css';
import { useMemo, useRef, useState } from "react";
import { Replace, Trash2, Image as ImageIcon, Loader2, ArrowRight, ArrowLeft, Info } from "./Glyphs";
import { PolygonEditor, type Polygon, type PolyKind } from "./PolygonEditor";
import type { AnalysisMethod } from "./types";

const ACCEPTED = ["image/jpeg", "image/png", "image/webp"];

export interface PickedFile {
  file: File;
  url: string;
  width: number;
  height: number;
}

interface Props {
  picked: PickedFile | null;
  onPick: (p: PickedFile | null) => void;
  polys: Polygon[];
  onPolys: (p: Polygon[]) => void;
  busy: boolean;
  onAnalyze: () => void;
  onError: (msg: string) => void;
  method: AnalysisMethod;
  
  filas: number | null;
  onFilas: (n: number | null) => void;
  metadata: { pasillo: string; captureDate: string; reference: string; observations: string };
  onMetadata: (value: { pasillo: string; captureDate: string; reference: string; observations: string }) => void;
  limits: { max_upload_mb: number; min_side_px: number };

}

const STEPS = [
  { n: 1, label: "Cargar fotografía" },
  { n: 2, label: "Definir regiones" },
  { n: 3, label: "Analizar y revisar" },
];

export function NewAnalysis({ picked, onPick, polys, onPolys, busy, onAnalyze, onError, method, filas, onFilas, metadata, onMetadata, limits }: Props) {
  const [step, setStep] = useState<1 | 2 | 3>(picked ? 2 : 1);
  const [drag, setDrag] = useState(false);
  const [kind, setKind] = useState<PolyKind>("roi");
  const inputRef = useRef<HTMLInputElement>(null);

  const roiCount = useMemo(() => polys.filter((p) => p.kind === "roi").length, [polys]);



  function acceptFile(f: File | undefined | null) {
    if (!f || busy) return;
    if (!f.size) return onError("El archivo está vacío.");
    if (!ACCEPTED.includes(f.type)) return onError("Formato no permitido. Usa JPG, PNG o WEBP.");
    if (f.size > limits.max_upload_mb * 1024 * 1024) return onError(`La imagen supera ${limits.max_upload_mb} MB.`);
    const url = URL.createObjectURL(f);
    const img = new Image();
    img.onload = () => {
      if (Math.min(img.naturalWidth, img.naturalHeight) < limits.min_side_px) {
        URL.revokeObjectURL(url);
        return onError(`El ancho y el alto deben ser de al menos ${limits.min_side_px} px.`);
      }
      if (picked) URL.revokeObjectURL(picked.url);
      onPick({ file: f, url, width: img.naturalWidth, height: img.naturalHeight });
      onPolys([]);
      setStep(1);
    };
    img.onerror = () => { URL.revokeObjectURL(url); onError("No se pudo leer la imagen. ¿Está dañada?"); };
    img.src = url;
  }

  function removeImage() {
    if (picked) URL.revokeObjectURL(picked.url);
    onPick(null);
    setStep(1);
    onPolys([]);
  }

  const sizeLabel = picked ? `${(picked.file.size / 1024 / 1024).toFixed(2)} MB` : "";

  return (
    <div className="new">

      <ol className="stepper" aria-label="Progreso del análisis">
        {STEPS.map((s) => {
          const state = step === s.n ? "current" : (s.n === 1 && picked) || (s.n === 2 && step === 3) ? "done" : "todo";
          return (
            <li key={s.n} className={`step step-${state}`}>
              <button
                className="step-btn"
                disabled={(s.n > 1 && !picked) || busy}
                onClick={() => {
                  if (step === 2 && document.querySelector('[data-drawing="true"]')) { onError('Cierra o cancela la zona en curso antes de cambiar de paso.'); return; }
                  if (s.n > 1 && !metadata.pasillo.trim()) { onError('Indica el pasillo de la fotografía.'); return; }
                  if (s.n > 1 && !metadata.captureDate) { onError('Indica la fecha y hora de captura.'); return; }
                  if (s.n === 3 && step === 1) { onError('Continúa primero a definir las zonas de análisis.'); return; }
                  setStep(s.n as 1 | 2 | 3);
                }}
                aria-current={step === s.n ? "step" : undefined}
              >
                <span className="step-num">{s.n}</span>
                <span>{s.label}</span>
              </button>
            </li>
          );
        })}
      </ol>

      {step === 1 && <section className="analysis-page regova-capture">
        <header className="analysis-intro"><div className="analysis-breadcrumb"><span>Análisis</span><span aria-hidden="true">›</span><span>Nueva captura</span></div><h2>Análisis de góndola</h2><p>Carga una imagen, comprueba la vista previa y continúa a definir la región de análisis.</p></header>
        <div className="analysis-grid">
          <article className="analysis-card"><h3>1. Seleccionar imagen</h3>
            <input ref={inputRef} type="file" accept={ACCEPTED.join(',')} hidden onChange={e => {acceptFile(e.target.files?.[0]);e.target.value='';}} aria-label="Seleccionar fotografía de góndola" />
            <div className={`analysis-upload-zone ${drag ? 'analysis-upload-zone--dragging' : ''}`} onDragOver={e=>{e.preventDefault();setDrag(true);}} onDragLeave={()=>setDrag(false)} onDrop={e=>{e.preventDefault();setDrag(false);acceptFile(e.dataTransfer.files?.[0]);}}>
              <ImageUploadIcon size={56} /><p>Arrastra una imagen aquí<br />o selecciona un archivo</p><button type="button" className="analysis-select-button" onClick={()=>inputRef.current?.click()}>{picked?'Cambiar imagen':'Seleccionar imagen'}</button>
              {picked && <div className="analysis-selected-file"><span title={picked.file.name}>{picked.file.name}</span><button type="button" className="analysis-remove-button" onClick={removeImage}>Quitar imagen</button></div>}
            </div>
            <p className="analysis-file-hint">Formatos: JPG, PNG y WEBP<br />Tamaño máximo: {limits.max_upload_mb} MB · Dimensión mínima: {limits.min_side_px} px</p>
          </article>
          <article className="analysis-card"><h3>2. Vista previa</h3><div className="analysis-preview">{picked?<img src={picked.url} alt={`Vista previa de ${picked.file.name}`} className="analysis-preview-image" />:<div className="analysis-preview-empty"><ImageUploadIcon size={48} /><p>La imagen seleccionada aparecerá aquí.</p></div>}</div><div className="analysis-preview-notice"><span aria-hidden="true">ⓘ</span><p>{picked?`${picked.width} × ${picked.height} px · ${sizeLabel}. Comprueba que la fotografía sea la correcta antes de trazar las zonas.`:'Asegúrate de que la góndola sea visible y esté bien iluminada.'}</p></div></article>
          <article className="analysis-card analysis-info-card"><h3>Información de la captura</h3>
            <div className="analysis-field"><label htmlFor="capture-pasillo">Pasillo</label><input id="capture-pasillo" required value={metadata.pasillo} maxLength={50} onChange={e=>onMetadata({...metadata,pasillo:e.target.value})} placeholder="Ej. 4 o P-04" /></div>
            <div className="analysis-field"><label htmlFor="capture-reference">Referencia de ubicación (opcional)</label><input id="capture-reference" value={metadata.reference} maxLength={100} onChange={e=>onMetadata({...metadata,reference:e.target.value})} placeholder="Ej. Sector de bebidas" /></div>
            <div className="analysis-field"><label htmlFor="capture-date">Fecha y hora de captura</label><input id="capture-date" type="datetime-local" value={metadata.captureDate} required onChange={e=>onMetadata({...metadata,captureDate:e.target.value})} /></div>
            <div className="analysis-field"><label htmlFor="capture-observations">Observaciones de la captura (opcional)</label><textarea id="capture-observations" rows={3} maxLength={500} value={metadata.observations} onChange={e=>onMetadata({...metadata,observations:e.target.value})} placeholder="Ej. Cartel que obstruye parte del estante" aria-describedby="capture-counter" /><small id="capture-counter">{metadata.observations.length}/500 caracteres</small></div>
            <button type="button" className="analysis-start-button" disabled={!picked || !metadata.captureDate || !metadata.pasillo.trim()} onClick={()=>setStep(2)}>Continuar a definir zonas →</button>
          </article>
        </div>
        <aside className="analysis-considerations"><span className="analysis-considerations-icon" aria-hidden="true">ⓘ</span><div><strong>Consideraciones</strong><ul><li>Comprueba que la fotografía sea nítida y corresponda a la captura.</li><li>En el siguiente paso podrás delimitar la región de interés y excluir obstrucciones.</li><li>La fecha corresponde a cuando se tomó la fotografía.</li></ul></div></aside>
      </section>}
      {step >= 2 && picked && (
        <>
          <section className="file-bar">
            <div className="file-meta">
              <ImageIcon size={18} />
              <div>
                <b title={picked.file.name}>{picked.file.name}</b>
                <span className="muted">{picked.width} × {picked.height} px · {sizeLabel}</span>
              </div>
            </div>
            <div className="file-actions">
              <button disabled={busy} className="btn ghost sm" onClick={() => inputRef.current?.click()}><Replace size={14} /> Reemplazar</button>
              <button className="btn danger-ghost sm" disabled={busy} onClick={removeImage}><Trash2 size={14} /> Quitar</button>
              <input ref={inputRef} type="file" accept={ACCEPTED.join(",")} hidden onChange={(e) => { acceptFile(e.target.files?.[0]); e.target.value = ""; }} />
            </div>
          </section>

          {step === 2 && (
            <>
              <div className="info-line"><Info size={16} /> Marcar zonas es opcional. Sin marcas, el sistema analiza toda la imagen.</div>
              <PolygonEditor key={picked.url} src={picked.url} imageWidth={picked.width} imageHeight={picked.height} polygons={polys} onChange={onPolys} kind={kind} onKindChange={setKind} />
            </>
          )}

          {step === 3 && (
            <section className="panel ready">
              <h2>Listo para analizar</h2>
              <ul className="summary">
                <li>Fotografía: <b>{picked.file.name}</b></li>
                <li>Región de análisis: <b>{roiCount === 0 ? "toda la imagen" : `${roiCount} definida`}</b></li>
                <li>Zonas excluidas: <b>{polys.filter((p) => p.kind === "exclusion").length}</b></li>
                <li>Zonas estructurales: <b>{polys.filter((p) => p.kind === "structural").length}</b></li>
              </ul>
              {roiCount > 1 && <p className="notice warn" role="alert">Hay más de una región de análisis. Deja solo una para continuar.</p>}
              <p className="notice info">Revisa el área seleccionada y el número de estantes antes de continuar.</p>
            </section>
          )}

          {step === 3 && (
            <section className="method-picker">
              <label className="field">
                {method !== "heuristic" && roiCount === 0 && <small className="hint">Sin área de estantes, el piso y el techo cuentan como vacío. Marca los estantes para un resultado fiable.</small>}
              </label>
              {method !== "heuristic" && (
                <label className="field">
                  <span>Estantes dentro de la región de interés (opcional)</span>
                  <input type="number" min={1} max={20} inputMode="numeric" placeholder="Automático" value={filas ?? ""} disabled={busy}
                    onChange={(e) => onFilas(e.target.value ? Number(e.target.value) : null)} />
                  <small className="hint">La región se divide en esa cantidad de estantes. Si no se detecta ningún producto, no se pueden estimar los frentes.</small>
                </label>
              )}
            </section>
          )}

          <footer className="wizard-nav">
            <button className="btn ghost" onClick={() => { if (document.querySelector('[data-drawing="true"]') && !window.confirm("¿Descartar el trazado sin cerrar y volver?")) return; setStep(step === 3 ? 2 : 1); }} disabled={step === 1 || busy}>
              <ArrowLeft size={16} /> {step === 3 ? "Volver a las zonas" : "Anterior"}
            </button>
            {step === 2 ? (
              <button className="btn primary" onClick={() => { if (document.querySelector('[data-drawing="true"]')) { onError("Cierra o cancela la zona en curso antes de continuar."); return; } setStep(3); }} disabled={roiCount > 1}>
                Continuar <ArrowRight size={16} />
              </button>
            ) : (
              <button className="btn primary lg" onClick={onAnalyze} disabled={busy || roiCount > 1 || !picked || !metadata.captureDate || !metadata.pasillo.trim() || (filas !== null && (!Number.isInteger(filas) || filas < 1 || filas > 20))}>
                {busy ? <><Loader2 size={18} className="spin" /> Analizando…</> : <>Analizar góndola</>}
              </button>
            )}
          </footer>
        </>
      )}
    </div>
  );
}
