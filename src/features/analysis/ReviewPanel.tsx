import { useEffect, useRef, useState } from 'react';
import { createReview, getReviews, type ReviewDecision, type SavedReview } from './api';
import './ReviewPanel.css';

const labels = { confirmado: 'Confirmado', corregido: 'Corregido', descartado: 'Descartado' };
export function ReviewPanel({ analysisId }: { analysisId: number }) {
  const [reviews, setReviews] = useState<SavedReview[]>([]);
  const [decision, setDecision] = useState<ReviewDecision>('confirmado');
  const [description, setDescription] = useState('');
  const [percentage, setPercentage] = useState('');
  const [comment, setComment] = useState('');
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [loadError, setLoadError] = useState('');
  const [error, setError] = useState('');
  const [success, setSuccess] = useState('');
  const [retry, setRetry] = useState(0);
  const submitting = useRef(false);
  useEffect(() => {
    let active = true;
    setLoading(true);setLoadError('');
    getReviews(analysisId).then(value => { if(active)setReviews(value); })
      .catch(e => { if(active)setLoadError(e instanceof Error ? e.message : 'No se pudieron cargar las revisiones.'); })
      .finally(() => { if(active)setLoading(false); });
    return () => { active = false; };
  }, [analysisId, retry]);
  async function save(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if(submitting.current)return;
    setError('');setSuccess('');
    if(decision === 'corregido' && description.trim().length < 3) { setError('Describe la corrección con al menos 3 caracteres.');return; }
    const number = Number(percentage);
    if(decision === 'corregido' && percentage !== '' && (!Number.isFinite(number) || number < 0 || number > 100)) { setError('La disponibilidad debe estar entre 0 y 100.');return; }
    submitting.current = true;setSaving(true);
    try {
      await createReview(analysisId, {decision, comentario:comment.trim() || null, correccion:decision === 'corregido' ? {descripcion:description.trim(), ...(percentage !== '' ? {availability_pct:number} : {})} : {}});
      setSuccess('Revisión guardada. La predicción original y el estado de las alertas se conservan.');
      setComment('');setDescription('');setPercentage('');setDecision('confirmado');setRetry(value=>value+1);
    } catch(e) { setError(e instanceof Error ? e.message : 'No se pudo guardar la revisión.'); }
    finally { submitting.current=false;setSaving(false); }
  }
  return <section className="panel review-panel" aria-labelledby="review-title">
    <h2 id="review-title">Revisión del resultado</h2>
    <p>Contrasta las imágenes y métricas del análisis con tu evaluación. La revisión se registra por separado; no reemplaza la predicción ni cierra alertas.</p>
    <form onSubmit={save}>
      <fieldset disabled={saving}>
        <label className="field">Decisión<select value={decision} onChange={e=>setDecision(e.target.value as ReviewDecision)}>{Object.entries(labels).map(([value,label])=><option key={value} value={value}>{label}</option>)}</select></label>
        {decision === 'corregido' && <>
          <label className="field">Detalle de la corrección<textarea required minLength={3} maxLength={1000} rows={3} value={description} onChange={e=>setDescription(e.target.value)} /></label>
          <label className="field">Disponibilidad corregida (%) — opcional<input type="number" min="0" max="100" step="any" value={percentage} onChange={e=>setPercentage(e.target.value)} /></label>
        </>}
        <label className="field">Comentario (opcional)<textarea maxLength={1000} rows={3} value={comment} onChange={e=>setComment(e.target.value)} /></label>
        <button className="btn primary" type="submit">{saving ? 'Guardando revisión…' : 'Guardar revisión'}</button>
      </fieldset>
    </form>
    {error && <p role="alert">{error}</p>}
    {success && <p role="status">{success}</p>}
    <h3>Revisiones registradas</h3>
    {loading && <p role="status">Cargando revisiones…</p>}
    {loadError && <div role="alert">{loadError} <button type="button" className="btn ghost" onClick={()=>setRetry(value=>value+1)}>Reintentar consulta</button></div>}
    {!loading && !loadError && reviews.length === 0 && <p>Aún no hay revisiones registradas.</p>}
    <ol className="review-list">{reviews.map(item=><li key={item.id}>
      <strong>{labels[item.decision]}</strong> · {item.revisor_nombre} ({item.revisor_codigo}) · {new Date(item.creado_en).toLocaleString('es-CL')}
      {Object.entries(item.correccion).map(([key,value])=><p key={key}>{key === 'descripcion' ? 'Corrección' : key === 'availability_pct' ? 'Disponibilidad corregida (%)' : key}: {typeof value === 'object' ? JSON.stringify(value) : String(value)}</p>)}
      {item.comentario && <p>Comentario: {item.comentario}</p>}
    </li>)}</ol>
  </section>;
}
