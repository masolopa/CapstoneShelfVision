import { useEffect, useState } from 'react';
import { apiJson, jsonBody } from '../../services/http';
import type { User } from '../../services/auth';
import './Alerts.css';

type Alert = { id: number; analisis_id: number; motivo: string; estado: string; pasillo: string; referencia: string; responsable: string | null; motivo_cierre?: string | null; revisado_por?: string | null; cerrada_en?: string | null };
const states = [{ value: 'pendiente', label: 'Pendientes' }, { value: 'en_atencion', label: 'En atención' }, { value: 'atendida', label: 'Atendidas' }, { value: 'descartada', label: 'No procede' }];
const labels: Record<string, string> = { pendiente: 'Pendiente', en_atencion: 'En atención', atendida: 'Atendida', descartada: 'No procede' };

export default function Alerts({ user }: { user: User }) {
  const [items, setItems] = useState<Alert[]>([]);
  const [error, setError] = useState('');
  const [busy, setBusy] = useState<number | null>(null);
  const [loading, setLoading] = useState(true);
  const [reload, setReload] = useState(0);
  const [filter, setFilter] = useState('todas');
  const [search, setSearch] = useState('');
  const [discardId, setDiscardId] = useState<number | null>(null);
  const [discardReason, setDiscardReason] = useState('');
  const canDiscard = (item: Alert) => ['pendiente', 'en_atencion'].includes(item.estado)
    && (['admin_principal', 'admin_local', 'supervisor'].includes(user.role)
      || (user.role === 'reponedor' && (item.responsable === null || item.responsable === user.id)));
  useEffect(() => {
    let active = true;
    apiJson<Alert[]>('/api/alerts').then(value => { if (active) { setItems(value); setError(''); } })
      .catch(e => { if (active) setError(e.message); }).finally(() => { if (active) setLoading(false); });
    return () => { active = false; };
  }, [reload]);
  async function attend(alert: Alert, estado: string, motivo?: string) {
    setBusy(alert.id); setError('');
    try {
      await apiJson(`/api/alerts/${alert.id}`, jsonBody(motivo === undefined ? { estado } : { estado, motivo }, 'PATCH'));
      setDiscardId(null); setDiscardReason('');
      setItems(previous => previous.map(item => item.id === alert.id ? { ...item, estado, responsable: estado === 'descartada' ? item.responsable : user.id, ...(estado === 'descartada' ? {motivo_cierre: motivo, revisado_por: user.id, cerrada_en: new Date().toISOString()} : {}) } : item));
      setReload(v => v + 1);
    } catch (e) { setError(e instanceof Error ? e.message : 'No se pudo actualizar la alerta.'); }
    finally { setBusy(null); }
  }
  const visible = items.filter(item => (filter === 'todas' || item.estado === filter) && `${item.pasillo} ${item.referencia} ${item.responsable ?? ''}`.toLocaleLowerCase('es').includes(search.trim().toLocaleLowerCase('es')));
  return <section className="alerts-page" aria-labelledby="alerts-title">
    <header className="alerts-intro"><div><span className="alerts-eyebrow">SEGUIMIENTO DEL LOCAL</span><h2 id="alerts-title">Alertas de reposición</h2><p>Revisa la evidencia y sigue el avance de cada reposición.</p></div><span className="alerts-local">Operación del local</span></header>
    <div className="alerts-summary" aria-label="Resumen de alertas">
      {states.map(state => <div key={state.value} className={`alerts-stat alerts-stat--${state.value}`}><span>{state.label}</span><strong>{loading ? '—' : items.filter(item => item.estado === state.value).length}</strong><small>{state.value === 'pendiente' ? 'Por iniciar' : state.value === 'en_atencion' ? 'Reposición en curso' : state.value === 'descartada' ? 'Cerrada sin reposición' : 'Atención completada'}</small></div>)}
    </div>
    <div className="alerts-toolbar"><div className="alerts-filters" role="group" aria-label="Filtrar por estado">{[{ value: 'todas', label: 'Todas' }, ...states].map(state => <button type="button" key={state.value} aria-pressed={filter === state.value} onClick={() => setFilter(state.value)}>{state.label}</button>)}</div><label className="alerts-search"><span className="alerts-sr-only">Buscar por pasillo, referencia o responsable</span><input type="search" placeholder="Buscar pasillo o referencia…" value={search} onChange={e => setSearch(e.target.value)} /></label></div>
    {error && <div className="alerts-error" role="alert"><p>{error}</p><button type="button" onClick={() => setReload(v => v + 1)}>Volver a intentar</button></div>}
    {loading ? <p className="alerts-empty" role="status">Cargando alertas…</p> : <>
      <p className="alerts-count" role="status">{visible.length} de {items.length} alertas</p>
      {!visible.length && !error && <div className="alerts-empty"><h3>{items.length ? 'No hay coincidencias' : 'Sin alertas registradas'}</h3><p>{items.length ? 'Prueba con otro estado o término de búsqueda.' : 'Aquí aparecerán los análisis que generen una alerta de reposición.'}</p></div>}
      <div className="alerts-grid">{visible.map(item => <article key={item.id} className={`alert-card alert-card--${states.some(state => state.value === item.estado) ? item.estado : 'pendiente'}`}>
        <header className="alert-card-header"><span className="alert-card-id">ALERTA #{item.id}</span><span className="alert-badge"><span aria-hidden="true" />{labels[item.estado] ?? item.estado}</span></header>
        <h3>Pasillo {item.pasillo}</h3><p className="alert-reference">{item.referencia || 'Sin referencia adicional'}</p>
        <div className="alert-reason"><span>Motivo de la alerta</span><p>{item.motivo}</p></div>
        <dl className="alert-details"><div><dt>Responsable</dt><dd>{item.responsable ?? 'Sin asignar'}</dd></div><div><dt>Análisis de origen</dt><dd>#{item.analisis_id}</dd></div></dl>
        {item.estado === 'descartada' && <div className="alert-reason"><span>Motivo de No procede</span><p>{item.motivo_cierre || 'Sin motivo registrado'}</p><p>Revisó: {item.revisado_por || 'Sin registro'}{item.cerrada_en && ` · ${new Date(item.cerrada_en).toLocaleString('es-CL')}`}</p></div>}
        {discardId === item.id && <form className="alert-discard-form" onSubmit={event => {event.preventDefault(); if (discardReason.trim().length >= 3) void attend(item, 'descartada', discardReason.trim());}}>
          <label htmlFor={`discard-${item.id}`}>Motivo de No procede</label>
          <textarea id={`discard-${item.id}`} required minLength={3} maxLength={1000} value={discardReason} onChange={event => setDiscardReason(event.target.value)} placeholder="Ejemplo: producto no apilable; el espacio no permite reposición." disabled={busy !== null} />
          <p>Se guardarán el motivo, tu usuario y la fecha. La alerta quedará cerrada sin marcarse como atendida.</p>
          <div><button type="submit" disabled={busy !== null || discardReason.trim().length < 3}>Confirmar No procede</button><button type="button" disabled={busy !== null} onClick={() => {setDiscardId(null);setDiscardReason('');}}>Cancelar</button></div>
        </form>}
        <footer className="alert-actions"><a href={`#/history?result=${item.analisis_id}`}>Ver evidencia y reporte <span aria-hidden="true">↗</span></a>
          {user.role === 'reponedor' && ['pendiente', 'en_atencion'].includes(item.estado) && <button type="button" disabled={busy !== null || (item.responsable !== null && item.responsable !== user.id)} onClick={() => attend(item, item.estado === 'pendiente' ? 'en_atencion' : 'atendida')}>{busy === item.id ? 'Guardando…' : item.estado === 'pendiente' ? 'Tomar reposición' : 'Marcar como atendida'}</button>}
          {canDiscard(item) && discardId !== item.id && <button aria-label="Marcar como No procede" type="button" disabled={busy !== null} onClick={() => {setDiscardId(item.id);setDiscardReason('');}}>No procede</button>}
        </footer>
      </article>)}</div>
    </>}
  </section>;
}
