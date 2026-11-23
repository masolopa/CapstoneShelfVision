import { ReviewPanel } from './ReviewPanel';
import { useSession } from '../../services/session';
import { surfacePercentageTenths } from "./surfacePercentages";
import { useState } from "react";
import { ArrowLeft, Download, Clock, Layers, Eye, Columns2, Image as ImageIcon } from "./Glyphs";
import type { AnalysisResult } from "./types";
import { reportUrl, updateAnalysisMetadata, deleteAnalysis } from "./api";
import { SEMANTIC, type Semantic } from "./Icon";
import { ShelfRows } from "./ShelfRows";

interface Props {
  review?: boolean;
  result: AnalysisResult;
  originalUrl: string | null;
  onBack: () => void;
  onNew: () => void;
  onFinish: () => void;
  onUpdated: (result:AnalysisResult) => void;
}

type Mode = "overlay" | "original" | "side";

const CRIT_TEXT: Record<string, string> = {
  aceptable: "Disponibilidad aceptable",
  baja: "Disponibilidad baja",
  critica: "Disponibilidad crítica",
  no_evaluable: "No evaluable",
};

export function Results({ review = false, result, originalUrl, onBack, onNew, onFinish, onUpdated }: Props) {
  const user = useSession();
  const canWrite = user?.role === 'admin_principal' || user?.role === 'admin_local' || user?.role === 'supervisor';
  const canDelete = user?.role === 'admin_principal' || user?.role === 'admin_local';
  originalUrl = originalUrl || (result.original_jpg_b64 ? `data:image/jpeg;base64,${result.original_jpg_b64}` : null);
  const [editing,setEditing]=useState(false);
  const [metadata,setMetadata]=useState({pasillo:result.pasillo,reference:result.reference??'',observations:result.observations??''});
  const [saving,setSaving]=useState(false);
  const [feedback,setFeedback]=useState('');
  async function saveMetadata(event:React.FormEvent<HTMLFormElement>){
    event.preventDefault();if(saving)return;setSaving(true);setFeedback('');
    try{const updated=await updateAnalysisMetadata(result.id,metadata);onUpdated(updated);setEditing(false);setFeedback('Cambios guardados en el reporte.');}
    catch(error){setFeedback(error instanceof Error?error.message:'No se pudo guardar.');}
    finally{setSaving(false);}
  }
  async function removeReport(){
    if(saving || !window.confirm(`¿Eliminar el reporte #${result.id} (${result.filename??'captura'})? Dejará de estar disponible en Reportes, el dashboard y las descargas. Se conservará una copia interna de respaldo.`))return;
    setSaving(true);setFeedback('');
    try{await deleteAnalysis(result.id);onFinish();}
    catch(error){setFeedback(error instanceof Error?error.message:'No se pudo eliminar.');setSaving(false);}
  }
  const [mode, setMode] = useState<Mode>("overlay");
  const [opacity, setOpacity] = useState(80);
  const overlaySrc = `data:image/jpeg;base64,${result.overlay_jpg_b64}`;
  const a = result.areas_px as Record<string, number>;
  const useful = result.availability_basis === 'useful_fronts';
  const evaluable = result.status === "evaluable";
  const usefulPixels = (a.occupied ?? 0) + (a.empty ?? 0) + (a.unknown ?? 0);
  const showProductCoverage = !useful && usefulPixels > 0 &&
    (result.alert_product_coverage_pct !== undefined || result.upper_free_surface_pct !== undefined);
  const productCoverage = result.alert_product_coverage_pct ?? (100 * (a.occupied ?? 0) / usefulPixels);
  const usefulSurface = (["occupied", "empty", "unknown"] as const).map(key => ({
    key,
    pct: 100 * (a[key] ?? 0) / usefulPixels,
    label: { occupied: "Producto detectado", empty: "Vacío estimado", unknown: "Sin clasificar" }[key],
  }));
  const formatCoverage = (value: number) => value.toLocaleString("es-CL", {
    minimumFractionDigits: 2, maximumFractionDigits: 2,
  });

  const rows: { key: Semantic; px: number }[] = [
    { key: "occupied", px: a.occupied ?? 0 },
    { key: "empty", px: a.empty ?? 0 },
    { key: "excluded", px: a.excluded ?? 0 },
    { key: "structural", px: a.structural ?? 0 },
    { key: "unknown", px: a.unknown ?? 0 },
  ];

  const percentages = surfacePercentageTenths(rows.map(row=>row.px));
  const formatPercent = (tenths:number) => (tenths/10).toLocaleString("es-CL", {minimumFractionDigits:1,maximumFractionDigits:1});

  return (
    <div className="results">
      <header className="res-head">
        <button className="btn ghost" onClick={onBack}><ArrowLeft size={16} /> Volver</button>
        <div className="res-title">
          <h1>{result.filename || `Análisis #${result.id}`}</h1>
          <div className="res-meta">
            <span><Clock size={14} /> {result.created_at ? new Date(result.created_at).toLocaleString("es-CL") : "Recién analizado"}</span>
          </div>
        </div>
        <a className="btn primary" href={reportUrl(result.id)}><Download size={16} /> Descargar PDF</a>
      </header>

      <section className="panel report-metadata"><div className="report-metadata-heading"><h2>Datos de la captura</h2><div>{canWrite && <button type="button" className="btn ghost sm" disabled={saving || editing} onClick={()=>{setMetadata({pasillo:result.pasillo,reference:result.reference??'',observations:result.observations??''});setFeedback('');setEditing(true);}}>Editar datos</button>}{canDelete && <button type="button" className="btn danger-ghost sm" disabled={saving} onClick={removeReport}>Eliminar reporte</button>}</div></div>
        <p>Estantes indicados: {result.requested_shelves ?? 'Automático'}</p><p>Captura: {result.capture_date?new Date(result.capture_date).toLocaleString('es-CL'):'No registrada'}</p>
        {editing?<form className="report-metadata-form" onSubmit={saveMetadata}>
          <label className="field">Pasillo<input required maxLength={50} value={metadata.pasillo} disabled={saving} onChange={e=>setMetadata({...metadata,pasillo:e.target.value})} /></label>
          <label className="field">Referencia (opcional)<input maxLength={100} value={metadata.reference} disabled={saving} onChange={e=>setMetadata({...metadata,reference:e.target.value})} /><small>{metadata.reference.length}/100 caracteres</small></label>
          <label className="field">Observaciones (opcional)<textarea maxLength={500} rows={4} value={metadata.observations} disabled={saving} onChange={e=>setMetadata({...metadata,observations:e.target.value})} /><small>{metadata.observations.length}/500 caracteres</small></label>
          <p className="muted small">Estos cambios no modifican las detecciones, porcentajes ni umbrales del análisis.</p>
          <div className="report-selection-actions"><button className="btn ghost" type="button" disabled={saving} onClick={()=>{setEditing(false);setFeedback('');}}>Cancelar</button><button className="btn primary" type="submit" disabled={saving || !metadata.pasillo.trim() || (metadata.pasillo===result.pasillo && metadata.reference===(result.reference??'') && metadata.observations===(result.observations??''))}>{saving?'Guardando…':'Guardar cambios'}</button></div>
        </form>:<><p>Pasillo: {result.pasillo}</p><p>Referencia: {result.reference||'Sin referencia'}</p><p style={{whiteSpace:'pre-wrap',overflowWrap:'anywhere'}}>Observaciones: {result.observations||'Sin observaciones'}</p></>}
        {feedback && <p role="status">{feedback}</p>}
      </section>
      {review && canWrite && <ReviewPanel analysisId={result.id} />}
      {result.warnings.length > 0 && (
        <section className="warnings" aria-label="Advertencias">
          {result.warnings.map((w) => <p key={w}>⚠ {w}</p>)}
        </section>
      )}

      <div className="res-grid">
        <section className="panel hero-metric">
          <span className={`status-pill st-${result.criticality}`}>{CRIT_TEXT[result.criticality]}</span>
          {showProductCoverage ? (
            <>
              <p className="metric-label">Producto detectado en la región útil</p>
              <p className="metric-value">{formatCoverage(productCoverage)} %</p>
              <div className="split-bar" role="img" aria-label={usefulSurface.map(({ label, pct }) => `${label} ${formatCoverage(pct)} %`).join(", ")}>
                {usefulSurface.map(({ key, pct }) => (
                  <span key={key} style={{ width: `${pct}%`, background: SEMANTIC[key].color }} />
                ))}
              </div>
              <div className="split-legend">
                {usefulSurface.map(({ key, label, pct }) => (
                  <span key={key}><i style={{ background: SEMANTIC[key].color }} /> {label} {formatCoverage(pct)} %</span>
                ))}
              </div>
              <p className="muted small">La región útil deja fuera las estructuras y las zonas excluidas.</p>
              <p className="muted small">
                {result.alert_basis === "product_coverage_review" ? "Alerta: revisar góndola." : result.alert ? "Alerta de baja disponibilidad." : "Sin alerta automática."}
                {" "}Umbral crítico: {result.threshold} %.
              </p>
              {result.availability_pct !== null && (
                <p className="formula">Ocupación entre las zonas clasificadas: <strong>{formatCoverage(result.availability_pct)} %</strong>. Se calcula solo con el verde y el rojo.</p>
              )}
            </>
          ) : evaluable ? (
            <>
              <p className="metric-label">{useful ? "Ocupación útil estimada" : "Disponibilidad de superficie"}</p>
              <p className="metric-value">{result.availability_pct}%</p>
              <div className="split-bar" role="img" aria-label={`Ocupado ${result.availability_pct}%, vacío ${result.empty_pct}%`}>
                <span style={{ width: `${result.availability_pct}%`, background: SEMANTIC.occupied.color }} />
                <span style={{ width: `${result.empty_pct}%`, background: SEMANTIC.empty.color }} />
              </div>
              <div className="split-legend">
                <span><i style={{ background: SEMANTIC.occupied.color }} /> Ocupado {result.availability_pct}%</span>
                <span><i style={{ background: SEMANTIC.empty.color }} /> {useful ? "Capacidad libre" : "Vacío"} {result.empty_pct}%</span>
              </div>
              <p className="muted small">Umbral de alerta: {result.threshold} %. {result.low_threshold !== undefined && `Suficiente desde ${result.low_threshold} %. `} {result.alert ? "Igual o por debajo del umbral: se genera alerta." : "Por encima del umbral: sin alerta."}</p>
            </>
          ) : (
            <>
              <p className="metric-value muted">Sin área evaluable</p>
              <p className="muted">No hay superficie que el sistema pueda medir con los datos actuales, así que no se muestra una disponibilidad. Revisa las zonas marcadas o la calidad de la foto.</p>
            </>
          )}
          {!showProductCoverage && <p className="formula">{useful
            ? "Ocupación útil = frentes ocupados ÷ (frentes ocupados + espacios donde cabe otro producto) × 100. Es una estimación visible; no garantiza capacidad física en profundidad."
            : "Disponibilidad: porcentaje ocupado de la superficie evaluable. Se calcula como ocupado ÷ (ocupado + vacío) × 100. Las zonas excluidas, estructurales y desconocidas no entran en este cálculo."}</p>}
          {useful && <><p className="muted small">Frentes ocupados: {result.useful_occupied_fronts}. Espacios útiles para reponer: {result.useful_free_fronts}. Las posiciones útiles se marcan en rojo.</p><p className="muted small">Superficie ocupada: {result.surface_availability_pct} %. Superficie vacía: {result.surface_empty_pct} %. Las separaciones pequeñas pueden ser superficie vacía sin admitir otro producto.</p></>}
        </section>

        <section className="panel">
          <div className="panel-head"><h2>Distribución de superficies</h2></div>
          <table className="areas">
            <thead>
              <tr><th>Categoría</th><th className="num">Píxeles</th><th className="num">% del total</th><th>Área evaluable</th></tr>
            </thead>
            <tbody>
              {rows.map(({ key, px }, index) => (
                <tr key={key}>
                  <td><i className="sw" style={{ background: SEMANTIC[key].color }} /> {SEMANTIC[key].label}</td>
                  <td className="num">{px.toLocaleString("es-CL")}</td>
                  <td className="num">{formatPercent(percentages[index])} %</td>
                  <td>{SEMANTIC[key].counts ? "Sí" : "No"}</td>
                </tr>
              ))}
            </tbody>
          </table>
          <p className="muted small">Los porcentajes de esta tabla se calculan sobre toda la región marcada.</p>
        </section>
      </div>



      <section className="panel">
        <div className="viewer-bar">
          <div className="seg" role="tablist" aria-label="Modo de visualización">
            <button role="tab" aria-selected={mode === "overlay"} className={mode === "overlay" ? "on" : ""} onClick={() => setMode("overlay")}><Layers size={15} /> Resultado</button>
            <button role="tab" aria-selected={mode === "original"} className={mode === "original" ? "on" : ""} onClick={() => setMode("original")} disabled={!originalUrl}><ImageIcon size={15} /> Original</button>
            <button role="tab" aria-selected={mode === "side"} className={mode === "side" ? "on" : ""} onClick={() => setMode("side")} disabled={!originalUrl}><Columns2 size={15} /> Lado a lado</button>
          </div>
          {mode === "overlay" && originalUrl && (
            <label className="opacity">
              <Eye size={15} /> Opacidad
              <input type="range" min={10} max={100} value={opacity} onChange={(e) => setOpacity(Number(e.target.value))} />
              <span>{opacity}%</span>
            </label>
          )}
        </div>

        <div className="viewer">
          {mode === "overlay" && (
            <div className="layered">
              {originalUrl && <img src={originalUrl} alt="Fotografía original" />}
              <img src={overlaySrc} alt="Resultado del análisis" style={{ opacity: originalUrl ? opacity / 100 : 1 }} />
            </div>
          )}
          {mode === "original" && originalUrl && <img src={originalUrl} alt="Fotografía original" />}
          {mode === "side" && originalUrl && (
            <div className="side">
              <figure><img src={originalUrl} alt="Original" /><figcaption>Original</figcaption></figure>
              <figure><img src={overlaySrc} alt="Resultado" /><figcaption>Resultado</figcaption></figure>
            </div>
          )}
          {!originalUrl && <p className="muted small">La fotografía original solo está disponible mientras la sesión esté abierta. Para análisis anteriores se muestra el resultado con colores.</p>}
        </div>

        <ul className="legend" aria-label="Leyenda de colores">
          {(Object.keys(SEMANTIC) as Semantic[]).map((k) => (
            <li key={k}><i style={{ background: SEMANTIC[k].color }} /> {SEMANTIC[k].label}{SEMANTIC[k].counts ? "" : " (no cuenta)"}</li>
          ))}
        </ul>
      </section>
      {result.conteo && <ShelfRows conteo={result.conteo} />}
      <footer className="panel result-completion">
        <div><strong>Análisis guardado en Reportes</strong><p className="muted small">Puedes volver a consultar este resultado y descargar su PDF desde allí.</p></div>
        <div className="result-completion-actions">{canWrite && <button type="button" className="btn ghost" onClick={onNew}>Nuevo análisis</button>}<button type="button" className="btn primary" onClick={onFinish}>Finalizar y ver reportes →</button></div>
      </footer>
    </div>
  );
}
