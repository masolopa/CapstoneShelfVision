import { useState } from "react";
import type { Conteo } from "./types";

interface Props {
  conteo: Conteo;
}

const ESTADO: Record<string, { label: string; cls: string }> = {
  REPONER: { label: "Reponer", cls: "chip-critica" },
  REVISAR: { label: "Revisar", cls: "chip-baja" },
  OK: { label: "En orden", cls: "chip-aceptable" },
};

export function ShelfRows({ conteo }: Props) {
  const { resumen, filas } = conteo;
  const [filter, setFilter] = useState('all');
  const [page, setPage] = useState(0);
  const products = conteo.productos.filter(p => filter === 'all' || p.fila === Number(filter));
  const pages = Math.max(1, Math.ceil(products.length / 20));
  const currentPage = Math.min(page, pages - 1);
  const sinFilas = filas.length === 0;
  return (
    <section className="panel shelf-rows">
      <div className="panel-head">
        <div>
          <h2>Detecciones por estante</h2>
          <p className="muted small">Productos y frentes detectados en cada estante. Un frente es una columna de producto.</p>
        </div>
      </div>

      <div className="rows-kpis">
        <div><span>Productos</span><strong>{resumen.productos}</strong></div>
        <div><span>Filas</span><strong>{resumen.filas}</strong></div>
        <div><span>Frentes ocupados</span><strong>{resumen.frentes_ocupados} / {resumen.frentes_totales}</strong></div>
        <div><span>Frentes a reponer</span><strong>{resumen.frentes_libres}</strong></div>
        <div><span>Filas a reponer</span><strong>{resumen.filas_reponer}</strong></div>
        {resumen.frentes_para_rellenar_huecos !== undefined && (
          <div className="kpi-empty"><span>Espacios vacíos (rojo)</span><strong>{resumen.frentes_para_rellenar_huecos} frente(s)</strong></div>
        )}
      </div>

      {sinFilas ? (
        <p className="muted">No se detectaron productos dentro de la región. Si los estantes están vacíos, indica cuántas filas hay para que se muestren.</p>
      ) : (
        <div className="table-wrap">
          <table className="grid-table rows-table">
            <thead>
              <tr>
                <th>Fila</th>
                <th className="num">Productos</th>
                <th className="num">Frentes ocupados</th>
                <th className="num">Libres</th>
                <th>Ocupación</th>
                <th>Estado</th>
                <th className="num">Confianza</th>
              </tr>
            </thead>
            <tbody>
              {filas.map((f) => (
                <tr key={f.indice}>
                  <td>{f.indice}</td>
                  <td className="num">{f.productos}</td>
                  <td className="num">{f.frentes_ocupados} / {f.frentes_totales}</td>
                  <td className="num">{f.frentes_libres}</td>
                  <td>
                    <div className="mini-bar" role="img" aria-label={`Ocupación ${f.ocupacion_pct}%`}>
                      <span style={{ width: `${f.ocupacion_pct}%` }} />
                    </div>
                    <span className="small">{f.ocupacion_pct.toFixed(0)}%</span>
                  </td>
                  <td><span className={`chip ${ESTADO[f.estado].cls}`}>{ESTADO[f.estado].label}</span></td>
                  <td className="num">{f.confianza_media === null ? "—" : `${f.confianza_media.toFixed(0)}%`}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
      {conteo.productos.length > 0 && (
        <details className="product-list">
          <summary>Productos detectados ({conteo.productos.length})</summary>
          <label className="field">Estante<select value={filter} onChange={e => {setFilter(e.target.value);setPage(0);}}><option value="all">Todos</option>{filas.map(f => <option key={f.indice} value={f.indice}>{f.indice}</option>)}</select></label>
          <p>{products.length} detecciones · Página {currentPage + 1} de {pages}</p>
          <button className="btn ghost" disabled={currentPage === 0} onClick={() => setPage(currentPage - 1)}>Anterior</button><button className="btn ghost" disabled={currentPage + 1 >= pages} onClick={() => setPage(currentPage + 1)}>Siguiente</button>
          <div className="table-wrap">
            <table className="grid-table">
              <thead>
                <tr><th>ID</th><th>Fila</th><th className="num">Posición</th><th className="num">Confianza</th></tr>
              </thead>
              <tbody>
                {products.slice(currentPage * 20, (currentPage + 1) * 20).map((p) => (
                  <tr key={p.id}>
                    <td><strong>P{p.id}</strong></td>
                    <td>{p.fila}</td>
                    <td className="num">{p.posicion}</td>
                    <td className="num">{p.confianza === null ? "—" : `${p.confianza.toFixed(0)}%`}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </details>
      )}
      <p className="muted small">
        Filas a reponer: ocupación de frentes igual o menor a {resumen.umbral_pct}%. {resumen.low_threshold !== undefined && ` En orden desde ${resumen.low_threshold} %. `}La estimación de frentes libres depende del ancho de frente medido; es orientativa y no reemplaza el conteo físico.
      </p>
    </section>
  );
}
