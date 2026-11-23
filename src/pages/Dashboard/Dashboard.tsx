import { useSession } from '../../services/session';
import { hasPermission } from '../../services/permissions';
import { useEffect, useState } from 'react';
import { apiJson } from '../../services/http';
import type { Criticality, HistoryItem } from '../../features/analysis/types';
import '../../components/DashboardCharts/DashboardCharts.css';
import '../../components/GondolaTable/GondolaTable.css';
import './Dashboard.css';

const states: {key:Criticality; label:string; tone:string; color:string}[] = [
  {key:'aceptable',label:'Aceptable',tone:'normal',color:'#159568'},
  {key:'baja',label:'Baja',tone:'warning',color:'#e3a02d'},
  {key:'critica',label:'Crítica',tone:'critical',color:'#dc5963'},
  {key:'no_evaluable',label:'Sin evaluar',tone:'unevaluable',color:'#bac7d6'},
];
const resultLink = (item: HistoryItem) => item.origin === 'historical_test' ? `/api/dashboard/historical/${item.legacy_id}/report.pdf` : `#/history?result=${item.id}`;
const recordLabel = (item: HistoryItem) => item.origin === 'historical_test' ? `H-${item.legacy_id}` : `#${item.id}`;
export default function Dashboard() {
  const user = useSession();
  const canAnalyze = !!user && hasPermission(user.role, 'analysis.execute');
  const [includeHistorical,setIncludeHistorical] = useState(true);
  const [items,setItems] = useState<HistoryItem[] | null>(null);
  const [error,setError] = useState('');
  const [retry,setRetry] = useState(0);
  const [search,setSearch] = useState('');
  const [filter,setFilter] = useState('all');
  const [page,setPage] = useState(0);
  const [period,setPeriod] = useState('all');
  const [asOf,setAsOf] = useState(() => Date.now());
  useEffect(() => {
    let active=true;
    const refresh=()=>apiJson<HistoryItem[]>('/api/dashboard/history?limit=200').then(value=>{if(active){setItems(value);setAsOf(Date.now());setError('');}}).catch(()=>{if(active)setError('No se pudo cargar el historial del servidor.');});
    refresh();window.addEventListener('focus',refresh);
    return()=>{active=false;window.removeEventListener('focus',refresh);};
  },[retry]);
  const historicalCount = items?.filter(item=>item.origin==='historical_test').length ?? 0;
  const rows=(items??[]).filter(item=>includeHistorical || item.origin!=='historical_test');
  const evaluable = rows.filter((item): item is HistoryItem & { availability_pct: number } => item.criticality !== 'no_evaluable' && typeof item.availability_pct === 'number' && Number.isFinite(item.availability_pct));
  const average = evaluable.length ? evaluable.reduce((sum,item)=>sum+item.availability_pct,0)/evaluable.length : null;
  const latest = rows.slice().sort((a,b)=>Date.parse(b.created_at)-Date.parse(a.created_at))[0];
  const cards=[
    {label:'Análisis disponibles',value:rows.length,tone:'blue',description:'Hasta las últimas 200 capturas guardadas',compact:false},
    {label:'Disponibilidad promedio',value:average === null ? '—' : `${average.toFixed(2)} %`,tone:'green',description:`Media simple de ${evaluable.length} capturas evaluables disponibles`,compact:false},
    {label:'Disponibilidad crítica',value:rows.filter(item=>item.criticality==='critica').length,tone:'red',description:'Capturas clasificadas como críticas al analizarse',compact:false},
    {label:'Último análisis',value:latest ? new Date(latest.created_at).toLocaleString('es-CL',{dateStyle:'medium',timeStyle:'short'}) : '—',tone:'yellow',description:latest ? latest.filename : 'Todavía no hay capturas guardadas',compact:true},
  ];
  const cutoff = period === 'all' ? -Infinity : asOf-Number(period)*86400000;
  const timeline = evaluable.filter(item=>Number.isFinite(Date.parse(item.created_at)) && Date.parse(item.created_at)>=cutoff).slice().sort((a,b)=>Date.parse(a.created_at)-Date.parse(b.created_at));
  const firstTime = timeline.length ? Date.parse(timeline[0].created_at) : 0;
  const lastTime = timeline.length ? Date.parse(timeline[timeline.length-1].created_at) : 0;
  const chartX = (index:number) => timeline.length <= 1 ? 317.5 : 55+index/(timeline.length-1)*525;
  const chartY = (value:number) => 190-value*1.5;
  const filtered=rows.filter(item=>(`${item.id} ${item.filename}`).toLowerCase().includes(search.trim().toLowerCase()) && (filter==='all'|| (filter==='alerts'?Boolean(item.alert):item.criticality===filter)));
  const pages=Math.max(1,Math.ceil(filtered.length/5));
  const currentPage=Math.min(page,pages-1);
  const recentEvaluable=rows.filter(item=>typeof item.availability_pct==='number' && Number.isFinite(item.availability_pct)).slice(0,5);
  const circumference=2*Math.PI*74;
  const distribution=states.map((state,index)=>({...state,count:rows.filter(item=>item.criticality===state.key).length,offset:states.slice(0,index).reduce((sum,previous)=>sum+rows.filter(item=>item.criticality===previous.key).length,0)}));
  return <section className="dashboard-page">
    <div className="dashboard-intro"><div><span className="dashboard-eyebrow">RESUMEN OPERATIVO</span><h2>Estado general</h2><p>Información registrada y resultados de los análisis de REGOVA.</p></div><div className="dashboard-intro-actions">{canAnalyze && <a className="dashboard-new-analysis" href="#/analysis">＋ Nuevo análisis</a>}</div></div>
    {error && <div className="dashboard-feedback" role="alert">{error} <button type="button" className="gondola-detail-button" onClick={()=>setRetry(value=>value+1)}>Reintentar</button></div>}
    {historicalCount > 0 && <p className="dashboard-indicator-description"><label><input type="checkbox" checked={includeHistorical} onChange={e=>{setIncludeHistorical(e.target.checked);setPage(0);}} /> Incluir historial de prueba ({historicalCount} registros)</label> · Se conservan fechas y resultados originales; sus alertas no son tareas actuales. Los reportes de la sección Reportes corresponden a análisis nuevos.</p>}
    {!items && !error && <p role="status">Cargando análisis…</p>}
    <div className="dashboard-indicators">{cards.map(card=><article key={card.label} className={`dashboard-indicator dashboard-indicator--${card.tone}`}><div className="dashboard-indicator-top"><h3>{card.label}</h3><span className="dashboard-indicator-signal" aria-hidden="true" /></div><strong className={`dashboard-indicator-value ${card.compact ? 'dashboard-indicator-date' : ''}`}>{items?card.value:'—'}</strong><p className="dashboard-indicator-description">{card.description}</p></article>)}</div>
    <div className="dashboard-charts dashboard-overview-charts">
    <section className="dashboard-chart-card dashboard-temporal" aria-labelledby="dashboard-temporal-title">
      <div className="dashboard-temporal-heading"><div className="dashboard-chart-heading"><h3 id="dashboard-temporal-title">Evolución de la disponibilidad</h3><p>Cada punto es un análisis evaluable, del más antiguo al más reciente. Separación uniforme por captura.</p></div><label>Período<select value={period} onChange={event=>setPeriod(event.target.value)}><option value="7">Últimos 7 días</option><option value="30">Últimos 30 días</option><option value="90">Últimos 90 días</option><option value="all">Historial disponible</option></select></label></div>
      {timeline.length ? <><svg className="dashboard-temporal-chart" viewBox="0 0 630 240" role="group" aria-label={`Disponibilidad de ${timeline.length} capturas evaluables`}>
        {[0,25,50,75,100].map(value=><g key={value}><line x1="55" x2="580" y1={chartY(value)} y2={chartY(value)} stroke="#dfe8f3" strokeDasharray="4 5" /><text x="8" y={chartY(value)+4}>{value} %</text></g>)}
        <polyline fill="none" stroke="#087bff" strokeWidth="2" points={timeline.map((item,index)=>`${chartX(index)},${chartY(item.availability_pct)}`).join(' ')} />
        {timeline.map((item,index)=><a key={item.id} href={resultLink(item)} aria-label={`Análisis ${item.id}, ${item.filename}, ${item.availability_pct.toFixed(2)} %, ${new Date(item.created_at).toLocaleString('es-CL')}`}><circle cx={chartX(index)} cy={chartY(item.availability_pct)} r="3" fill="white" stroke="#087bff" strokeWidth="1.5"><title>{recordLabel(item)} · {item.filename} · {item.availability_pct.toFixed(2)} % · {new Date(item.created_at).toLocaleString('es-CL')}</title></circle></a>)}
        <text x="55" y="222">{new Date(firstTime).toLocaleDateString('es-CL')}</text>{firstTime!==lastTime && <text x="580" y="222" textAnchor="end">{new Date(lastTime).toLocaleDateString('es-CL')}</text>}
      </svg>{timeline.length===1 && <p className="dashboard-chart-empty">Hay una sola captura evaluable en este período; se necesitan dos para comparar.</p>}</> : <p className="dashboard-temporal-empty">{items?'No hay capturas evaluables en este período.':'Cargando capturas…'}</p>}
      <p className="dashboard-temporal-note">Se muestran hasta 200 análisis recientes. Pueden corresponder a lugares distintos: la curva y el promedio describen las capturas, no la evolución de una misma góndola ni la disponibilidad de toda la tienda. Las capturas sin evaluar no se cuentan como 0 %.</p>
    </section>
      <article className="dashboard-chart-card"><div className="dashboard-chart-heading"><h3>Estado de los análisis</h3><p>Clasificación guardada al procesar cada fotografía; incluye capturas sin evaluar.</p></div><div className="dashboard-donut-layout"><div className="dashboard-donut-container"><svg className="dashboard-donut" viewBox="0 0 200 200" role="img" aria-label={items?`Distribución de ${rows.length} análisis: ${distribution.map(state=>`${state.label}: ${state.count}`).join(', ')}`:'Cargando distribución de análisis'}><circle cx="100" cy="100" r="74" fill="none" stroke="#e8eef6" strokeWidth="22" />{distribution.map(state=><circle key={state.key} cx="100" cy="100" r="74" fill="none" stroke={state.color} strokeWidth="22" strokeDasharray={`${rows.length?state.count/rows.length*circumference:0} ${circumference}`} strokeDashoffset={rows.length?-state.offset/rows.length*circumference:0} transform="rotate(-90 100 100)" />)}</svg><div className="dashboard-donut-center" aria-hidden="true"><strong>{items?rows.length:'—'}</strong><span>Análisis</span></div></div><div className="dashboard-donut-legend">{distribution.map(state=><div className="dashboard-legend-item" key={state.key}><span className="dashboard-legend-dot" style={{backgroundColor:state.color}} /><span>{state.label}</span><strong>{items?state.count:'—'}</strong></div>)}</div></div></article>
    </div>
    <section className="gondola-table-section" aria-labelledby="dashboard-captures-title">
      <div className="gondola-table-header"><div><h3 id="dashboard-captures-title">Estado de las capturas</h3><p>Últimos análisis guardados. Consulta el resultado y sus detecciones.</p></div><div className="gondola-table-controls"><input type="search" aria-label="Buscar captura por archivo o ID" placeholder="Buscar captura…" value={search} onChange={e=>{setSearch(e.target.value);setPage(0);}} /><select aria-label="Filtrar capturas por estado" value={filter} onChange={e=>{setFilter(e.target.value);setPage(0);}}><option value="all">Todos los estados</option><option value="alerts">Con alertas</option>{states.map(state=><option key={state.key} value={state.key}>{state.label}</option>)}</select></div></div>
      <div className="gondola-table-scroll"><table className="gondola-table"><thead><tr><th>Análisis</th><th>Fotografía</th><th>Estado</th><th>Disponibilidad estimada</th><th>Alertas</th><th>Fecha de análisis</th><th>Resultado</th></tr></thead><tbody>
        {!filtered.length?<tr><td colSpan={7} className="gondola-table-empty">{!items?'Esperando datos del servidor…':rows.length?'No hay capturas que coincidan con estos filtros.':'Todavía no hay análisis guardados. Comienza cargando una fotografía.'}</td></tr>:filtered.slice(currentPage*5,currentPage*5+5).map(item=>{const state=states.find(value=>value.key===item.criticality);return <tr key={item.id}><td className="gondola-table-code">{recordLabel(item)}{item.origin==='historical_test' && <small style={{display:'block'}}>Histórico de prueba</small>}</td><td>{item.filename}</td><td><span className={`gondola-state gondola-state--${state?.tone??'unassessed'}`}>{state?.label??'Sin evaluar'}</span></td><td>{item.availability_pct===null?'—':`${item.availability_pct.toFixed(1)} %`}</td><td><span className={`gondola-alert-count ${item.alert?'has-alerts':''}`}>{item.criticality==='no_evaluable'?'—':item.alert?'Con alerta':'Sin alertas'}</span></td><td>{new Date(item.created_at).toLocaleString('es-CL')}</td><td><a className="gondola-detail-button dashboard-detail-link" href={resultLink(item)}>{item.origin==='historical_test'?'Ver PDF histórico':'Ver resultado'}</a></td></tr>;})}
      </tbody></table></div>
      <div className="gondola-table-footer dashboard-table-footer"><span>{filtered.length?`${currentPage*5+1}–${Math.min(currentPage*5+5,filtered.length)} de ${filtered.length}`:'0 capturas'} · Hasta 200 análisis recientes</span><div><button type="button" className="gondola-detail-button" disabled={currentPage===0} onClick={()=>setPage(currentPage-1)}>Anterior</button><button type="button" className="gondola-detail-button" disabled={currentPage+1>=pages} onClick={()=>setPage(currentPage+1)}>Siguiente</button><a href="#/history">Ver reportes →</a></div></div>
    </section>
    <section className="dashboard-charts dashboard-capture-bars" aria-label="Disponibilidad de capturas recientes">
      <article className="dashboard-chart-card"><div className="dashboard-chart-heading"><h3>Disponibilidad estimada por captura</h3><p>Últimas cinco fotografías evaluables; cada imagen se analiza de forma independiente.</p></div><div className="dashboard-zone-list">{!recentEvaluable.length?<p className="dashboard-chart-empty">{items?'No hay estimaciones disponibles todavía.':'Cargando estimaciones…'}</p>:recentEvaluable.map(item=><div className="dashboard-zone" key={item.id}><div className="dashboard-zone-label"><a href={resultLink(item)}>{recordLabel(item)} · {item.filename}</a><strong>{item.availability_pct!.toFixed(1)} %</strong></div><div className="dashboard-zone-track" role="progressbar" aria-label={`Disponibilidad estimada de la captura ${item.id}`} aria-valuenow={item.availability_pct!} aria-valuemin={0} aria-valuemax={100}><div className="dashboard-zone-fill" style={{width:`${Math.max(0,Math.min(100,item.availability_pct!))}%`}} /></div></div>)}</div></article>

    </section>
  </section>;
}
