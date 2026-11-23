import { useEffect, useState } from 'react';
import { getAnalysisSettings, saveAnalysisSettings, type AnalysisSettings } from '../../services/analysisSettings';
import './Settings.css';

type Thresholds = { critical: number; low: number };
const DEFAULTS: Thresholds = { critical: 30, low: 70 };
function valid(value:Thresholds):boolean {return Number.isInteger(value.critical) && Number.isInteger(value.low) && value.critical>=1 && value.critical<value.low && value.low<=100;}

function classify(value: number, t: Thresholds) {
  if (value <= t.critical) return { label: 'Crítico', kind: 'critical' };
  if (value < t.low) return { label: 'Bajo', kind: 'low' };
  return { label: 'Suficiente', kind: 'sufficient' };
}

export default function Settings() {
  const [saved,setSaved]=useState<Thresholds>(DEFAULTS);
  const [criticalInput,setCriticalInput]=useState(String(DEFAULTS.critical));
  const [lowInput,setLowInput]=useState(String(DEFAULTS.low));
  const [message,setMessage]=useState('');
  const [engineSaved,setEngineSaved]=useState<AnalysisSettings|null>(null);
  const [engine,setEngine]=useState({max_upload_mb:'10',min_side_px:'200'});
  const [connection,setConnection]=useState('loading');
  const [reload,setReload]=useState(0);
  const [busy,setBusy]=useState(false);
  useEffect(()=>{
    const controller=new AbortController();
    getAnalysisSettings(controller.signal).then(value=>{
      setEngineSaved(value);setSaved({critical:value.threshold,low:value.low_threshold});
      setCriticalInput(String(value.threshold));setLowInput(String(value.low_threshold));
      setEngine({max_upload_mb:String(value.max_upload_mb),min_side_px:String(value.min_side_px)});setConnection('ready');
    }).catch(()=>{if(!controller.signal.aborted)setConnection('error');});
    return()=>controller.abort();
  },[reload]);
  const critical=Number(criticalInput), low=Number(lowInput);
  const thresholds={critical,low};
  const isValid=criticalInput.trim()!=='' && lowInput.trim()!=='' && valid(thresholds);
  const dirty=critical!==saved.critical || low!==saved.low;
  const engineValues={threshold:critical,low_threshold:low,max_upload_mb:Number(engine.max_upload_mb),min_side_px:Number(engine.min_side_px)};
  const engineErrors={
    max_upload_mb:!engine.max_upload_mb.trim() || !Number.isFinite(engineValues.max_upload_mb) || engineValues.max_upload_mb<=0 || engineValues.max_upload_mb>50 ? 'Ingresa un tamaño mayor que 0 y de hasta 50 MB.' : '',
    min_side_px:!engine.min_side_px.trim() || !Number.isSafeInteger(engineValues.min_side_px) || engineValues.min_side_px<50 ? 'Ingresa un número entero de al menos 50 px.' : '',
  };
  const engineValid=Object.values(engineErrors).every(error=>!error);
  const engineDirty=engineSaved!==null && (Object.keys(engineValues) as (keyof AnalysisSettings)[]).some(key=>engineValues[key]!==engineSaved[key]);
  function changeEngine(key:'max_upload_mb'|'min_side_px',value:string){setEngine(current=>({...current,[key]:value}));setMessage('');}
  const examples=[18,45,62,85];
  const zones=isValid?[
    {kind:'critical',label:'Crítico',from:0,to:critical,width:critical,range:`0 % ≤ valor ≤ ${critical} %`},
    {kind:'low',label:'Bajo',from:critical,to:low,width:low-critical,range:`${critical} % < valor < ${low} %`},
    {kind:'sufficient',label:'Suficiente',from:low,to:100,width:100-low,range:`${low} % ≤ valor ≤ 100 %`},
  ]:[];
  async function save(){
    if(!isValid || !engineValid || busy || !engineSaved)return;
    setBusy(true);setMessage('');
    try{
      const updated=await saveAnalysisSettings(engineValues);
      setEngineSaved(updated);setSaved({critical:updated.threshold,low:updated.low_threshold});
      setCriticalInput(String(updated.threshold));setLowInput(String(updated.low_threshold));
      setEngine({max_upload_mb:String(updated.max_upload_mb),min_side_px:String(updated.min_side_px)});
      setMessage('Configuración guardada. Los próximos análisis utilizarán estos criterios.');
    }catch(error){setMessage(error instanceof Error?error.message:'No se pudo guardar.');}
    finally{setBusy(false);}
  }

  function reset() {
    setEngine({ max_upload_mb: '10', min_side_px: '200' });
    setCriticalInput(String(DEFAULTS.critical));
    setLowInput(String(DEFAULTS.low));
    setMessage('Valores predeterminados restaurados en el formulario. Presiona Guardar para conservarlos.');
  }

  return (
    <div className="settings-page">
      <div className="settings-intro">
        <span className="settings-eyebrow">ADMINISTRACIÓN DE CRITERIOS · CU02</span>
        <h2>Configuración de análisis</h2>
        <p>Define los criterios de clasificación y los requisitos de las fotografías.</p>
      </div>

      <div className="settings-notice" role="note"><span aria-hidden="true">ⓘ</span><p><strong>Alcance de los cambios.</strong> Los umbrales y los requisitos de imágenes se aplican a los próximos análisis. Cada reporte anterior conserva sus criterios y resultados originales.</p></div>
      {connection === 'loading' && <p className="settings-message" role="status">Cargando configuración del servidor…</p>}
      {connection === 'error' && <p className="settings-error" role="alert">No se pudo cargar la configuración. Comprueba que el backend esté disponible y vuelve a abrir esta sección. Los valores mostrados son de referencia; guardar está deshabilitado. <button type="button" className="settings-reset" onClick={()=>{setConnection('loading');setReload(value=>value+1);}}>Reintentar conexión</button></p>}
      <fieldset className="settings-engine" disabled={connection !== 'ready' || busy}>
        <legend className="settings-sr-only">Configuración del motor de análisis</legend>
        <section className="settings-card">
          <h3>Requisitos de imágenes</h3>
          <p className="settings-muted">Requisitos que deben cumplir las fotografías.</p>
          <div className="settings-upload-grid">
            <div><label className="settings-upload-field" htmlFor="settings-size">Tamaño máximo del archivo (MB)
              <input id="settings-size" type="number" min="0" max="50" step="any" value={engine.max_upload_mb} onChange={e => changeEngine('max_upload_mb', e.target.value)} aria-invalid={Boolean(engineErrors.max_upload_mb)} aria-describedby="settings-size-help" />
            </label><p id="settings-size-help" className={engineErrors.max_upload_mb ? 'settings-error' : 'settings-muted'}>{engineErrors.max_upload_mb || 'Se admiten archivos de hasta 50 MB según el límite configurado.'}</p></div>
            <div><label className="settings-upload-field" htmlFor="settings-dimension">Dimensión mínima de la imagen (px)
              <input id="settings-dimension" type="number" min="50" step="1" value={engine.min_side_px} onChange={e => changeEngine('min_side_px', e.target.value)} aria-invalid={Boolean(engineErrors.min_side_px)} aria-describedby="settings-dimension-help" />
            </label><p id="settings-dimension-help" className={engineErrors.min_side_px ? 'settings-error' : 'settings-muted'}>{engineErrors.min_side_px || `El ancho y el alto deben ser de al menos ${engine.min_side_px} px.`}</p></div>
          </div>
        </section>
      </fieldset>

      <div className="settings-grid">
        <section className="settings-card settings-criteria">
          <h3>Umbrales de clasificación</h3>
          <p className="settings-muted">Define los rangos de disponibilidad para cada estado.</p>
          <div className="settings-level settings-level--critical">
            <span className="settings-level-icon" aria-hidden="true">!</span>
            <div className="settings-level-copy"><strong>Estado crítico</strong><span>Disponibilidad igual o menor: genera alerta.</span></div>
            <label className="settings-level-field">Hasta (incluido)<div className="settings-input-wrap"><input type="number" disabled={busy || connection!=='ready'} min="1" max="99" step="1" value={criticalInput} onChange={(event) => { setCriticalInput(event.target.value); setMessage(''); }} aria-label="Umbral de estado crítico" /><span>%</span></div></label>
          </div>
          <div className="settings-level settings-level--low">
            <span className="settings-level-icon" aria-hidden="true">!</span>
            <div className="settings-level-copy"><strong>Estado bajo</strong><span>Por encima del crítico y por debajo de este valor.</span></div>
            <label className="settings-level-field">Menor a<div className="settings-input-wrap"><input type="number" disabled={busy || connection!=='ready'} min="2" max="100" step="1" value={lowInput} onChange={(event) => { setLowInput(event.target.value); setMessage(''); }} aria-label="Umbral de estado bajo" /><span>%</span></div></label>
          </div>
          <div className="settings-level settings-level--sufficient">
            <span className="settings-level-icon" aria-hidden="true">✓</span>
            <div className="settings-level-copy"><strong>Estado suficiente</strong><span>Desde el umbral bajo en adelante.</span></div>
            <div className="settings-level-field">Igual o mayor a<div className="settings-input-wrap"><output>{isValid ? low : '—'}</output><span>%</span></div></div>
          </div>
          {!isValid && <p className="settings-error" role="alert">Ingresa números enteros con 1 ≤ Crítico &lt; Bajo ≤ 100.</p>}
        </section>

        <div className="settings-right">
          <section className="settings-card">
            <h3>Vista previa de clasificación</h3>
            <p className="settings-muted">Representación visual de los rangos configurados.</p>
            {isValid ? <>
              <div className="settings-scale-labels"><span>0 %</span><span>100 %</span></div>
              <div className="settings-scale" role="img" aria-label={`Crítico hasta ${critical} por ciento incluido; bajo por encima de ${critical} y menor que ${low}; suficiente desde ${low} por ciento incluido`}>
                {zones.map((zone) => <div key={zone.kind} className={`settings-scale-part settings-scale-part--${zone.kind}`} style={{ flexGrow: zone.width, flexBasis: 0 }} title={`${zone.label}: ${zone.range}`} />)}
              </div>
              <div className="settings-range-cards">{zones.map((zone) => <div key={zone.kind} className={`settings-range settings-range--${zone.kind}`}><strong><i />{zone.label}</strong><span>{zone.range}</span></div>)}</div>
            </> : <div className="settings-preview-empty">Corrige los umbrales para visualizar los rangos.</div>}
          </section>
          <section className="settings-card">
            <h3>Ejemplos de clasificación</h3>
            <p className="settings-muted">Cómo se verían distintos valores con los criterios actuales.</p>
            <div className="settings-examples">{examples.map((value) => {
              const state = isValid ? classify(value, thresholds) : null;
              return <div key={value} className={`settings-example settings-example--${state?.kind ?? 'disabled'}`}><div className="settings-example-shelf" aria-hidden="true"><span /><span /><span /></div><strong>{value} %</strong><span className="settings-example-state"><i />{state?.label ?? '—'}</span></div>;
            })}</div>
          </section>
        </div>
      </div>

      <div className="settings-footer">
        <div className="settings-considerations"><span aria-hidden="true">ⓘ</span><div><strong>Consideraciones</strong><p>El estado crítico dispara la alerta. El estado suficiente empieza en el límite de Bajo y se calcula automáticamente. El estado global mide superficie; por estante se aplica el mismo criterio a la ocupación de frentes.</p></div></div>
        <div className="settings-actions"><button className="settings-reset" type="button" onClick={reset} disabled={busy}>Restablecer valores</button><button className="settings-save" type="button" disabled={!isValid || !engineValid || (!dirty && !engineDirty) || !engineSaved || busy} onClick={save}>{busy ? 'Guardando…' : 'Guardar cambios'}</button></div>
      </div>
      {message && <p className="settings-message" role="status">{message}</p>}
    </div>
  );
}
