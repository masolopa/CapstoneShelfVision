import { useSession } from '../../services/session';
import { useEffect, useMemo, useState } from "react";
import { Search, Eye, Download, ArrowUpDown, Loader2, FileSearch } from "./Glyphs";
import { getHistory, reportUrl, downloadGroupedReports, deleteAnalysis } from "./api";
import type { HistoryItem, Criticality } from "./types";

interface Props {
  mode: "history" | "reports";
  onOpen: (id: number) => void;
}

const LABEL: Record<Criticality, string> = { aceptable: "Aceptable", baja: "Baja", critica: "Crítica", no_evaluable: "No evaluable" };

export function History({ mode, onOpen }: Props) {
  const user = useSession();
  const canDelete = user?.role === 'admin_principal' || user?.role === 'admin_local';
  const [reload,setReload]=useState(0);
  const [page,setPage]=useState(0);
  const [items, setItems] = useState<HistoryItem[] | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [q, setQ] = useState("");
  const [status, setStatus] = useState<"all" | "alerts" | Criticality>("all");
  const [from, setFrom] = useState("");
  const [to, setTo] = useState("");
  const [sort, setSort] = useState<"date" | "availability">("date");
  const [asc, setAsc] = useState(false);
  const [selected,setSelected]=useState<Set<number>>(()=>new Set());
  const [exporting,setExporting]=useState(false);
  const [deleting,setDeleting]=useState<number|null>(null);
  const [exportMessage,setExportMessage]=useState('');
  async function removeReport(item:HistoryItem){
    if(deleting!==null || exporting || !window.confirm(`¿Eliminar el reporte #${item.id} (${item.filename})? Dejará de estar disponible para consulta y descarga. Se conservará una copia interna de respaldo.`))return;
    setDeleting(item.id);setExportMessage('');
    try{await deleteAnalysis(item.id);setItems(previous=>previous?.filter(row=>row.id!==item.id)??[]);setSelected(previous=>{const next=new Set(previous);next.delete(item.id);return next;});setExportMessage(`Reporte #${item.id} eliminado.`);}
    catch(error){setExportMessage(error instanceof Error?error.message:'No se pudo eliminar.');}
    finally{setDeleting(null);}
  }
  function toggle(id:number){setSelected(previous=>{const next=new Set(previous);if(next.has(id))next.delete(id);else next.add(id);return next;});setExportMessage('');}
  async function exportSelected(){
    if(!selected.size || exporting)return;
    setExporting(true);setExportMessage('');
    try{await downloadGroupedReports(orderedIds);setExportMessage('PDF agrupado generado. Se inició la descarga de un único archivo.');}
    catch(error){setExportMessage(error instanceof Error?error.message:'No se pudo generar el PDF.');}
    finally{setExporting(false);}
  }


  useEffect(() => {
    getHistory(200).then(setItems).catch((e) => setError(e instanceof Error ? e.message : "Error al cargar el historial"));
  }, [reload]);

  const rows = useMemo(() => {
    if (!items) return [];
    const f = items.filter((h) => {
      if (q && !`${h.filename??""} ${h.pasillo??""} ${h.reference??""}`.toLowerCase().includes(q.toLowerCase())) return false;
      if (status === "alerts" ? !h.alert : status !== "all" && h.criticality !== status) return false;
      const d = new Date(h.created_at).getTime();
      if (from && d < new Date(`${from}T00:00:00`).getTime()) return false;
      if (to && d > new Date(`${to}T23:59:59.999`).getTime()) return false;
      return true;
    });
    const key = (h: HistoryItem) => (sort === "date" ? new Date(h.created_at).getTime() : h.availability_pct ?? -1);
    f.sort((a, b) => (asc ? key(a) - key(b) : key(b) - key(a)));
    return f;
  }, [items, q, status, from, to, sort, asc]);

  const totalPages=Math.max(1,Math.ceil(rows.length/15));
  const currentPage=Math.min(page,totalPages-1);
  const visibleRows=rows.slice(currentPage*15,currentPage*15+15);
  const allFilteredSelected=rows.length>0 && rows.every(row=>selected.has(row.id));
  const hiddenSelected=[...selected].filter(id=>!rows.some(row=>row.id===id)).length;
  const orderedIds=[...rows.filter(row=>selected.has(row.id)).map(row=>row.id),...[...(items??[])].filter(row=>selected.has(row.id)&&!rows.some(visible=>visible.id===row.id)).map(row=>row.id)];

  function toggleSort(s: "date" | "availability") {
    if (sort === s) setAsc(!asc); else { setSort(s); setAsc(false); }
  }

  if (error) return <div className="panel error-panel" role="alert">{error}<button className="btn ghost" onClick={()=>{setError(null);setReload(value=>value+1);}}>Reintentar</button></div>;
  if (!items) return <div className="panel loading"><Loader2 className="spin" size={18} /> Cargando…</div>;

  const title = "Historial de reportes";
  const hint = "Consulta resultados y descarga reportes individuales o agrupados en un solo PDF.";

  return (
    <div className="history">
      <header className="page-head">
        <div><h1>{title}</h1><p className="muted">{hint}</p></div>
        <span className="count-pill">{rows.length} de {items.length}</span>
      </header>

      <div className="filters panel">
        <label className="field grow">
          <span>Buscar por archivo o referencia</span>
          <div className="input-icon"><Search size={16} /><input value={q} onChange={(e) => {setQ(e.target.value);setPage(0);}} placeholder="Ej. gondola_pasillo3.jpg" /></div>
        </label>
        <label className="field">
          <span>Estado</span>
          <select value={status} onChange={(e) => {setStatus(e.target.value as "all" | "alerts" | Criticality);setPage(0);}}>
            <option value="all">Todos</option><option value="alerts">Con alertas</option>
            <option value="aceptable">Aceptable</option>
            <option value="baja">Baja</option>
            <option value="critica">Crítica</option>
            <option value="no_evaluable">No evaluable</option>
          </select>
        </label>
        <label className="field"><span>Desde</span><input type="date" value={from} onChange={(e) => {setFrom(e.target.value);setPage(0);}} /></label>
        <label className="field"><span>Hasta</span><input type="date" value={to} onChange={(e) => {setTo(e.target.value);setPage(0);}} /></label>
      </div>

      <section className="panel report-selection" aria-label="Selección para PDF agrupado">
        <div><strong>{selected.size} reporte(s) seleccionado(s)</strong><p className="muted small">{hiddenSelected?`${hiddenSelected} están fuera de los filtros actuales. También se incluirán en el PDF.`:'El PDF incluirá portada, resumen y los reportes completos en el orden de la tabla.'}</p></div>
        <div className="report-selection-actions">
          <button type="button" className="btn ghost" disabled={!rows.length || exporting} onClick={()=>{setSelected(previous=>new Set([...previous,...rows.map(row=>row.id)]));setExportMessage('');}}>Seleccionar resultados filtrados ({rows.length})</button>
          <button type="button" className="btn ghost" disabled={!selected.size || exporting} onClick={()=>{setSelected(new Set());setExportMessage('');}}>Limpiar selección</button>
          <button type="button" className="btn primary" disabled={!selected.size || exporting || deleting!==null} onClick={exportSelected}>{exporting?<><Loader2 size={16} className="spin" /> Generando PDF…</>:<><Download size={16} /> Descargar PDF agrupado ({selected.size})</>}</button>
        </div>
        {exportMessage && <p className="report-export-message" role="status">{exportMessage}</p>}
      </section>
      {from && to && from>to && <p className="notice warn" role="alert">La fecha inicial debe ser anterior o igual a la fecha final.</p>}
      {items.length === 0 ? (
        <div className="panel empty-state"><FileSearch size={44} /><h2>Sin análisis todavía</h2><p>Cuando analices una góndola aparecerá aquí.</p></div>
      ) : rows.length === 0 ? (
        <div className="panel empty-state"><FileSearch size={44} /><h2>Ningún resultado con esos filtros</h2><p>Prueba quitando algún filtro.</p></div>
      ) : (
        <div className="panel table-wrap">
          <table className="grid-table">
            <thead>
              <tr>
                <th><input type="checkbox" aria-label="Seleccionar o deseleccionar todos los reportes filtrados" checked={allFilteredSelected} disabled={exporting || !rows.length} onChange={()=>setSelected(previous=>{const next=new Set(previous);rows.forEach(row=>{if(allFilteredSelected)next.delete(row.id);else next.add(row.id);});return next;})} /></th>
                <th>#</th>
                <th><button className="th-btn" onClick={() => toggleSort("date")}>Fecha <ArrowUpDown size={13} /></button></th>
                <th>Archivo</th>
                <th><button className="th-btn" onClick={() => toggleSort("availability")}>Disponibilidad <ArrowUpDown size={13} /></button></th>
                <th>Vacío</th>
                <th>Estado</th>
                <th aria-label="Acciones" />
              </tr>
            </thead>
            <tbody>
              {visibleRows.map((h) => (
                <tr key={h.id} className={selected.has(h.id)?"report-selected":""}>
                  <td><input type="checkbox" aria-label={`Seleccionar reporte ${h.id}: ${h.filename}`} checked={selected.has(h.id)} disabled={exporting} onChange={()=>toggle(h.id)} /></td>
                  <td className="muted">{h.id}</td>
                  <td>{new Date(h.created_at).toLocaleString("es-CL", { dateStyle: "medium", timeStyle: "short" })}</td>
                  <td className="ellipsis" title={h.filename}>{h.filename}{h.reference && <small className="report-reference">{h.reference}</small>}</td>
                  <td className="num">{h.availability_pct !== null ? `${h.availability_pct}%` : "—"}</td>
                  <td className="num">{h.empty_pct !== null ? `${h.empty_pct}%` : "—"}</td>
                  <td><span className={`chip chip-${h.criticality}`}>{LABEL[h.criticality] ?? h.criticality}</span></td>
                  <td className="actions">
                    {mode === "history" && <button className="btn ghost sm" onClick={() => onOpen(h.id)}><Eye size={14} /> Detalle</button>}
                    <a className="btn ghost sm" href={reportUrl(h.id)}><Download size={14} /> PDF</a>
                    {canDelete && <button type="button" className="btn danger-ghost sm" disabled={deleting!==null || exporting} onClick={()=>removeReport(h)}>{deleting===h.id?"Eliminando…":"Eliminar"}</button>}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
      {!!rows.length && <nav className="report-pagination" aria-label="Paginación de reportes"><span>{currentPage*15+1}–{Math.min((currentPage+1)*15,rows.length)} de {rows.length} reportes · Página {currentPage+1} de {totalPages}</span><button className="btn ghost" disabled={currentPage===0} onClick={()=>setPage(currentPage-1)}>Anterior</button><button className="btn ghost" disabled={currentPage+1>=totalPages} onClick={()=>setPage(currentPage+1)}>Siguiente</button></nav>}
      <p className="muted small">Se muestran hasta 200 reportes recientes. La selección se conserva al cambiar de filtro; el contador indica el total que se incluirá. Cada reporte conserva sus resultados originales.</p>
    </div>
  );
}
