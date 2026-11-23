import { moveHandle, validPolygon } from "./polygonGeometry";
import type { PointerEvent as ReactPointerEvent, KeyboardEvent as ReactKeyboardEvent } from "react";
import { useEffect, useRef, useState } from "react";
import { MousePointer2, Minus, Plus, RotateCcw, Trash2, Eraser, Check, Maximize2, Undo2 } from "./Glyphs";

export type PolyKind = "roi" | "exclusion" | "structural";
export type Polygon = { kind: PolyKind; points: [number, number][] };

const KIND_INFO: Record<PolyKind, { label: string; help: string; color: string }> = {
  roi: { label: "Región de análisis", help: "Define la superficie de la góndola que quieres evaluar.", color: "#2563EB" },
  exclusion: { label: "Zona excluida", help: "Obstrucciones o falta de visibilidad: no se cuentan.", color: "#9CA3AF" },
  structural: { label: "Zona estructural", help: "Soportes y separadores que no sirven para productos.", color: "#0064DC" },
};

const CLOSE_RADIUS_PX = 7; // radio visual constante, independiente del zoom
const ZOOM_STEPS = [1, 1.5, 2, 3, 4];

interface Props {
  src: string;
  imageWidth: number;
  imageHeight: number;
  polygons: Polygon[];
  onChange: (p: Polygon[]) => void;
  kind: PolyKind;
  onKindChange: (k: PolyKind) => void;
}

/** Editor de polígonos. Coordenadas normalizadas 0-1 respecto a la imagen; el zoom no altera la geometría. */
export function PolygonEditor({ src, imageWidth, imageHeight, polygons, onChange, kind, onKindChange }: Props) {
  const [draft, setDraft] = useState<[number, number][]>([]);
  const [cursor, setCursor] = useState<[number, number] | null>(null);
  const [history, setHistory] = useState<Polygon[][]>([]);
  const [selected, setSelected] = useState<number | null>(null);
  const [zoomIdx, setZoomIdx] = useState(0);
  const stageRef = useRef<HTMLDivElement>(null);
  const dragRef = useRef<{ pointer:number; polygon:number; index:number; edge:boolean; x:number; y:number; width:number; height:number; before:Polygon[]; latest:Polygon[] } | null>(null);
  const [editNotice,setEditNotice] = useState('');
  const viewportRef = useRef<HTMLDivElement>(null);
  const [fittedWidth, setFittedWidth] = useState(0);
  useEffect(() => {
    const viewport = viewportRef.current;
    if (!viewport) return;
    const observer = new ResizeObserver(([entry]) => {
      const { width, height } = entry.contentRect;
      const ratio = imageWidth / Math.max(1, imageHeight);
      setFittedWidth(Math.max(1, Math.min(imageWidth, width - 24, (height - 24) * ratio)));
    });
    observer.observe(viewport);
    return () => observer.disconnect();
  }, [imageWidth, imageHeight]);
  const color = KIND_INFO[kind].color;
  const zoom = ZOOM_STEPS[zoomIdx];

  function commit(next: Polygon[]) {
    setHistory((h) => [...h, polygons]);
    onChange(next);
  }

  function toNorm(e: React.MouseEvent<HTMLDivElement>): [number, number] {
    const r = e.currentTarget.getBoundingClientRect();
    const x = Math.min(1, Math.max(0, (e.clientX - r.left) / r.width));
    const y = Math.min(1, Math.max(0, (e.clientY - r.top) / r.height));
    return [Math.round(x * 10000) / 10000, Math.round(y * 10000) / 10000];
  }

  function closeDraft() {
    if (draft.length < 3) return;
    if (kind === "roi" && polygons.some(p => p.kind === "roi")) { window.alert("Elimina la región anterior antes de crear otra."); return; }
    commit([...polygons, { kind, points: draft }]);
    setSelected(polygons.length);
    setDraft([]);
  }

  function onStageClick(e: React.MouseEvent<HTMLDivElement>) {
    if (selected !== null) {setSelected(null);return;}
    if (e.detail > 1) return; // segundo clic de un doble clic: lo gestiona onDoubleClick
    const [x, y] = toNorm(e); // se calcula ahora: el evento de React no es accesible dentro de un setState
    if (draft.length >= 3) {
      const [fx, fy] = draft[0];
      const bounds = e.currentTarget.getBoundingClientRect();
      if (Math.hypot((x - fx) * bounds.width, (y - fy) * bounds.height) <= CLOSE_RADIUS_PX) return closeDraft();
    }
    setCursor([x, y]);
    setSelected(null);
    setDraft((d) => [...d, [x, y]]);
  }

  function undo() {
    if (draft.length > 0) return setDraft((d) => d.slice(0, -1));
    const prev = history[history.length - 1];
    if (prev) {
      setHistory((h) => h.slice(0, -1));
      onChange(prev);
      setSelected(null);
    }
  }

  function removeSelected() {
    if (selected === null) return;
    commit(polygons.filter((_, i) => i !== selected));
    setSelected(null);
  }

  function beginDrag(event:ReactPointerEvent<HTMLButtonElement>,index:number,edge:boolean) {
    event.preventDefault();event.stopPropagation();
    if(selected===null || event.button!==0 || !stageRef.current) return;
    const bounds=stageRef.current.getBoundingClientRect();
    dragRef.current={pointer:event.pointerId,polygon:selected,index,edge,x:event.clientX,y:event.clientY,width:bounds.width,height:bounds.height,before:polygons,latest:polygons};
    event.currentTarget.setPointerCapture(event.pointerId);
    setCursor(null);setEditNotice('');
  }
  function moveDrag(event:ReactPointerEvent<HTMLButtonElement>) {
    const drag=dragRef.current;
    if(!drag || event.pointerId!==drag.pointer)return;
    event.stopPropagation();
    const points=moveHandle(drag.before[drag.polygon].points,drag.index,drag.edge,(event.clientX-drag.x)/drag.width,(event.clientY-drag.y)/drag.height);
    if(!validPolygon(points)){setEditNotice('Ese ajuste cruzaría los bordes o colapsaría la zona. Ajusta en otra dirección.');return;}
    const next=drag.before.map((polygon,i)=>i===drag.polygon?{...polygon,points}:polygon);
    drag.latest=next;onChange(next);setEditNotice('');
  }
  function finishDrag(cancel=false) {
    const drag=dragRef.current;
    if(!drag)return;
    dragRef.current=null;
    if(cancel){onChange(drag.before);setEditNotice('Ajuste cancelado.');return;}
    if(JSON.stringify(drag.latest)!==JSON.stringify(drag.before)){setHistory(previous=>[...previous,drag.before]);setEditNotice('Contorno ajustado. Puedes deshacer el cambio.');}
  }
  function nudge(event:ReactKeyboardEvent<HTMLButtonElement>,index:number,edge:boolean) {
    const directions:Record<string,[number,number]>={ArrowLeft:[-1,0],ArrowRight:[1,0],ArrowUp:[0,-1],ArrowDown:[0,1]};
    if(event.key==='Escape'){finishDrag(true);return;}
    const direction=directions[event.key];
    if(!direction || selected===null || !stageRef.current)return;
    event.preventDefault();event.stopPropagation();
    const bounds=stageRef.current.getBoundingClientRect();
    const step=event.shiftKey?5:1;
    const points=moveHandle(polygons[selected].points,index,edge,direction[0]*step/bounds.width,direction[1]*step/bounds.height);
    if(validPolygon(points))commit(polygons.map((polygon,i)=>i===selected?{...polygon,points}:polygon));
  }
  const selectedPolygon=selected===null?null:polygons[selected];
  const toPts = (pts: [number, number][]) => pts.map(([x, y]) => `${x * 100},${y * 100}`).join(" ");
  const count = (k: PolyKind) => polygons.filter((p) => p.kind === k).length;
  const roiCount = count("roi");

  return (
    <div className="editor">
      <aside className="editor-panel" aria-label="Herramientas de edición">
        <h3>Herramientas</h3>
        <div className="tool-list" role="radiogroup" aria-label="Tipo de zona">
          {(Object.keys(KIND_INFO) as PolyKind[]).map((k) => (
            <button
              key={k}
              role="radio"
              aria-checked={k === kind}
              className={`tool ${k === kind ? "is-active" : ""}`}
              onClick={() => { if (draft.length && !window.confirm("¿Descartar el trazado sin cerrar para cambiar de herramienta?")) return; setDraft([]); setSelected(null); setEditNotice(''); onKindChange(k); }}
              title={KIND_INFO[k].help}
            >
              <span className="swatch" style={{ background: KIND_INFO[k].color }} />
              <span className="tool-text">
                <b>{KIND_INFO[k].label}</b>
                <small>{KIND_INFO[k].help}</small>
              </span>
            </button>
          ))}
        </div>

        <div className="tool-actions">
          <button className="btn ghost" onClick={undo} disabled={draft.length === 0 && history.length === 0} title="Deshacer (último punto o último cambio)">
            <Undo2 size={16} /> Deshacer
          </button>
          <button className="btn ghost" onClick={() => { setDraft([]); }} disabled={draft.length === 0} title="Cancelar el dibujo en curso">
            Cancelar dibujo
          </button>
          <button className="btn ghost" onClick={closeDraft} disabled={draft.length < 3} title="Cerrar la zona (mínimo 3 puntos)">
            <Check size={16} /> Cerrar zona
          </button>
          <button className="btn danger-ghost" onClick={removeSelected} disabled={selected === null} title="Eliminar la zona seleccionada">
            <Trash2 size={16} /> Eliminar seleccionada
          </button>
          <button
            className="btn danger-ghost"
            onClick={() => { commit([]); setDraft([]); setSelected(null); }}
            disabled={polygons.length === 0 && draft.length === 0}
            title="Quitar todas las zonas"
          >
            <Eraser size={16} /> Limpiar todo
          </button>
        </div>

        <div className="zoom-controls" aria-label="Zoom">
          <button className="icon-btn" onClick={() => setZoomIdx((i) => Math.max(0, i - 1))} disabled={zoomIdx === 0} aria-label="Alejar"><Minus size={16} /></button>
          <span className="zoom-label">{zoomIdx === 0 ? "Ajustada" : `${Math.round(zoom * 100)}%`}</span>
          <button className="icon-btn" onClick={() => setZoomIdx((i) => Math.min(ZOOM_STEPS.length - 1, i + 1))} disabled={zoomIdx === ZOOM_STEPS.length - 1} aria-label="Acercar"><Plus size={16} /></button>
          <button className="icon-btn" onClick={() => setZoomIdx(0)} aria-label="Ajustar imagen" title="Ajustar al espacio disponible"><Maximize2 size={16} /></button>
          <button className="icon-btn" onClick={() => setZoomIdx(0)} aria-label="Restablecer zoom" title="Restablecer zoom"><RotateCcw size={16} /></button>
        </div>

        <div className="counts">
          <span><i style={{ background: KIND_INFO.roi.color }} /> {roiCount} región</span>
          <span><i style={{ background: KIND_INFO.exclusion.color }} /> {count("exclusion")} excluidas</span>
          <span><i style={{ background: KIND_INFO.structural.color }} /> {count("structural")} estructurales</span>
        </div>
        {roiCount > 1 && (
          <p className="notice warn" role="alert">
            Hay {roiCount} regiones de análisis. Por ahora el sistema solo procesa una. Deja una sola para poder analizar.
          </p>
        )}
      </aside>

      <div className="canvas-wrap">
        <div className="canvas-scroll" ref={viewportRef} onScroll={() => setCursor(null)}>
          <div className="canvas" style={{ width: fittedWidth ? `${fittedWidth * zoom}px` : "1px", visibility: fittedWidth ? "visible" : "hidden" }}>
            <div
              ref={stageRef} className="stage" data-drawing={draft.length > 0 ? "true" : "false"}
              onMouseMove={event => setCursor(toNorm(event))}
              onMouseLeave={() => setCursor(null)}
              onClick={onStageClick}
              onDoubleClick={(e) => { e.preventDefault(); closeDraft(); }}
              role="application"
              aria-label="Área de dibujo: clic para añadir puntos, doble clic para cerrar"
            >
              <img src={src} alt="Fotografía de la góndola" draggable={false} />
              <svg viewBox="0 0 100 100" preserveAspectRatio="none" className="overlay">
                {polygons.map((p, i) => (
                  <polygon
                    key={i}
                    points={toPts(p.points)}
                    fill={KIND_INFO[p.kind].color}
                    fillOpacity={i === selected ? 0.45 : 0.3}
                    stroke={KIND_INFO[p.kind].color}
                    strokeWidth={i === selected ? 3 : 2}
                    vectorEffect="non-scaling-stroke"
                    onClick={(e) => { if (draft.length || (selected === null && p.kind !== kind)) return; e.stopPropagation(); setSelected(i); }}
                    style={{ cursor: "pointer" }}
                  />
                ))}
                {draft.length > 0 && (
                  <g pointerEvents="none" aria-hidden="true">
                    <polyline points={toPts(draft)} fill="none" stroke={color} strokeWidth={1.4} vectorEffect="non-scaling-stroke" />
                    {cursor && <>
                      <polyline points={toPts([draft[draft.length - 1], cursor])} fill="none" stroke={color} strokeWidth={1.4} strokeDasharray="6 4" vectorEffect="non-scaling-stroke" />
                    </>}
                  </g>
                )}
              </svg>
              {selectedPolygon && !draft.length && selectedPolygon.points.map((point,index)=>{
                const next=selectedPolygon.points[(index+1)%selectedPolygon.points.length];
                const angle=Math.atan2((next[1]-point[1])*imageHeight,(next[0]-point[0])*imageWidth)*180/Math.PI;
                return <span key={`handles-${index}`}>
                  {[false,true].map(edge=><button key={String(edge)} type="button" className={`polygon-handle ${edge?'polygon-handle-edge':'polygon-handle-vertex'}`} style={{left:`${(edge?(point[0]+next[0])/2:point[0])*100}%`,top:`${(edge?(point[1]+next[1])/2:point[1])*100}%`, '--handle-angle':`${angle}deg`} as React.CSSProperties}
                    aria-label={`${edge?'Mover borde':'Mover vértice'} ${index+1}`} title={`${edge?'Arrastra para mover este lado':'Arrastra para ajustar esta esquina'}. También puedes usar las flechas.`}
                    onPointerDown={event=>beginDrag(event,index,edge)} onPointerMove={moveDrag} onPointerUp={()=>finishDrag()} onPointerCancel={()=>finishDrag(true)} onLostPointerCapture={()=>finishDrag(true)}
                    onClick={event=>event.stopPropagation()} onDoubleClick={event=>event.stopPropagation()} onKeyDown={event=>nudge(event,index,edge)}><span /></button>)}
                </span>;
              })}
              {draft.map(([x, y], i) => (
                <div
                  key={i}
                  className={`pt ${i === 0 ? "pt-first" : ""}`}
                  style={{ left: `${x * 100}%`, top: `${y * 100}%`, background: color }}
                  title={i === 0 ? "Primer punto: haz clic aquí para cerrar la zona" : `Punto ${i + 1}`}
                >
                  <span className="pt-label">{i + 1}</span>
                </div>
              ))}
            </div>
          </div>
        </div>
        <p className="canvas-hint">
          <MousePointer2 size={14} />{" "}
          {selectedPolygon && !draft.length
            ? 'Arrastra los tiradores celestes: círculos para las esquinas y rayitas para los bordes. Haz clic fuera para terminar.'
            : draft.length === 0
            ? `Haz clic sobre la foto para empezar: ${KIND_INFO[kind].label.toLowerCase()}.`
            : draft.length < 3
              ? `Punto ${draft.length}. Necesitas al menos 3 puntos para cerrar la zona.`
              : `${draft.length} puntos. Haz clic en el punto 1 (o doble clic) para cerrar.`}
        </p>
        {editNotice && <p className="canvas-hint" role="status">{editNotice}</p>}
      </div>
    </div>
  );
}
